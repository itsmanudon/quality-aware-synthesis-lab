"""Phase 1: U2/UGO/SMOTE pools through the RC-QASyn quality gate, on dev validation only.

Two subcommands, either side of ``u2_pools.py`` (which runs in the isolated U2 venv):

``jobs``  writes one job per (dev dataset, split seed): the inner TRAIN and VALIDATION row
          ids from the same carve as ``phase1.py``, the verified raw path and SHA-256, and
          the pool size 4 x budget_rule. TEST ids are not written.
``gate``  reads the exported pools and, per pool, records (a) structural failures
          (``complete_record``), (b) bounded-repair eligibility (``propose_repair``, the
          frozen integer-half-even-max3-v1 policy), (c) exact duplicates within the pool and
          exact copies of inner TRAIN feature rows (copying diagnostics, not privacy),
          (d) q=0.90 admission counts (``fresh_geometry``). It then runs the step-1 curators
          on each pool and scores HYBRID_MINORITY on VALIDATION, exactly as ``phase1.py``.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from rcqasyn.datasets.loader import load_dataset
from rcqasyn.datasets.registry import DatasetRegistry
from rcqasyn.datasets.split import make_split
from rcqasyn.empirical.addendum import budget_rule
from rcqasyn.empirical.generation import fresh_geometry
from rcqasyn.phase2.common import digest
from rcqasyn.phase2.specifications import dataset_specification
from rcqasyn.phase3.contracts import M2Config
from rcqasyn.phase3.validators import TrainEvidenceModel
from rcqasyn.phase5.contracts import STRATEGIES
from rcqasyn.phase5.geometry import complete_record
from rcqasyn.phase6.repair import propose_repair
from rcqasyn.phase6.utility import outer_frames

from .devroot import DEV, DEVROOT, sha256_file
from .phase1 import (
    CLASSIFIERS,
    SELECTION_SEEDS,
    SPLIT_SEEDS,
    carve_validation,
    construct,
    hybrid,
    score,
)

U2_METHODS = ("smote", "kmeans_smote", "rwo", "original_ugo", "u2_native", "u2_flow_gate")


def _split(dataset: str, seed: int) -> tuple[Any, Any, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    registry = DatasetRegistry(project_root=DEVROOT)
    spec = registry.get(dataset)
    loaded = load_dataset(spec, registry)
    split = make_split(loaded, seed).to_dict()
    train, _test_not_used = outer_frames(loaded.frame, split)
    del _test_not_used  # TEST is never scored in Phase 1
    inner_ids, val_ids = carve_validation(train, spec.target_column, dataset, seed)
    return spec, loaded, train.loc[inner_ids], train.loc[val_ids], split


def jobs(out: Path, datasets: list[str], seeds: list[int]) -> None:
    rows = []
    for dataset in datasets:
        for seed in seeds:
            spec, loaded, inner, validation, _ = _split(dataset, seed)
            n_min = int((inner[spec.target_column] == spec.minority_label).sum())
            budget = budget_rule(n_min)
            rows.append({"dataset_id": dataset, "split_seed": seed,
                         "dat_path": str(Path(loaded.path).resolve()),
                         "dat_sha256": sha256_file(Path(loaded.path)),
                         "minority_label": spec.minority_label, "budget": budget,
                         "pool_target": 4 * budget,
                         "inner_ids": [int(i) for i in inner.index],
                         "validation_ids": [int(i) for i in validation.index]})
    out.mkdir(parents=True, exist_ok=True)
    (out / "jobs.json").write_text(json.dumps(rows, sort_keys=True), encoding="utf-8")
    print(f"{len(rows)} jobs -> {out / 'jobs.json'}")


def _payloads(pool: dict[str, Any], spec: Any) -> pd.DataFrame:
    by_lower = {c.lower(): c for c in spec.feature_columns}
    frame = pd.DataFrame(pool["records"]).rename(columns=lambda c: by_lower[str(c).lower()])
    frame = frame.reindex(columns=list(spec.feature_columns))
    frame[spec.target_column] = pool["labels"]
    return frame


def gate_pool(dataset: str, seed: int, method: str, pool: dict[str, Any]) -> dict[str, Any]:
    spec, _loaded, inner, validation, split = _split(dataset, seed)
    specification = dataset_specification(DEVROOT, dataset)
    spec_dict = specification["specification"]
    n_min = int((inner[spec.target_column] == spec.minority_label).sum())
    budget = budget_rule(n_min)
    unit: dict[str, Any] = {"dataset_id": dataset, "split_seed": seed, "method": method,
                            "budget": budget, "pool_status": pool["status"], "rows": []}
    if pool["status"] != "ok":
        unit["pool_reason"] = pool.get("reason")
        return unit
    candidates = _payloads(pool, spec)
    records = candidates.to_dict(orient="records")
    features = list(spec.feature_columns)
    inner_rows = {digest({k: r[k] for k in features})
                  for r in inner.to_dict(orient="records")}
    feature_digests = [digest({k: r[k] for k in features}) for r in records]
    model = TrainEvidenceModel(specification, tuple(int(i) for i in inner.index),
                               inner.to_dict(orient="records"), M2Config())
    repair = Counter()
    for ordinal, payload in enumerate(records):
        occurrence = {"occurrence_id": f"u2:{dataset}:{seed}:{method}:{ordinal}",
                      "payload": payload, "payload_sha256": digest(payload),
                      "dataset_id": dataset, "source_artifact": "u2-pools",
                      "source_artifact_sha256": digest(records), "source_occurrence_ordinal": ordinal}
        structural = model.score(occurrence)[0].model_dump(mode="json")
        proposal = propose_repair(occurrence, specification, structural)
        repair[proposal["eligibility"]] += 1
        for reason in proposal["reasons"]:
            repair["reason:" + reason] += 1
    unit["gate"] = {
        "pool_n": len(records),
        "label_counts": dict(Counter(candidates[spec.target_column])),
        "structurally_complete_n": sum(complete_record(r, spec_dict) for r in records),
        "repair_outcomes": dict(repair),
        "exact_duplicate_within_pool_n": len(records) - len(set(feature_digests)),
        "exact_copy_of_inner_train_n": sum(d in inner_rows for d in feature_digests),
        # u2_pools.py writes None where a categorical block was not an exact one-hot.
        "noncategorical_one_hot_n": sum(any(r[c] is None for c in spec.categorical_columns)
                                        for r in records)}
    if not records:
        return unit
    provenance = {"generator": f"u2:{method}", "payload_fingerprint": digest(records),
                  "fit_row_ids": [int(i) for i in inner.index]}
    g, pools, concerns, _ = fresh_geometry(inner, candidates, specification,
                                           digest({"outer": split["split_fingerprint"],
                                                   "validation": [int(i) for i in validation.index]}),
                                           provenance)
    unit["gate"].update({f"{k}_admitted_n": len(v) for k, v in pools.items()})
    designs: list[tuple[str, list[int], str, int]] = [
        (f"{name}/random/s{s}", pools[name], "random", s)
        for name in ("schema", "combined") for s in SELECTION_SEEDS]
    designs += [(f"combined/{s}", pools["combined"], s, 42) for s in STRATEGIES]
    for name, eligible, strategy, sel_seed in designs:
        frame, info = construct(g, eligible, concerns, strategy, budget, sel_seed)
        if info["budget_achieved"] < budget:
            unit["rows"].append({"method": name, "status": "unavailable",
                                 "reason": "MATCHED_BUDGET_SHORTFALL", **info})
            continue
        for classifier in CLASSIFIERS:
            unit["rows"].append({"method": name, "classifier": classifier,
                                 "selection_seed": sel_seed, **info,
                                 **score(hybrid(inner, frame, spec), validation, spec,
                                         classifier)})
    return unit


def gate(pools_dir: Path, out: Path) -> None:
    (out / "units").mkdir(parents=True, exist_ok=True)
    files = sorted((pools_dir / "units").glob("*.json"))
    for done, path in enumerate(files, start=1):
        exported = json.loads(path.read_text(encoding="utf-8"))
        dataset, seed = exported["job"]["dataset_id"], exported["job"]["split_seed"]
        for method in U2_METHODS:
            target = out / "units" / f"{dataset}__s{seed}__{method}.json"
            if target.exists():
                continue
            start = time.perf_counter()
            pool = exported["methods"].get(method, {"status": "missing"})
            unit = gate_pool(dataset, seed, method, pool)
            unit["runtime_seconds"] = time.perf_counter() - start
            tmp = target.with_suffix(".tmp")
            tmp.write_text(json.dumps(unit, sort_keys=True, indent=1, allow_nan=False,
                                      default=str), encoding="utf-8")
            tmp.replace(target)
            print(dataset, seed, method, unit["pool_status"], unit.get("gate", {}).get("pool_n"),
                  flush=True)
        (out / "progress.json").write_text(json.dumps({"planned": len(files), "finished": done}),
                                           encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    j = sub.add_parser("jobs")
    j.add_argument("--out", type=Path, required=True)
    j.add_argument("--datasets", nargs="+", default=list(DEV))
    j.add_argument("--seeds", type=int, nargs="+", default=list(SPLIT_SEEDS))
    g = sub.add_parser("gate")
    g.add_argument("--pools", type=Path, required=True)
    g.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "jobs":
        jobs(args.out, args.datasets, args.seeds)
    else:
        gate(args.pools, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
