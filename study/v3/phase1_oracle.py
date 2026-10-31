"""Phase 1 step 4: how much could selection from the admitted pool gain? (VALIDATION only).

For every dev (dataset, split) unit the SMOTE/SMOTENC pool and q=0.90 admission are rebuilt
exactly as in ``phase1.py``. K random budget-sized subsets of the combined admitted pool are
drawn (seeds derived with ``derive_seed``), and each HYBRID_MINORITY model is scored on
VALIDATION. Two upper-bound readings are recorded per classifier:

- in-sample oracle: max over K of validation F1, minus the mean over K. Optimistic by
  construction (chosen and scored on the same rows).
- honest oracle: validation is split into two stratified halves A/B (SHA-256 ordered); the
  subset with the best F1 on A is scored on B, minus the mean B score over K.

TEST is never used. Nothing here is a method; it only bounds what any selection rule
applied to this pool could reach on these validation rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
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
from rcqasyn.phase6.utility import outer_frames
from rcqasyn.utils.seeds import derive_seed

from .devroot import DEV, DEVROOT
from .phase1 import CLASSIFIERS, SPLIT_SEEDS, carve_validation, hybrid

K = 100


def halves(validation: pd.DataFrame, target: str, dataset: str, seed: int) -> tuple[Any, Any]:
    """Two stratified halves of VALIDATION, each class ordered by SHA-256 (A gets floor)."""
    derived = derive_seed(seed, f"study-v3-oracle-halves:{dataset}")
    ids = validation.index.to_numpy(dtype=np.int64)
    labels = validation[target].astype(str).to_numpy(dtype=object)
    half_a: list[int] = []
    half_b: list[int] = []
    for label in sorted(set(labels.tolist())):
        group = sorted((int(i) for i, v in zip(ids, labels, strict=True) if v == label),
                       key=lambda i: hashlib.sha256(f"{derived}:{label}:{i}".encode()).hexdigest())
        cut = len(group) // 2
        half_a += group[:cut]
        half_b += group[cut:]
    return validation.loc[sorted(half_a)], validation.loc[sorted(half_b)]


def run_unit(dataset: str, split_seed: int, k: int = K) -> dict[str, Any]:
    registry = DatasetRegistry(project_root=DEVROOT)
    spec = registry.get(dataset)
    loaded = load_dataset(spec, registry)
    specification = dataset_specification(DEVROOT, dataset)
    split = make_split(loaded, split_seed).to_dict()
    train, _test_not_used = outer_frames(loaded.frame, split)
    del _test_not_used
    inner_ids, val_ids = carve_validation(train, spec.target_column, dataset, split_seed)
    inner, validation = train.loc[inner_ids], train.loc[val_ids]
    val_a, val_b = halves(validation, spec.target_column, dataset, split_seed)
    budget = budget_rule(int((inner[spec.target_column] == spec.minority_label).sum()))
    method = "SMOTENC" if spec.categorical_columns else "SMOTE"
    unit: dict[str, Any] = {"dataset_id": dataset, "split_seed": split_seed, "budget": budget,
                            "k": k, "test_used": False,
                            "half_minority": [int((h[spec.target_column] == spec.minority_label)
                                                  .sum()) for h in (val_a, val_b)]}
    candidates, provenance = generate(inner, spec, method, 4 * budget, split_seed)
    g, pools, _concerns, _ = fresh_geometry(
        inner, candidates, specification,
        digest({"outer": split["split_fingerprint"], "validation": val_ids}), provenance)
    eligible = pools["combined"]
    unit["eligible_n"] = len(eligible)
    if len(eligible) < budget:
        unit["status"] = "unavailable"
        unit["reason"] = "MATCHED_BUDGET_SHORTFALL"
        return unit
    names = [f["name"] for f in g.fields] + [g.target]
    scores: dict[str, dict[str, list[float | None]]] = {
        c: {"full": [], "a": [], "b": []} for c in CLASSIFIERS}
    for draw in range(k):
        rng = np.random.default_rng(derive_seed(split_seed, "study-v3-oracle", dataset, draw))
        chosen = rng.permutation(eligible)[:budget].tolist()
        frame = pd.DataFrame([g.occurrences[i]["payload"] for i in chosen],
                             columns=pd.Index(names))
        training = hybrid(inner, frame, spec)
        for classifier in CLASSIFIERS:
            for key, rows in (("full", validation), ("a", val_a), ("b", val_b)):
                result = evaluate(training, rows, spec, classifier)
                scores[classifier][key].append(result.get("f1"))
    summary = {}
    for classifier, by in scores.items():
        full = np.array(by["full"], dtype=float)
        a = np.array(by["a"], dtype=float)
        b = np.array(by["b"], dtype=float)
        best_a = int(np.nanargmax(a))
        summary[classifier] = {
            "mean_full": float(np.nanmean(full)), "max_full": float(np.nanmax(full)),
            "in_sample_gain": float(np.nanmax(full) - np.nanmean(full)),
            "mean_b": float(np.nanmean(b)), "b_of_best_a": float(b[best_a]),
            "honest_gain": float(b[best_a] - np.nanmean(b)),
            "sd_full": float(np.nanstd(full, ddof=1))}
    unit.update(status="ok", summary=summary, scores=scores)
    return unit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--datasets", nargs="+", default=list(DEV))
    parser.add_argument("--seeds", type=int, nargs="+", default=list(SPLIT_SEEDS))
    parser.add_argument("--k", type=int, default=K)
    args = parser.parse_args(argv)
    units = args.run / "units"
    units.mkdir(parents=True, exist_ok=True)
    plan = [(d, s) for d in args.datasets for s in args.seeds]
    for done, (dataset, seed) in enumerate(plan, start=1):
        path = units / f"{dataset}__s{seed}.json"
        if not path.exists():
            start = time.perf_counter()
            unit = run_unit(dataset, seed, args.k)
            unit["runtime_seconds"] = time.perf_counter() - start
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(unit, sort_keys=True, allow_nan=False), encoding="utf-8")
            tmp.replace(path)
            print(dataset, seed, unit["status"], f"{unit['runtime_seconds']:.1f}s", flush=True)
        (args.run / "progress.json").write_text(json.dumps({"planned": len(plan),
                                                            "finished": done}), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
