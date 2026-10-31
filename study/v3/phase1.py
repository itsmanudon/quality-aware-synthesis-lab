"""Phase 1 diagnosis on the 8 dev datasets, scored on VALIDATION only (never TEST).

Step 1 (PLAN.md Phase 1): carve a stratified 20% validation split from each outer TRAIN,
then re-run the existing Empirical v2 / addendum v1 offline curation design on the
remaining inner TRAIN and score it on validation:

    outer split (rcqasyn make_split, seeds 13/29/43/61/79)
      -> TRAIN = inner TRAIN + VALIDATION (stratified 20%, SHA-256 ordered, like make_split)
      -> pool = SMOTE/SMOTENC(inner TRAIN), 4 x budget (rcqasyn.empirical.generation.generate)
      -> evidence + q=0.90 admission (fresh_geometry, unchanged)
      -> curators: schema/random, combined/random (5 selection seeds), 4 declared strategies
      -> HYBRID_MINORITY training (inner TRAIN + selected) scored on VALIDATION

Every method reuses the frozen implementation by import; nothing here changes a curator,
B1/B2/B3, the evidence model or the evaluator. TEST indices are computed (to keep the outer
split identical to the declared design) but TEST rows are never passed to any function.

Runs are resumable: each (dataset, split seed, variant) unit writes one JSON file and is
skipped if that file exists. ``progress.json`` in the run directory records the state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from rcqasyn.datasets.loader import load_dataset
from rcqasyn.datasets.registry import DatasetRegistry
from rcqasyn.datasets.split import make_split
from rcqasyn.empirical.addendum import budget_rule
from rcqasyn.empirical.evaluation import evaluate
from rcqasyn.empirical.generation import fresh_geometry, generate
from rcqasyn.phase2.common import digest
from rcqasyn.phase2.specifications import dataset_specification
from rcqasyn.phase5.contracts import STRATEGIES, SelectionConfig
from rcqasyn.phase5.geometry import complete_record, metrics
from rcqasyn.phase5.selection import select
from rcqasyn.phase6.utility import outer_frames
from rcqasyn.utils.seeds import derive_seed

from .devroot import DEV, DEVROOT

SPLIT_SEEDS = (13, 29, 43, 61, 79)
SELECTION_SEEDS = (13, 29, 43, 61, 79)
VALIDATION_FRACTION = 0.2
CLASSIFIERS = ("logistic_regression", "random_forest")
SCORED = ("f1", "average_precision", "mcc", "balanced_accuracy", "auroc",
          "tp", "fp", "tn", "fn", "test_positive_n", "test_negative_n", "status", "reason")
CONSTRUCTION_KEYS = ("selected_n", "exact_duplicate_rate", "near_duplicate_rate",
                     "unique_train_feature_coverage", "train_row_coverage")


def carve_validation(train: pd.DataFrame, target: str, dataset: str,
                     split_seed: int) -> tuple[list[int], list[int]]:
    """Stratified 20% of TRAIN, ordered by SHA-256 exactly as make_split orders TEST."""
    seed = derive_seed(split_seed, f"study-v3-validation:{dataset}")
    labels = train[target].astype("string").fillna("<MISSING>")
    inner: list[int] = []
    validation: list[int] = []
    for label in sorted(labels.unique().tolist()):
        group = sorted((int(i) for i in labels.index[labels == label]),
                       key=lambda i: hashlib.sha256(f"{seed}:{label}:{i}".encode()).hexdigest())
        n_val = max(1, round(len(group) * VALIDATION_FRACTION)) if len(group) > 1 else 0
        n_val = min(n_val, len(group) - 1)
        validation.extend(group[:n_val])
        inner.extend(group[n_val:])
    return sorted(inner), sorted(validation)


def construct(g: Any, eligible: list[int], concerns: dict[int, float], strategy: str,
              budget: int, seed: int, quota: float = .5) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Same construction as rcqasyn.empirical.study.Study.construct, without its bookkeeping."""
    if strategy == "random":
        selected = np.random.default_rng(seed).permutation(eligible)[:budget].tolist()
        measured = metrics(g, selected, eligible, .05, .01)
    else:
        recipe = select(g, eligible, concerns, SelectionConfig(
            strategy=strategy, budget=budget, minority_quota_fraction=quota))  # type: ignore[arg-type]
        selected, measured = recipe["selected_indices"], recipe["metrics"]
    records = [g.occurrences[i] for i in selected]
    frame = pd.DataFrame([r["payload"] for r in records],
                         columns=pd.Index([f["name"] for f in g.fields] + [g.target]))
    info = {k: measured.get(k) for k in CONSTRUCTION_KEYS}
    info.update(eligible_n=len(eligible), budget_achieved=len(selected),
                selected_ids_fingerprint=digest([r["occurrence_id"] for r in records]))
    return frame, info


def score(train: pd.DataFrame, validation: pd.DataFrame, spec: Any, classifier: str,
          *, balanced: bool = False) -> dict[str, Any]:
    try:
        result = evaluate(train, validation, spec, classifier, balanced=balanced)
    except (ValueError, TypeError, RuntimeError) as error:
        result = {"status": "failed", "reason": f"{type(error).__name__}: {error}"}
    return {k: result.get(k) for k in SCORED}


def hybrid(inner: pd.DataFrame, synthetic: pd.DataFrame, spec: Any) -> pd.DataFrame:
    minority = synthetic.loc[synthetic[spec.target_column] == spec.minority_label]
    return pd.concat([inner, minority], ignore_index=True)


