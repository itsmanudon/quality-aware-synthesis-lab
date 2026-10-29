"""Exploratory addendum v1, declared after the main study; never merged into canonical tables.

Reuses the frozen Study scoring, construction, population and external-comparator methods
unchanged. Only new designs (new datasets, a real-ratio quota, an equal-budget B2 control and
bounded repair of fresh pools) are added here, behind a separate entry point and output.
"""
from __future__ import annotations

import json
import platform
import subprocess
import time
from collections import Counter
from importlib.metadata import version
from pathlib import Path
from typing import Any

import pandas as pd

from rcqasyn.datasets.loader import load_dataset
from rcqasyn.datasets.registry import DatasetRegistry
from rcqasyn.datasets.split import make_split
from rcqasyn.phase2.common import digest
from rcqasyn.phase2.specifications import dataset_specification
from rcqasyn.phase3.contracts import M2Config
from rcqasyn.phase3.validators import TrainEvidenceModel
from rcqasyn.phase5.contracts import STRATEGIES, SelectionConfig
from rcqasyn.phase5.geometry import complete_record
from rcqasyn.phase5.selection import select
from rcqasyn.phase5.workflow import load_context, pool
from rcqasyn.phase6.repair import propose_repair
from rcqasyn.phase6.utility import outer_frames

from .evaluation import METRICS
from .generation import fresh_geometry, generate
from .study import Study, file_hash, write_json

FROZEN_SOURCE = "244a9bfd490a03a35c4be5cb3b83354e425795fc"
# The addendum is a self-contained project root outside every protected historical path
# (data/, configs/, artifacts/reports/ ...), so the canonical inventory and crosswalk
# snapshots never see it. Its layout mirrors the root the canonical builders expect.
ADDENDUM = "addendum/v1"
CONFIG = ADDENDUM+"/addendum-v1.json"
LABEL = "EXPLORATORY_ADDENDUM_DECLARED_AFTER_MAIN_STUDY"


def budget_rule(n_minority: int) -> int:
    return min(70, max(30, round(.5*n_minority)))


