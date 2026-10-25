"""Frozen-protocol study orchestration, keeping historical and fresh-split tracks apart."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import platform
import subprocess
import time
from collections import Counter
from importlib.metadata import version
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from rcqasyn.datasets.loader import load_dataset
from rcqasyn.datasets.registry import DatasetRegistry
from rcqasyn.datasets.split import make_split
from rcqasyn.phase2.common import digest, read_bundle
from rcqasyn.phase5.contracts import STRATEGIES, SelectionConfig
from rcqasyn.phase5.geometry import complete_record, feature_supported, metrics
from rcqasyn.phase5.selection import select
from rcqasyn.phase5.workflow import load_context, pool
from rcqasyn.phase6.utility import outer_frames, synthetic_sources

from .evaluation import (
    METRICS,
    aligned,
    bootstrap_metrics,
    evaluate,
    interval,
    stratified_indices,
)
from .generation import fresh_geometry, generate


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+"\n",
                    encoding="utf-8")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_predictions(output: Path, row: dict[str, Any]) -> list[dict[str, Any]]:
    data = json.loads(gzip.decompress((output/row["prediction_path"]).read_bytes()))
    if digest(data) != row["prediction_fingerprint"]:
        raise ValueError("saved prediction identity mismatch")
    return data


class Study:
    def __init__(self, root: Path, source: Path, output: Path):
        if output.exists():
            raise FileExistsError("use a fresh versioned output directory")
        if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip() != (
                "244a9bfd490a03a35c4be5cb3b83354e425795fc"):
            raise ValueError("source checkout differs from frozen base")
        self.root, self.source, self.output = root, source, output
        self.config = json.loads((root/"configs/empirical/protocol-v1.json").read_text("utf-8-sig"))
        self.rows: list[dict[str, Any]] = []
        self.constructions: list[dict[str, Any]] = []
        self.populations: list[dict[str, Any]] = []
        self.failures: list[dict[str, Any]] = []
        self.replay_checks: list[dict[str, Any]] = []
        self.registry = DatasetRegistry(project_root=source)
        self.ctx = load_context(root, source)
        output.mkdir(parents=True)

    def score(self, meta: dict[str, Any], train: pd.DataFrame, test: pd.DataFrame,
              synthetic: pd.DataFrame, spec: Any, regimes: tuple[str, ...],
              *, classifiers: list[str] | None = None, balanced: bool = False) -> None:
        for classifier in classifiers or self.config["classifiers"]:
            for regime in regimes:
                reason = None
                if regime == "TRTR":
                    actual = train
                elif regime == "TSTR":
                    actual = synthetic
                elif regime == "HYBRID_MINORITY":
                    minority = synthetic.loc[synthetic[spec.target_column] == spec.minority_label]
                    actual = pd.concat([train, minority], ignore_index=True)
                    if minority.empty:
                        reason = "NO_SYNTHETIC_MINORITY_AUGMENTATION"
                else:
                    raise ValueError("unknown regime")
                try:
                    result = evaluate(actual, test, spec, classifier, balanced=balanced) if not reason else {
                        "status": "unavailable", "reason": reason, "training_n": len(actual),
                        "test_positive_n": int((test[spec.target_column] == spec.minority_label).sum()),
                        "test_negative_n": int((test[spec.target_column] != spec.minority_label).sum())}
                except (ValueError, TypeError, RuntimeError) as error:
                    result = {"status": "failed", "reason": f"{type(error).__name__}: {error}"}
                predictions = result.pop("predictions", None)
                if predictions is not None:
                    relative = "predictions/"+result["prediction_fingerprint"]+".json.gz"
                    path = self.output/relative
                    path.parent.mkdir(exist_ok=True)
                    path.write_bytes(gzip.compress(json.dumps(predictions, sort_keys=True,
                                                              allow_nan=False).encode(), mtime=0))
                    result["prediction_path"] = relative
                self.rows.append({**meta, "classifier": classifier, "regime": regime,
                                  "classifier_seed": 42, "selection_budget": meta.get("budget", 0),
                                  "synthetic_input_n": len(synthetic),
                                  "synthetic_class_counts": dict(Counter(synthetic[spec.target_column])),
                                  **result})

    def construct(self, g: Any, eligible: list[int], concern: dict[int, float],
                  strategy: str, budget: int, seed: int, meta: dict[str, Any]) -> pd.DataFrame:
        if strategy == "random":
            selected = np.random.default_rng(seed).permutation(eligible)[:budget].tolist()
            measured = metrics(g, selected, eligible, .05, .01)
        else:
            recipe = select(g, eligible, concern, SelectionConfig.model_validate({"strategy": strategy, "budget": budget}))
            selected, measured = recipe["selected_indices"], recipe["metrics"]
        records = [g.occurrences[i] for i in selected]
        self.constructions.append({**meta, "strategy": strategy, "seed": seed,
                                   "eligible_n": len(eligible), "budget": budget,
                                   "budget_achieved": len(selected),
                                   "status": "ok" if len(selected) == budget else "unavailable",
                                   "reason": None if len(selected) == budget else "MATCHED_BUDGET_SHORTFALL",
                                   "selected_ids": [r["occurrence_id"] for r in records],
                                   "selected_payload_fingerprint": digest([r["payload"] for r in records]),
                                   **measured})
        return pd.DataFrame([r["payload"] for r in records],
                            columns=[f["name"] for f in g.fields]+[g.target])

    def population(self, track: str, loaded: Any, split: dict[str, Any],
                   train: pd.DataFrame, test: pd.DataFrame, seed: int) -> dict[str, Any]:
        spec = loaded.spec
        features = list(spec.feature_columns)
        hashes = {digest(r) for r in train.loc[:, features].to_dict(orient="records")}
        overlap = sum(digest(r) in hashes for r in test.loc[:, features].to_dict(orient="records"))
        row = {"track": track, "dataset_id": spec.dataset_id, "split_seed": seed,
               **split, "train_class_counts": dict(Counter(train[spec.target_column])),
               "test_class_counts": dict(Counter(test[spec.target_column])),
               "test_rows_with_train_feature_overlap": overlap,
               "source_file_sha256": file_hash(loaded.path),
               "dataset_fingerprint": loaded.fingerprint}
        self.populations.append(row)
        return {"track": track, "dataset_id": spec.dataset_id, "split_seed": seed,
                "split_fingerprint": split["split_fingerprint"]}

    def external(self, train: pd.DataFrame, test: pd.DataFrame, spec: Any,
                 meta: dict[str, Any], seed: int, budget: int) -> None:
        empty = train.iloc[:0]
        self.score({**meta, "method": "REAL_TRAIN", "category": "real-training"},
                   train, test, empty, spec, ("TRTR",))
        self.score({**meta, "method": "CLASS_WEIGHTED_LR", "category": "classifier-training"},
                   train, test, empty, spec, ("TRTR",),
                   classifiers=["logistic_regression"], balanced=True)
        for method in ["RandomOverSampler", "SMOTENC" if spec.categorical_columns else "SMOTE"]:
            smeta = {**meta, "method": method+"+b", "category": "generation-augmentation",
                     "budget": budget}
            try:
                generated, provenance = generate(train, spec, method, budget, seed)
                provenance_path = f"generation/{meta['track']}-{spec.dataset_id}-{seed}-{method}.json"
                write_json(self.output/provenance_path,
                           {"provenance": provenance, "payloads": generated.to_dict(orient="records")})
                compliant = sum(complete_record(r, self.ctx.specifications[spec.dataset_id]["specification"])
                                for r in generated.to_dict(orient="records"))
                self.score({**smeta, "generation_path": provenance_path,
                            "generated_structural_complete_n": compliant,
                            "generated_noncompliant_n": len(generated)-compliant},
                           train, test, generated, spec, ("HYBRID_MINORITY",))
            except (ValueError, TypeError, RuntimeError) as error:
                self.failures.append({**smeta, "status": "unavailable", "reason": str(error)})
        incompatible = "SMOTE" if spec.categorical_columns else "SMOTENC"
        self.failures.append({**meta, "method": incompatible, "status": "unavailable",
                              "reason": "INCOMPATIBLE_DECLARED_FEATURE_TYPES; use declared counterpart"})

    def historical(self) -> None:
        core = self.root/"artifacts/reports/phase6/core-v1"
        archive = read_bundle(self.root/"artifacts/reports/phase6/utility-v1")["results"]
        for dataset in self.config["datasets"]:
            print("Track A:", dataset, flush=True)
            spec = self.registry.get(dataset)
            loaded = load_dataset(spec, self.registry)
            split = json.loads((self.source/f"data/manifests/{dataset}/split_manifest.json").read_text())
            train, test = outer_frames(loaded.frame, split)
            meta = self.population("A", loaded, split, train, test, split["root_seed"])
            self.external(train, test, spec, meta, 13, self.config["budgets"][dataset])
            for source in synthetic_sources(self.ctx, core, dataset):
                frame = pd.DataFrame([r["payload"] for r in source["records"]], columns=train.columns)
                self.score({**meta, "method": source["name"], "category": "historical-replay",
                            "source_fingerprint": source["fingerprint"],
                            "budget": len(frame)}, train, test, frame, spec,
                           ("TSTR", "HYBRID_MINORITY"))
            # Every old utility row, including unavailable rows, must be reproduced.
            for old in [r for r in archive if r["dataset_id"] == dataset]:
                new = next(r for r in self.rows if r["track"] == "A"
                           and r["dataset_id"] == dataset and r["method"] == old["method"]
                           and r["regime"] == old["regime"] and r["classifier"] == old["classifier"])
                previous = old["evaluation_result"]
                matches = previous["status"] == new["status"] and all(
                    previous.get(m) == new.get(m) or (
                        previous.get(m) is not None and new.get(m) is not None
                        and abs(previous[m]-new[m]) < 1e-12) for m in METRICS)
                self.replay_checks.append({"dataset_id": dataset, "method": old["method"],
                                           "regime": old["regime"], "classifier": old["classifier"],
                                           "matches": matches})
                if not matches:
                    raise ValueError(f"frozen utility replay mismatch: {old['method']}")
            g = self.ctx.geometries[dataset]
            budget = self.config["budgets"][dataset]
            config = SelectionConfig(strategy="quality-coverage", budget=budget)
            combined, _, _ = pool(self.ctx, dataset, config)
            decisions = self.ctx.shadow["decisions"]
            pools = {policy: [i for i, o in enumerate(g.occurrences) if any(
                r["occurrence_id"] == o["occurrence_id"] and r["policy"]["name"] == policy
                and r["action"] == "PROVISIONAL_PASS" for r in decisions)
                and complete_record(o["payload"], self.ctx.specifications[dataset]["specification"])]
                for policy in ["structure-only", "local-review", "global-review"]}
            pools["combined-review"] = combined
            # Concerns are held fixed even when an ablation changes admission eligibility.
            vectors = {r["occurrence_id"]: r for r in self.ctx.shadow["harmonized"]["vectors"]}
            all_concerns = {i: vectors[o["occurrence_id"]]["fusion"]["uncalibrated_max"]
                            for i, o in enumerate(g.occurrences)}
            raw = [i for i, o in enumerate(g.occurrences)
                   if feature_supported(o["payload"], g.fields)
                   and o["payload"].get(g.target) in ["positive", "negative"]
                   and all(o["payload"][f["name"]] in f["documented_categories"]
                           for f in g.fields if f["type"] == "categorical")]
            designs = [(name+"/random", indices, "random", seed)
                       for name, indices in [("raw-labeled", raw),
                                              ("schema", pools["structure-only"]),
                                              ("combined", combined)]
                       for seed in self.config["selection_seeds"]]
            designs += [("ablation/"+name, indices, "quality-coverage", 42)
                        for name, indices in pools.items()]
            designs += [("selection/"+name, combined, name, 42) for name in STRATEGIES]
            for method, eligible, strategy, seed in designs:
                m = {**meta, "method": method+f"/s{seed}", "category": "candidate-curation",
                     "budget": budget, "selection_seed": seed}
                frame = self.construct(g, eligible, all_concerns, strategy, budget, seed, m)
                self.score(m, train, test, frame, spec, ("TSTR", "HYBRID_MINORITY"))

    def replication(self) -> None:
        for dataset in self.config["datasets"]:
            spec = self.registry.get(dataset)
            loaded = load_dataset(spec, self.registry)
            for seed in self.config["split_seeds"]:
                print("Track B:", dataset, seed, flush=True)
                split = make_split(loaded, seed).to_dict()
                train, test = outer_frames(loaded.frame, split)
                meta = self.population("B", loaded, split, train, test, seed)
                budget = self.config["budgets"][dataset]
                self.external(train, test, spec, meta, seed, budget)
                try:
                    candidates, provenance = generate(train, spec,
                        self.config["replication_generators"][dataset], 4*budget, seed)
                    if set(provenance["fit_row_ids"]) & set(test.index):
                        raise ValueError("generator fit identities overlap TEST")
                    g, pools, concerns, evidence = fresh_geometry(
                        train, candidates, self.ctx.specifications[dataset],
                        split["split_fingerprint"], provenance)
                    write_json(self.output/f"replication/{dataset}-{seed}.json", evidence)
                    designs = [("schema/random", pools["schema"], "random"),
                               ("combined/random", pools["combined"], "random")]
                    designs += [("combined/"+s, pools["combined"], s) for s in STRATEGIES]
                    for method, eligible, strategy in designs:
                        m = {**meta, "method": method, "category": "offline-candidate-curation",
                             "budget": budget, "generator": provenance["generator"]}
                        frame = self.construct(g, eligible, concerns, strategy, budget, seed, m)
                        self.score(m, train, test, frame, spec, ("TSTR", "HYBRID_MINORITY"))
                except (ValueError, TypeError, RuntimeError) as error:
                    self.failures.append({**meta, "status": "failed", "method": "offline-curation",
                                          "reason": f"{type(error).__name__}: {error}"})

    def bootstrap(self) -> None:
        results, differences = [], []
        cfg = self.config["bootstrap"]
        for dataset in self.config["datasets"]:
            historical = [r for r in self.rows if r["track"] == "A" and r["dataset_id"] == dataset]
            primary = {"REAL_TRAIN", "quality-coverage:original", "quality-coverage:repair-augmented",
                       "schema/random/s13", "combined/random/s13"}
            rows = [r for r in historical if r["method"] in primary and r["status"] == "ok"]
            first = load_predictions(self.output, rows[0])
            indices = stratified_indices(np.array([r["y"] for r in first]), cfg["replicates"], cfg["seed"])
            buffer = io.BytesIO()
            np.save(buffer, indices, allow_pickle=False)
            (self.output/f"bootstrap-{dataset}.npy.gz").write_bytes(gzip.compress(buffer.getvalue(), mtime=0))
            cache = {}
            for row in rows:
                predictions = load_predictions(self.output, row)
                aligned(first, predictions)
                key = (row["method"], row["classifier"], row["regime"])
                samples = bootstrap_metrics(predictions, indices)
                cache[key] = samples
                for metric, values in samples.items():
                    results.append({"dataset_id": dataset, "method": row["method"],
                                    "classifier": row["classifier"], "regime": row["regime"],
                                    "metric": metric, "estimate": row[metric],
                                    "positive_n": row["test_positive_n"], "negative_n": row["test_negative_n"],
                                    "tp": row["tp"], "fp": row["fp"], "tn": row["tn"], "fn": row["fn"],
                                    "bootstrap_seed": cfg["seed"], "replicates": cfg["replicates"],
                                    "indices_fingerprint": hashlib.sha256(indices.tobytes()).hexdigest(),
                                    **interval(values)})
            for classifier in self.config["classifiers"]:
                for regime in ["TSTR", "HYBRID_MINORITY"]:
                    original = ("quality-coverage:original", classifier, regime)
                    repaired = ("quality-coverage:repair-augmented", classifier, regime)
                    pairs = [(repaired, original)]
                    pairs += [(original, (name, classifier, regime))
                              for name in ["schema/random/s13", "combined/random/s13"]]
                    if regime == "HYBRID_MINORITY":
                        pairs.append((original, ("REAL_TRAIN", classifier, "TRTR")))
                    for left, right in pairs:
                        if left not in cache or right not in cache:
                            self.failures.append({"track": "A-bootstrap", "dataset_id": dataset,
                                "method": str((left, right)), "status": "unavailable",
                                "reason": "PAIRED_METHOD_PREDICTIONS_UNAVAILABLE"})
                            continue
                        for metric in cache[left]:
                            differences.append({"dataset_id": dataset, "left": list(left),
                                                "right": list(right), "metric": metric,
                                                "replicates": cfg["replicates"],
                                                **interval(cache[left][metric]-cache[right][metric])})
        write_json(self.output/"bootstrap.json", results)
        write_json(self.output/"paired-differences.json", differences)

    def finish(self, runtime: float) -> dict[str, Any]:
        write_json(self.output/"results.json", self.rows)
        write_json(self.output/"constructions.json", self.constructions)
        write_json(self.output/"populations.json", self.populations)
        write_json(self.output/"unavailable.json", self.failures)
        write_json(self.output/"historical-replay.json", self.replay_checks)
        pd.DataFrame(self.rows).to_csv(self.output/"results.csv", index=False)
        repeated = pd.DataFrame([r for r in self.rows if r["track"] == "B"])
        summary = []
        for key, group in repeated.groupby(["dataset_id", "method", "classifier", "regime"], sort=True):
            valid = group.loc[group.status == "ok"]
            row: dict[str, Any] = dict(zip(["dataset_id", "method", "classifier", "regime"], cast(tuple[Any, ...], key), strict=True))
            row.update(n_splits=len(group), completed=len(valid), unavailable=len(group)-len(valid))
            for metric in METRICS:
                values = valid[metric].dropna()
                row[metric+"_mean"] = float(values.mean()) if len(values) else None
                row[metric+"_std"] = float(values.std(ddof=1)) if len(values) > 1 else None
            summary.append(row)
        write_json(self.output/"split-summary.json", summary)
        hashes = {p.relative_to(self.output).as_posix(): file_hash(p)
                  for p in sorted(self.output.rglob("*")) if p.is_file()}
        code_hashes = {p.relative_to(self.root).as_posix(): file_hash(p)
                       for folder in [self.root/"src/rcqasyn/empirical", self.root/"scripts"]
                       for p in sorted(folder.glob("*.py"))}
        manifest = {"base_sha": self.config["base_sha"],
                    "implementation_revision": subprocess.check_output(
                        ["git", "rev-parse", "HEAD"], cwd=self.root, text=True).strip(),
                    "code_hashes": code_hashes, "protocol_fingerprint": digest(self.config),
                    "protocol_document_sha256": file_hash(self.root/"docs/empirical-v2/protocol.md"),
                    "python": platform.python_version(), "platform": platform.platform(),
                    "dependencies": {p: version(p) for p in ["numpy", "pandas", "scipy", "scikit-learn",
                                                           "imbalanced-learn", "sklearn-compat"]},
                    "bootstrap_configuration": self.config["bootstrap"], "runtime_seconds": runtime,
                    "result_content_fingerprint": digest({"rows": self.rows, "constructions": self.constructions,
                                                           "populations": self.populations, "summary": summary}),
                    "status_counts": dict(Counter(r["status"] for r in self.rows)),
                    "historical_replay_rows": len(self.replay_checks),
                    "historical_replay_all_match": all(r["matches"] for r in self.replay_checks),
                    "output_hashes": hashes, "human_annotation_active": False,
                    "test_used_for_selection": False,
                    "replication_interpretation": "Overlapping repeated random holdouts; offline generator curation, not LLM replication"}
        write_json(self.output/"manifest.json", manifest)
        return manifest


def run(root: Path, source: Path, output: Path) -> dict[str, Any]:
    start = time.perf_counter()
    study = Study(root, source, output)
    study.historical()
    study.replication()
    study.bootstrap()
    return study.finish(time.perf_counter()-start)