def run_unit(dataset: str, split_seed: int, *, budget_scale: float = 1.0) -> dict[str, Any]:
    registry = DatasetRegistry(project_root=DEVROOT)
    spec = registry.get(dataset)
    loaded = load_dataset(spec, registry)
    specification = dataset_specification(DEVROOT, dataset)
    split = make_split(loaded, split_seed).to_dict()
    train, _test_not_used = outer_frames(loaded.frame, split)
    del _test_not_used  # TEST is never scored in Phase 1
    inner_ids, val_ids = carve_validation(train, spec.target_column, dataset, split_seed)
    inner, validation = train.loc[inner_ids], train.loc[val_ids]
    target, positive = spec.target_column, spec.minority_label
    n_min = int((inner[target] == positive).sum())
    budget = max(1, round(budget_rule(n_min) * budget_scale))
    method = "SMOTENC" if spec.categorical_columns else "SMOTE"
    unit: dict[str, Any] = {
        "dataset_id": dataset, "split_seed": split_seed, "budget_scale": budget_scale,
        "budget": budget, "generator": method,
        "outer_split_fingerprint": split["split_fingerprint"],
        "inner_n": len(inner), "inner_minority_n": n_min,
        "validation_n": len(validation),
        "validation_minority_n": int((validation[target] == positive).sum()),
        "validation_ids_fingerprint": digest(val_ids), "test_used": False, "rows": []}
    rows: list[dict[str, Any]] = unit["rows"]

    def add(method_name: str, frame: pd.DataFrame, classifiers: tuple[str, ...] = CLASSIFIERS,
            *, balanced: bool = False, **extra: Any) -> None:
        for classifier in classifiers:
            rows.append({"method": method_name, "classifier": classifier, **extra,
                         **score(frame, validation, spec, classifier, balanced=balanced)})

    add("REAL_INNER_TRAIN", inner)
    add("CLASS_WEIGHTED_LR", inner, ("logistic_regression",), balanced=True)
    for oversampler in ("RandomOverSampler", method):
        try:
            generated, _ = generate(inner, spec, oversampler, budget, split_seed)
            add(oversampler + "+b", hybrid(inner, generated, spec))
        except (ValueError, TypeError, RuntimeError) as error:
            rows.append({"method": oversampler + "+b", "status": "failed",
                         "reason": f"{type(error).__name__}: {error}"})
    try:
        candidates, provenance = generate(inner, spec, method, 4 * budget, split_seed)
        if set(provenance["fit_row_ids"]) & set(val_ids):
            raise ValueError("generator fit identities overlap VALIDATION")
        pool_fp = digest({"outer": split["split_fingerprint"], "validation": val_ids})
        g, pools, concerns, _evidence = fresh_geometry(inner, candidates, specification,
                                                       pool_fp, provenance)
        spec_dict = specification["specification"]
        unit["pool"] = {"candidates_n": len(candidates),
                        "structurally_complete_n": sum(complete_record(r, spec_dict) for r in
                                                       candidates.to_dict(orient="records")),
                        **{f"{k}_n": len(v) for k, v in pools.items()}}
        designs: list[tuple[str, list[int], str, int]] = [
            (f"{name}/random/s{s}", pools[name], "random", s)
            for name in ("schema", "combined") for s in SELECTION_SEEDS]
        designs += [(f"combined/{s}", pools["combined"], s, 42) for s in STRATEGIES]
        for name, eligible, strategy, seed in designs:
            frame, info = construct(g, eligible, concerns, strategy, budget, seed)
            if info["budget_achieved"] < budget:
                rows.append({"method": name, "status": "unavailable",
                             "reason": "MATCHED_BUDGET_SHORTFALL", **info})
                continue
            add(name, hybrid(inner, frame, spec), selection_seed=seed, **info)
    except (ValueError, TypeError, RuntimeError) as error:
        unit["pool_failure"] = f"{type(error).__name__}: {error}"
    return unit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True, help="run directory (resumable)")
    parser.add_argument("--datasets", nargs="+", default=list(DEV))
    parser.add_argument("--seeds", type=int, nargs="+", default=list(SPLIT_SEEDS))
    parser.add_argument("--budget-scales", type=float, nargs="+", default=[1.0])
    args = parser.parse_args(argv)
    units_dir = args.run / "units"
    units_dir.mkdir(parents=True, exist_ok=True)
    plan = [(d, s, b) for b in args.budget_scales for d in args.datasets for s in args.seeds]
    for done, (dataset, seed, scale) in enumerate(plan, start=1):
        path = units_dir / f"{dataset}__s{seed}__b{scale:g}.json"
        if not path.exists():
            start = time.perf_counter()
            unit = run_unit(dataset, seed, budget_scale=scale)
            unit["runtime_seconds"] = time.perf_counter() - start
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(unit, sort_keys=True, indent=1, allow_nan=False,
                                      default=str), encoding="utf-8")
            tmp.replace(path)
            print(f"{dataset} s{seed} b{scale:g}: {len(unit['rows'])} rows, "
                  f"{unit['runtime_seconds']:.1f}s", flush=True)
        (args.run / "progress.json").write_text(json.dumps(
            {"planned_units": len(plan), "finished_units": done,
             "last": [dataset, seed, scale],
             "status_counts": dict(Counter(
                 p.suffix for p in units_dir.iterdir()))}, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