class Addendum(Study):
    def __init__(self, root: Path, source: Path, output: Path):
        if output.exists():
            raise FileExistsError("use a fresh versioned output directory")
        if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source,
                                   text=True).strip() != FROZEN_SOURCE:
            raise ValueError("source checkout differs from frozen base")
        self.root, self.source, self.output = root, source, output
        self.config = json.loads((root/CONFIG).read_text("utf-8"))
        self.rows: list[dict[str, Any]] = []
        self.constructions: list[dict[str, Any]] = []
        self.populations: list[dict[str, Any]] = []
        self.failures: list[dict[str, Any]] = []
        self.replay_checks: list[dict[str, Any]] = []
        self.pools: list[dict[str, Any]] = []
        self.repairs: list[dict[str, Any]] = []
        self.registry = DatasetRegistry(project_root=source)
        self.addendum = root/ADDENDUM
        self.new_registry = DatasetRegistry(project_root=self.addendum)
        self.ctx = load_context(root, source)
        self.new_datasets = [d for d in self.config["E1"]["datasets"]
                             if d not in self.config["E1"]["unavailable_datasets"]]
        for dataset in self.new_datasets:
            # The existing builder verifies the recorded split, source checksum and raw schema.
            self.ctx.specifications[dataset] = dataset_specification(self.addendum, dataset)
        output.mkdir(parents=True)

    def construct_config(self, g: Any, eligible: list[int], concern: dict[int, float],
                         config: SelectionConfig, meta: dict[str, Any]) -> pd.DataFrame:
        """Study.construct with a full SelectionConfig, needed only for the E2 quota."""
        recipe = select(g, eligible, concern, config)
        selected, measured = recipe["selected_indices"], recipe["metrics"]
        records = [g.occurrences[i] for i in selected]
        self.constructions.append({**meta, "strategy": config.strategy, "seed": config.seed,
                                   "eligible_n": len(eligible), "budget": config.budget,
                                   "budget_achieved": len(selected),
                                   "status": "ok" if len(selected) == config.budget else "unavailable",
                                   "reason": None if len(selected) == config.budget
                                   else "MATCHED_BUDGET_SHORTFALL",
                                   "minority_quota_fraction": config.minority_quota_fraction,
                                   "minority_quota_requested": recipe["minority_quota_requested"],
                                   "minority_quota_feasible": recipe["minority_quota_feasible"],
                                   "selected_ids": [r["occurrence_id"] for r in records],
                                   "selected_payload_fingerprint": digest([r["payload"] for r in records]),
                                   **measured})
        return pd.DataFrame([r["payload"] for r in records],
                            columns=pd.Index([f["name"] for f in g.fields]+[g.target]))

    def track_a(self) -> None:
        """E2 and E3 on the historical split, plus same-environment canonical comparators."""
        for dataset in self.config["E2"]["datasets"]:
            print("Track A:", dataset, flush=True)
            spec = self.registry.get(dataset)
            loaded = load_dataset(spec, self.registry)
            split = json.loads((self.source/f"data/manifests/{dataset}/split_manifest.json").read_text())
            train, test = outer_frames(loaded.frame, split)
            g = self.ctx.geometries[dataset]
            budget = self.config["E2"]["budgets"][dataset]
            specification = self.ctx.specifications[dataset]["specification"]
            combined, _, _ = pool(self.ctx, dataset, SelectionConfig(strategy="quality-coverage",
                                                                     budget=budget))
            vectors = {r["occurrence_id"]: r for r in self.ctx.shadow["harmonized"]["vectors"]}
            concerns = {i: vectors[o["occurrence_id"]]["fusion"]["uncalibrated_max"]
                        for i, o in enumerate(g.occurrences)}
            positives = int((train[spec.target_column] == spec.minority_label).sum())
            fraction = positives/len(train)
            b2 = [i for i, o in enumerate(g.occurrences) if o["controls"]["b2"]["decision"]["accepted"]
                  and complete_record(o["payload"], specification)]
            base = self.population("A", loaded, split, train, test, split["root_seed"])
            for track, name, eligible, config in [
                    ("A-reproduction", "selection/quality-coverage/s42", combined,
                     SelectionConfig(strategy="quality-coverage", budget=budget)),
                    ("E2", "E2/quality-coverage-real-ratio/s42", combined,
                     SelectionConfig(strategy="quality-coverage", budget=budget,
                                     minority_quota_fraction=float(fraction)))]:
                meta = {**base, "track": track, "method": name, "category": "candidate-curation", "budget": budget,
                        "selection_seed": 42, "train_minority_fraction": fraction,
                        "addendum_label": LABEL}
                frame = self.construct_config(g, eligible, concerns, config, meta)
                self.score(meta, train, test, frame, spec, ("TSTR", "HYBRID_MINORITY"))
            for track, prefix, eligible in [("A-reproduction", "combined/random", combined),
                                            ("E3", "E3/b2-accepted-random", b2)]:
                for seed in self.config["selection_seeds"]:
                    meta = {**base, "track": track, "method": f"{prefix}/s{seed}", "category": "candidate-curation",
                            "budget": budget, "selection_seed": seed, "addendum_label": LABEL}
                    frame = self.construct(g, eligible, concerns, "random", budget, seed, meta)
                    self.score(meta, train, test, frame, spec, ("TSTR", "HYBRID_MINORITY"))
            self.pools.append({"track": "A", "dataset_id": dataset, "budget": budget,
                               "train_positive_n": positives, "train_n": len(train),
                               "train_minority_fraction": fraction,
                               "e2_quota_requested": int(budget*fraction),
                               "canonical_quota_requested": int(budget*.5),
                               "combined_review_pool_n": len(combined),
                               "combined_review_pool_classes": dict(Counter(
                                   g.occurrences[i]["payload"][g.target] for i in combined)),
                               "b2_accepted_complete_pool_n": len(b2),
                               "b2_accepted_complete_pool_classes": dict(Counter(
                                   g.occurrences[i]["payload"][g.target] for i in b2))})
        self.reproduction()

    def reproduction(self) -> None:
        """Compare re-scored canonical comparators with run-v2 instead of assuming equality."""
        canonical = json.loads((self.root/self.config["canonical_protocol"]["run"]/"results.json")
                               .read_text("utf-8"))
        old_constructions = json.loads((self.root/self.config["canonical_protocol"]["run"]
                                        /"constructions.json").read_text("utf-8"))
        for row in [r for r in self.rows if r["track"] == "A-reproduction"]:
            old = next(r for r in canonical if r["track"] == "A" and r["dataset_id"] == row["dataset_id"]
                       and r["method"] == row["method"] and r["classifier"] == row["classifier"]
                       and r["regime"] == row["regime"])
            built = next(c for c in self.constructions if c["track"] == "A-reproduction"
                         and c["dataset_id"] == row["dataset_id"] and c["method"] == row["method"])
            prior = next(c for c in old_constructions if c["track"] == "A"
                         and c["dataset_id"] == row["dataset_id"] and c["method"] == row["method"])
            differences = {m: abs(row[m]-old[m]) for m in METRICS
                           if row.get(m) is not None and old.get(m) is not None}
            self.replay_checks.append({
                "dataset_id": row["dataset_id"], "method": row["method"],
                "classifier": row["classifier"], "regime": row["regime"],
                "status_match": row["status"] == old["status"],
                "selected_ids_match": built["selected_ids"] == prior["selected_ids"],
                "prediction_fingerprint_match": row.get("prediction_fingerprint")
                == old.get("prediction_fingerprint"),
                "max_abs_metric_difference": max(differences.values()) if differences else None,
                "missing_metric_mismatch": any((row.get(m) is None) != (old.get(m) is None)
                                               for m in METRICS)})

    def repaired(self, train: pd.DataFrame, candidates: pd.DataFrame, specification: dict[str, Any],
                 split: dict[str, Any], provenance: dict[str, Any], meta: dict[str, Any]
                 ) -> pd.DataFrame:
        """Apply the frozen bounded-repair policy to a fresh pool, replacing at each ordinal."""
        model = TrainEvidenceModel(specification, tuple(int(i) for i in train.index),
                                   train.to_dict(orient="records"), M2Config())
        payloads, counts = [], Counter()
        for ordinal, payload in enumerate(candidates.to_dict(orient="records")):
            occurrence = {"occurrence_id": "offline:"+digest({"split": split["split_fingerprint"],
                                                              "ordinal": ordinal, "generator": provenance,
                                                              "payload": payload}),
                          "payload": payload, "payload_sha256": digest(payload),
                          "dataset_id": specification["specification"]["dataset_id"],
                          "source_artifact": "offline-generation",
                          "source_artifact_sha256": provenance["payload_fingerprint"],
                          "source_occurrence_ordinal": ordinal}
            structural = model.score(occurrence)[0].model_dump(mode="json")
            proposal = propose_repair(occurrence, specification, structural)
            counts[proposal["eligibility"]] += 1
            for reason in proposal["reasons"]:
                counts["reason:"+reason] += 1
            payloads.append(proposal["repaired_payload"] if proposal["eligibility"] == "REPAIR_ELIGIBLE"
                            else payload)
        self.repairs.append({**meta, "candidates_n": len(payloads), "outcomes": dict(counts)})
        return pd.DataFrame(payloads, columns=candidates.columns)

    def fresh(self, dataset: str, variant: str) -> None:
        """E1 / E1-repair: the run-v2 Track B design with the declared budget rule."""
        spec = self.new_registry.get(dataset)
        loaded = load_dataset(spec, self.new_registry)
        specification = self.ctx.specifications[dataset]
        generator = self.config["E1"]["generators"][dataset]
        for seed in self.config["split_seeds"]:
            print(variant+":", dataset, seed, flush=True)
            split = make_split(loaded, seed).to_dict()
            train, test = outer_frames(loaded.frame, split)
            n_minority = int((train[spec.target_column] == spec.minority_label).sum())
            budget = budget_rule(n_minority)
            meta = {**self.population(variant, loaded, split, train, test, seed),
                    "addendum_label": LABEL}
            if variant == "E1":
                self.external(train, test, spec, meta, seed, budget)
            try:
                candidates, provenance = generate(train, spec, generator, 4*budget, seed)
                if set(provenance["fit_row_ids"]) & set(test.index):
                    raise ValueError("generator fit identities overlap TEST")
                raw_complete = sum(complete_record(r, specification["specification"])
                                   for r in candidates.to_dict(orient="records"))
                if variant == "E1-repair":
                    candidates = self.repaired(train, candidates, specification, split, provenance,
                                               {**meta, "budget": budget})
                    provenance = {**provenance, "bounded_repair": "integer-half-even-max3-v1",
                                  "repaired_payload_fingerprint": digest(
                                      candidates.to_dict(orient="records"))}
                g, pools, concerns, evidence = fresh_geometry(
                    train, candidates, specification, split["split_fingerprint"], provenance)
                write_json(self.output/f"replication/{variant}-{dataset}-{seed}.json", evidence)
                self.pools.append({"track": variant, "dataset_id": dataset, "split_seed": seed,
                                   "train_minority_n": n_minority, "budget": budget,
                                   "generator": generator, "candidates_n": len(candidates),
                                   "generated_structural_complete_n": raw_complete,
                                   "generated_noncompliant_n": 4*budget-raw_complete,
                                   **{f"{k}_pool_n": len(v) for k, v in pools.items()}})
                designs = [("schema/random", pools["schema"], "random"),
                           ("combined/random", pools["combined"], "random")]
                designs += [("combined/"+s, pools["combined"], s) for s in STRATEGIES]
                for method, eligible, strategy in designs:
                    m = {**meta, "method": method, "category": "offline-candidate-curation",
                         "budget": budget, "generator": generator}
                    frame = self.construct(g, eligible, concerns, strategy, budget, seed, m)
                    self.score(m, train, test, frame, spec, ("TSTR", "HYBRID_MINORITY"))
            except (ValueError, TypeError, RuntimeError) as error:
                self.failures.append({**meta, "status": "failed", "method": "offline-curation",
                                      "reason": f"{type(error).__name__}: {error}"})

    def track_b(self) -> None:
        for dataset, reason in self.config["E1"]["unavailable_datasets"].items():
            for variant in ("E1", "E1-repair"):
                self.failures.append({"track": variant, "dataset_id": dataset,
                                      "method": "all", "status": "unavailable", "reason": reason})
        for dataset in self.new_datasets:
            self.fresh(dataset, "E1")
            fields = self.ctx.specifications[dataset]["specification"]["features"]
            if any(f.get("source_declaration", "").startswith("integer") for f in fields):
                self.fresh(dataset, "E1-repair")
            else:
                self.failures.append({"track": "E1-repair", "dataset_id": dataset, "method": "all",
                                      "status": "not_applicable",
                                      "reason": "NO_INTEGER_DECLARED_FEATURES; repair NOT_NEEDED for "
                                      "every candidate, so E1-repair equals E1"})

    def finish(self, runtime: float) -> dict[str, Any]:
        columns = pd.read_csv(self.root/self.config["canonical_protocol"]["run"]/"results.csv",
                              nrows=0).columns
        write_json(self.output/"results.json", self.rows)
        write_json(self.output/"constructions.json", self.constructions)
        write_json(self.output/"populations.json", self.populations)
        write_json(self.output/"unavailable.json", self.failures)
        write_json(self.output/"pools.json", self.pools)
        write_json(self.output/"repairs.json", self.repairs)
        write_json(self.output/"reproduction.json", self.replay_checks)
        pd.DataFrame(self.rows).reindex(columns=columns).to_csv(self.output/"results.csv", index=False)
        hashes = {p.relative_to(self.output).as_posix(): file_hash(p)
                  for p in sorted(self.output.rglob("*")) if p.is_file()}
        code = [self.root/"src/rcqasyn/empirical/addendum.py", self.root/"src/rcqasyn/empirical/study.py",
                self.root/"src/rcqasyn/empirical/generation.py",
                self.root/"src/rcqasyn/empirical/evaluation.py",
                self.root/"scripts/run_exploratory_addendum.py"]
        data: dict[str, Any] = {}
        for dataset in [*self.config["E2"]["datasets"], *self.new_datasets]:
            registry = self.registry if dataset in self.config["E2"]["datasets"] else self.new_registry
            root = self.source if registry is self.registry else self.addendum
            raw = registry.resolve_path(registry.get(dataset))
            data[dataset] = {"raw_path": raw.relative_to(root).as_posix(),
                             "raw_sha256": file_hash(raw),
                             "archive_sha256": file_hash(raw.with_suffix(".zip"))
                             if raw.with_suffix(".zip").exists() else None,
                             "source_manifest": json.loads((root/f"data/manifests/{dataset}/source.json")
                                                           .read_text("utf-8"))}
        for dataset in self.config["E1"]["unavailable_datasets"]:
            archive = self.addendum/f"data/raw/{dataset}/{dataset}.zip"
            data[dataset] = {"status": "unavailable", "archive_size_bytes": archive.stat().st_size
                             if archive.exists() else None,
                             "archive_sha256": file_hash(archive) if archive.exists() else None}
        git = lambda *a: subprocess.check_output(["git", *a], cwd=self.root, text=True).strip()
        manifest = {"label": LABEL, "schema_version": "exploratory-addendum-run-v1",
                    "addendum_protocol_path": CONFIG,
                    "addendum_protocol_sha256": file_hash(self.root/CONFIG),
                    "addendum_protocol_fingerprint": digest(self.config),
                    # Follow the relocation back to the commit that first added the settings.
                    "declaration_commit": git("log", "--follow", "--diff-filter=A", "--format=%H",
                                              "--", CONFIG).splitlines()[-1],
                    "implementation_revision": git("rev-parse", "HEAD"),
                    "implementation_worktree_clean": git("status", "--porcelain", "--", "src",
                                                         "scripts", "configs") == "",
                    "historical_source_revision": FROZEN_SOURCE,
                    "canonical_protocol": self.config["canonical_protocol"],
                    "code_hashes": {p.relative_to(self.root).as_posix(): file_hash(p) for p in code},
                    "data": data, "python": platform.python_version(), "platform": platform.platform(),
                    "dependencies": {p: version(p) for p in ["numpy", "pandas", "scipy", "scikit-learn",
                                                           "imbalanced-learn", "sklearn-compat"]},
                    "runtime_seconds": runtime,
                    "result_content_fingerprint": digest({"rows": self.rows,
                                                          "constructions": self.constructions,
                                                          "populations": self.populations}),
                    "status_counts": dict(Counter(r["status"] for r in self.rows)),
                    "rows_by_track": dict(Counter(r["track"] for r in self.rows)),
                    "reproduction_rows": len(self.replay_checks),
                    "reproduction_all_selected_ids_match": all(r["selected_ids_match"]
                                                               for r in self.replay_checks),
                    "reproduction_max_abs_metric_difference": max(
                        (r["max_abs_metric_difference"] for r in self.replay_checks
                         if r["max_abs_metric_difference"] is not None), default=None),
                    "output_hashes": hashes, "human_annotation_active": False,
                    "test_used_for_selection": False, "paid_provider_calls": False,
                    "interpretation": "Exploratory addendum declared after the main study; "
                    "overlapping repeated holdouts; offline generator curation, not LLM replication"}
        write_json(self.output/"manifest.json", manifest)
        return manifest


def run(root: Path, source: Path, output: Path) -> dict[str, Any]:
    start = time.perf_counter()
    study = Addendum(root, source, output)
    study.track_a()
    study.track_b()
    return study.finish(time.perf_counter()-start)

