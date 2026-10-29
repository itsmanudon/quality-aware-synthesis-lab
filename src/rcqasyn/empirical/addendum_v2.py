"""Exploratory addendum v2: published-method benchmark inside the frozen pipeline.

Declared in addendum/v2/addendum-v2.json before scoring. Reuses the frozen Study scoring,
construction, population and external-comparator methods unchanged and adds only published
imbalanced-learn oversamplers and two curators re-implemented from published principles
(not the authors' code). Never merged into canonical tables.
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

import numpy as np
import pandas as pd
from imblearn.combine import SMOTEENN, SMOTETomek
from imblearn.over_sampling import ADASYN, SMOTE, SMOTENC, BorderlineSMOTE
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from rcqasyn.datasets.loader import load_dataset
from rcqasyn.datasets.registry import DatasetRegistry
from rcqasyn.datasets.split import make_split
from rcqasyn.phase2.common import digest
from rcqasyn.phase2.specifications import dataset_specification
from rcqasyn.phase5.contracts import STRATEGIES
from rcqasyn.phase5.geometry import Geometry, metrics
from rcqasyn.phase5.workflow import load_context
from rcqasyn.phase6.utility import outer_frames

from .addendum import budget_rule
from .evaluation import METRICS
from .generation import fresh_geometry, generate
from .study import Study, file_hash, write_json

FROZEN_SOURCE = "244a9bfd490a03a35c4be5cb3b83354e425795fc"
ADDENDUM = "addendum/v2"
CONFIG = ADDENDUM+"/addendum-v2.json"
V1 = "addendum/v1"
LABEL = "EXPLORATORY_ADDENDUM_V2_DECLARED_AFTER_MAIN_STUDY"
OVERSAMPLERS = ("SMOTE-ENN", "SMOTE-Tomek", "Borderline-SMOTE", "ADASYN")
REIMPLEMENTED = ("reimpl/cllm-style", "reimpl/discriminator-realism")


class Unavailable(Exception):
    """A declared, non-error unavailability (for example no nominal path)."""


def encoder(train: pd.DataFrame, spec: Any) -> Any:
    features = list(spec.feature_columns)
    nominal = list(spec.categorical_columns)
    transform = ColumnTransformer([("nominal", OneHotEncoder(handle_unknown="ignore",
                                                            sparse_output=False), nominal)],
                                  remainder="passthrough") if nominal else None
    if transform is not None:
        transform.fit(train[features])
    return lambda frame: (transform.transform(frame[features]) if transform is not None
                          else frame[features].to_numpy(dtype=float))


def resample(train: pd.DataFrame, spec: Any, method: str, setting: str,
             budget: int) -> tuple[pd.DataFrame, dict[str, Any]]:
    positive, target = spec.minority_label, spec.target_column
    nominal, numerical = list(spec.categorical_columns), list(spec.numerical_columns)
    if nominal and method in ("Borderline-SMOTE", "ADASYN"):
        raise Unavailable("NO_NOMINAL_PATH_IN_IMBALANCED_LEARN")
    counts = Counter(train[target])
    n = counts[positive]
    k = min(5, n-1)
    x: Any = train[list(spec.feature_columns)].copy()
    if x.isna().any().any():
        raise Unavailable("MISSING_SOURCE_FIELDS_NOT_IMPUTED")
    scaler = StandardScaler().fit(x[numerical])
    x[numerical] = np.asarray(scaler.transform(x[numerical]), dtype=float)
    strategy: Any = "auto" if setting == "full" else {positive: n+budget}
    smote: Any = (SMOTENC(categorical_features=nominal, sampling_strategy=strategy, k_neighbors=k,
                          random_state=42) if nominal
                  else SMOTE(sampling_strategy=strategy, k_neighbors=k, random_state=42))
    sampler: Any = {"SMOTE-ENN": lambda: SMOTEENN(smote=smote, random_state=42),
                    "SMOTE-Tomek": lambda: SMOTETomek(smote=smote, random_state=42),
                    "Borderline-SMOTE": lambda: BorderlineSMOTE(
                        kind="borderline-1", sampling_strategy=strategy, k_neighbors=k, random_state=42),
                    "ADASYN": lambda: ADASYN(sampling_strategy=strategy, n_neighbors=k,
                                             random_state=42)}[method]()
    xr, yr = sampler.fit_resample(x, train[target])
    xr = pd.DataFrame(xr, columns=x.columns).reset_index(drop=True)
    # Inverse transform restores source units; values are never rounded.
    xr[numerical] = scaler.inverse_transform(xr[numerical])
    xr[target] = np.asarray(yr)
    final = Counter(xr[target])
    return xr, {"k_neighbors": k, "sampling_strategy": strategy, "train_class_counts": dict(counts),
                "final_class_counts": dict(final),
                "generated_minority_net": final[positive]-n,
                "removed_majority": sum(v for c, v in counts.items() if c != positive)
                - sum(v for c, v in final.items() if c != positive),
                "output_fingerprint": digest(xr.to_dict(orient="split"))}


def cllm_style(train: pd.DataFrame, spec: Any, g: Geometry, eligible: list[int],
               budget: int) -> tuple[list[int], dict[str, Any]]:
    """Learning-dynamics filter after Seedat et al. (2024); a re-implementation of the principle."""
    encode = encoder(train, spec)
    model: Any = GradientBoostingClassifier(n_estimators=100, random_state=42)
    model.fit(encode(train), train[spec.target_column].astype(str))
    column = list(model.classes_).index(str(spec.minority_label))
    pool = pd.DataFrame([g.occurrences[i]["payload"] for i in eligible])
    stages = list(model.staged_predict_proba(encode(pool)))
    p = np.array([stages[j-1][:, column] for j in range(10, 101, 10)])
    confidence, aleatoric = p.mean(axis=0), (p*(1-p)).mean(axis=0)
    median = float(np.median(aleatoric)) if len(eligible) else None
    order = lambda members: sorted(members, key=lambda m: (
        -confidence[m], g.occurrences[eligible[m]]["source_occurrence_ordinal"]))
    kept = order([m for m in range(len(eligible)) if median is not None and aleatoric[m] <= median])
    rest = order([m for m in range(len(eligible)) if m not in set(kept)])
    chosen = kept[:budget]
    fill = rest[:max(0, budget-len(chosen))]
    return [eligible[m] for m in chosen+fill], {
        "aleatoric_median": median, "kept_n": len(kept), "filled_n": len(fill),
        "scores_fingerprint": digest({"confidence": confidence.tolist(),
                                      "aleatoric": aleatoric.tolist()})}


def discriminator_realism(train: pd.DataFrame, spec: Any, g: Geometry, eligible: list[int],
                          budget: int) -> tuple[list[int], dict[str, Any]]:
    """Realism ranking after RUBRIC / Alaa et al.; a re-implementation of the principle."""
    encode = encoder(train, spec)
    minority = train.loc[train[spec.target_column] == spec.minority_label]
    pool = pd.DataFrame([g.occurrences[i]["payload"] for i in eligible])
    x = np.vstack([np.asarray(encode(minority)), np.asarray(encode(pool))])
    y = np.r_[np.ones(len(minority), dtype=int), np.zeros(len(pool), dtype=int)]
    probability = np.asarray(cross_val_predict(
        RandomForestClassifier(n_estimators=200, random_state=42), x, y,
        cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=42), method="predict_proba"))[:, 1]
    realism = probability[len(minority):]
    ranked = sorted(range(len(eligible)), key=lambda m: (
        -realism[m], g.occurrences[eligible[m]]["source_occurrence_ordinal"]))
    return [eligible[m] for m in ranked[:budget]], {
        "train_minority_n": len(minority), "scores_fingerprint": digest(realism.tolist())}


class Benchmark(Study):
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
        self.pools: list[dict[str, Any]] = []
        self.registry = DatasetRegistry(project_root=source)
        self.v1 = root/V1
        self.new_registry = DatasetRegistry(project_root=self.v1)
        self.ctx = load_context(root, source)
        datasets = self.config["datasets"]
        self.canonical, self.new = datasets["canonical"]["ids"], datasets["new"]["ids"]
        for dataset in self.new:
            self.ctx.specifications[dataset] = dataset_specification(self.v1, dataset)
        output.mkdir(parents=True)

    def recorded_pool(self, dataset: str, seed: int) -> str | None:
        path = (self.root/self.config["builds_on"]["canonical_run"]/f"replication/{dataset}-{seed}.json"
                if dataset in self.canonical else self.v1/f"report/replication/E1-{dataset}-{seed}.json")
        if not path.exists():
            return None
        return json.loads(path.read_text("utf-8"))["generation"]["payload_fingerprint"]

    def reimplemented(self, name: str, train: pd.DataFrame, spec: Any, g: Geometry,
                      eligible: list[int], budget: int, meta: dict[str, Any]) -> pd.DataFrame:
        curator = cllm_style if name == "reimpl/cllm-style" else discriminator_realism
        selected, details = curator(train, spec, g, eligible, budget) if len(eligible) >= budget else (
            list(eligible), {"reason": "ELIGIBLE_POOL_SMALLER_THAN_BUDGET"})
        records = [g.occurrences[i] for i in selected]
        complete = len(selected) == budget
        self.constructions.append({**meta, "strategy": name, "seed": 42, "eligible_n": len(eligible),
                                   "budget": budget, "budget_achieved": len(selected),
                                   "status": "ok" if complete else "unavailable",
                                   "reason": None if complete else "MATCHED_BUDGET_SHORTFALL",
                                   "selected_ids": [r["occurrence_id"] for r in records],
                                   "selected_payload_fingerprint": digest([r["payload"] for r in records]),
                                   "curator_details": details,
                                   "implementation": "re-implementation of the principle, not the authors' code",
                                   **metrics(g, selected, eligible, .05, .01)})
        frame = pd.DataFrame([r["payload"] for r in records],
                             columns=pd.Index([f["name"] for f in g.fields]+[g.target]))
        return frame if complete else frame.iloc[:0]

    def dataset(self, dataset: str) -> None:
        canonical = dataset in self.canonical
        registry = self.registry if canonical else self.new_registry
        spec = registry.get(dataset)
        loaded = load_dataset(spec, registry)
        specification = self.ctx.specifications[dataset]
        kind = "canonical" if canonical else "new"
        generator = self.config["datasets"][kind]["pool_generators"][dataset]
        for seed in self.config["split_seeds"]:
            print("V2:", dataset, seed, flush=True)
            split = make_split(loaded, seed).to_dict()
            train, test = outer_frames(loaded.frame, split)
            n_minority = int((train[spec.target_column] == spec.minority_label).sum())
            budget = (self.config["datasets"]["canonical"]["budgets"][dataset] if canonical
                      else budget_rule(n_minority))
            meta = {**self.population("V2", loaded, split, train, test, seed), "addendum_label": LABEL}
            self.external(train, test, spec, meta, seed, budget)
            for method in OVERSAMPLERS:
                for setting in ("full", "+b"):
                    m = {**meta, "method": f"{method}/{setting}", "category": "published-oversampler",
                         "budget": budget, "training_population": "OVERSAMPLER_OUTPUT_FROM_REAL_TRAIN"}
                    try:
                        frame, details = resample(train, spec, method, setting, budget)
                    except Unavailable as reason:
                        self.failures.append({**m, "status": "unavailable", "reason": str(reason)})
                        continue
                    except (ValueError, TypeError, RuntimeError) as error:
                        self.failures.append({**m, "status": "unavailable",
                                              "reason": f"LIBRARY_ERROR {type(error).__name__}: {error}"})
                        continue
                    self.score({**m, "resampling": details}, frame, test, frame.iloc[:0], spec, ("TRTR",))
            try:
                candidates, provenance = generate(train, spec, generator, 4*budget, seed)
                if set(provenance["fit_row_ids"]) & set(test.index):
                    raise ValueError("generator fit identities overlap TEST")
                recorded = self.recorded_pool(dataset, seed)
                g, pools, concerns, evidence = fresh_geometry(
                    train, candidates, specification, split["split_fingerprint"], provenance)
                write_json(self.output/f"replication/V2-{dataset}-{seed}.json", evidence)
                self.pools.append({"dataset_id": dataset, "split_seed": seed, "budget": budget,
                                   "train_minority_n": n_minority, "generator": generator,
                                   "candidates_n": len(candidates),
                                   "payload_fingerprint": provenance["payload_fingerprint"],
                                   "recorded_payload_fingerprint": recorded,
                                   "pool_identity_match": recorded == provenance["payload_fingerprint"],
                                   **{f"{k}_pool_n": len(v) for k, v in pools.items()}})
                designs = [("schema/random", pools["schema"], "random"),
                           ("combined/random", pools["combined"], "random")]
                designs += [("combined/"+s, pools["combined"], s) for s in STRATEGIES]
                for method, eligible, strategy in designs:
                    m = {**meta, "method": method, "category": "offline-candidate-curation",
                         "budget": budget, "generator": generator}
                    frame = self.construct(g, eligible, concerns, strategy, budget, seed, m)
                    self.score(m, train, test, frame, spec, ("TSTR", "HYBRID_MINORITY"))
                for name in REIMPLEMENTED:
                    m = {**meta, "method": name, "category": "reimplemented-curation",
                         "budget": budget, "generator": generator}
                    frame = self.reimplemented(name, train, spec, g, pools["schema"], budget, m)
                    self.score(m, train, test, frame, spec, ("TSTR", "HYBRID_MINORITY"))
            except (ValueError, TypeError, RuntimeError) as error:
                self.failures.append({**meta, "status": "failed", "method": "offline-curation",
                                      "reason": f"{type(error).__name__}: {error}"})

    def reproduction(self) -> list[dict[str, Any]]:
        """Compare re-scored existing methods with addendum v1 and run-v2 rather than assume."""
        previous = {"addendum-v1": [r for r in json.loads((self.v1/"report/results.json").read_text())
                                    if r["track"] == "E1"],
                    "run-v2": [r for r in json.loads((self.root/self.config["builds_on"]["canonical_run"]
                                                       /"results.json").read_text()) if r["track"] == "B"]}
        checks = []
        for source, rows in previous.items():
            index = {(r["dataset_id"], r["split_seed"], r["method"], r["classifier"], r["regime"]): r
                     for r in rows}
            for row in self.rows:
                old = index.get((row["dataset_id"], row["split_seed"], row["method"],
                                 row["classifier"], row["regime"]))
                if old is None:
                    continue
                differences = [abs(row[m]-old[m]) for m in METRICS
                               if row.get(m) is not None and old.get(m) is not None]
                checks.append({"source": source, "dataset_id": row["dataset_id"],
                               "split_seed": row["split_seed"], "method": row["method"],
                               "classifier": row["classifier"], "regime": row["regime"],
                               "status_match": row["status"] == old["status"],
                               "prediction_fingerprint_match": row.get("prediction_fingerprint")
                               == old.get("prediction_fingerprint"),
                               "max_abs_metric_difference": max(differences) if differences else None})
        return checks

    def finish(self, runtime: float) -> dict[str, Any]:
        checks = self.reproduction()
        columns = pd.read_csv(self.root/self.config["builds_on"]["canonical_run"]/"results.csv",
                              nrows=0).columns
        for name, value in [("results", self.rows), ("constructions", self.constructions),
                            ("populations", self.populations), ("unavailable", self.failures),
                            ("pools", self.pools), ("reproduction", checks)]:
            write_json(self.output/f"{name}.json", value)
        pd.DataFrame(self.rows).reindex(columns=columns).to_csv(self.output/"results.csv", index=False)
        git = lambda *a: subprocess.check_output(["git", *a], cwd=self.root, text=True).strip()
        summary = {}
        for source in ("addendum-v1", "run-v2"):
            mine = [c for c in checks if c["source"] == source]
            summary[source] = {"rows_compared": len(mine),
                               "status_all_match": all(c["status_match"] for c in mine),
                               "prediction_fingerprints_matching": sum(c["prediction_fingerprint_match"]
                                                                       for c in mine),
                               "max_abs_metric_difference": max(
                                   (c["max_abs_metric_difference"] for c in mine
                                    if c["max_abs_metric_difference"] is not None), default=None)}
        manifest = {"label": LABEL, "schema_version": "exploratory-addendum-v2-run",
                    "settings_path": CONFIG, "settings_sha256": file_hash(self.root/CONFIG),
                    "settings_fingerprint": digest(self.config),
                    "declaration_commit": git("log", "--diff-filter=A", "--format=%H", "--",
                                              CONFIG).splitlines()[-1],
                    "implementation_revision": git("rev-parse", "HEAD"),
                    "implementation_worktree_clean": git("status", "--porcelain", "--", "src",
                                                         "scripts", ADDENDUM) == "",
                    "historical_source_revision": FROZEN_SOURCE,
                    "code_hashes": {p: file_hash(self.root/p) for p in [
                        "src/rcqasyn/empirical/addendum_v2.py", "src/rcqasyn/empirical/addendum.py",
                        "src/rcqasyn/empirical/study.py", "src/rcqasyn/empirical/generation.py",
                        "src/rcqasyn/empirical/evaluation.py", "scripts/run_exploratory_addendum_v2.py"]},
                    "data": {d: {"raw_sha256": file_hash((self.registry if d in self.canonical
                                                          else self.new_registry).resolve_path(
                                    (self.registry if d in self.canonical else self.new_registry).get(d)))}
                             for d in [*self.canonical, *self.new]},
                    "python": platform.python_version(), "platform": platform.platform(),
                    "dependencies": {p: version(p) for p in ["numpy", "pandas", "scipy", "scikit-learn",
                                                           "imbalanced-learn", "sklearn-compat"]},
                    "runtime_seconds": runtime,
                    "result_content_fingerprint": digest({"rows": self.rows,
                                                          "constructions": self.constructions,
                                                          "populations": self.populations}),
                    "status_counts": dict(Counter(r["status"] for r in self.rows)),
                    "rows_by_category": dict(Counter(r["category"] for r in self.rows)),
                    "pool_identity_all_match": all(p["pool_identity_match"] for p in self.pools),
                    "reproduction": summary,
                    "output_hashes": {p.relative_to(self.output).as_posix(): file_hash(p)
                                      for p in sorted(self.output.rglob("*")) if p.is_file()},
                    "human_annotation_active": False, "test_used_for_selection": False,
                    "paid_provider_calls": False,
                    "interpretation": "Exploratory addendum v2 declared after the main study; "
                    "overlapping repeated holdouts; re-implemented curators are not the authors' code"}
        write_json(self.output/"manifest.json", manifest)
        return manifest


def run(root: Path, source: Path, output: Path) -> dict[str, Any]:
    start = time.perf_counter()
    study = Benchmark(root, source, output)
    for dataset in [*study.canonical, *study.new]:
        study.dataset(dataset)
    for dataset, reason in study.config["datasets"]["unavailable"].items():
        study.failures.append({"track": "V2", "dataset_id": dataset, "method": "all",
                               "status": "unavailable", "reason": reason})
    return study.finish(time.perf_counter()-start)
