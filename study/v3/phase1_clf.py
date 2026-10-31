"""Phase 1 classifier ablation, main-venv side: export training sets for U2's five learners.

For every dev (dataset, split) unit this rebuilds the step-1 design exactly (same carve,
same SMOTE/SMOTENC pool, same admission) and exports raw training sets for: REAL_INNER_TRAIN,
SMOTE+b / SMOTENC+b, combined/random (selection seeds 13 and 29) and
combined/quality-coverage. It also writes two stratified halves of VALIDATION
(``phase1_oracle.halves``). ``u2_classifiers.py`` (U2 venv) then trains U2's five learners
with U2's search spaces and picks parameters and threshold on one half, scoring the other
(2-fold cross-fit). TEST is never exported.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rcqasyn.datasets.loader import load_dataset
from rcqasyn.datasets.registry import DatasetRegistry
from rcqasyn.datasets.split import make_split
from rcqasyn.empirical.addendum import budget_rule
from rcqasyn.empirical.generation import fresh_geometry, generate
from rcqasyn.phase2.common import digest
from rcqasyn.phase2.specifications import dataset_specification
from rcqasyn.phase6.utility import outer_frames

from .devroot import DEV, DEVROOT, sha256_file
from .phase1 import SPLIT_SEEDS, carve_validation, construct
from .phase1_oracle import halves

RANDOM_SEEDS = (13, 29)


def export_unit(dataset: str, split_seed: int) -> dict[str, Any]:
    registry = DatasetRegistry(project_root=DEVROOT)
    spec = registry.get(dataset)
    loaded = load_dataset(spec, registry)
    specification = dataset_specification(DEVROOT, dataset)
    split = make_split(loaded, split_seed).to_dict()
    train, _test_not_used = outer_frames(loaded.frame, split)
    del _test_not_used
    inner_ids, val_ids = carve_validation(train, spec.target_column, dataset, split_seed)
    inner, validation = train.loc[inner_ids], train.loc[val_ids]
    half_a, half_b = halves(validation, spec.target_column, dataset, split_seed)
    target, positive = spec.target_column, spec.minority_label
    budget = budget_rule(int((inner[target] == positive).sum()))
    method = "SMOTENC" if spec.categorical_columns else "SMOTE"
    augment: dict[str, Any] = {"REAL_INNER_TRAIN": []}
    unavailable: dict[str, str] = {}

    def minority_records(frame: Any) -> list[dict[str, Any]]:
        rows = frame.loc[frame[target] == positive, list(spec.feature_columns)]
        # Exact native values; DataFrame.to_json would round floats to 10 digits.
        return [{k: v.item() if hasattr(v, "item") else v for k, v in r.items()}
                for r in rows.to_dict(orient="records")]

    generated, _ = generate(inner, spec, method, budget, split_seed)
    augment[method + "+b"] = minority_records(generated)
    candidates, provenance = generate(inner, spec, method, 4 * budget, split_seed)
    g, pools, concerns, _ = fresh_geometry(
        inner, candidates, specification,
        digest({"outer": split["split_fingerprint"], "validation": val_ids}), provenance)
    designs = [(f"combined/random/s{s}", "random", s) for s in RANDOM_SEEDS]
    designs.append(("combined/quality-coverage", "quality-coverage", 42))
    for name, strategy, seed in designs:
        frame, info = construct(g, pools["combined"], concerns, strategy, budget, seed)
        if info["budget_achieved"] < budget:
            unavailable[name] = "MATCHED_BUDGET_SHORTFALL"
            continue
        augment[name] = minority_records(frame)
    return {"dataset_id": dataset, "split_seed": split_seed, "budget": budget,
            "dat_path": str(Path(loaded.path).resolve()), "dat_sha256": sha256_file(
                Path(loaded.path)), "minority_label": positive,
            "feature_columns": list(spec.feature_columns),
            "inner_ids": inner_ids, "half_a_ids": [int(i) for i in half_a.index],
            "half_b_ids": [int(i) for i in half_b.index],
            "augmentations": augment, "unavailable": unavailable}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--datasets", nargs="+", default=list(DEV))
    parser.add_argument("--seeds", type=int, nargs="+", default=list(SPLIT_SEEDS))
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    jobs = [export_unit(d, s) for d in args.datasets for s in args.seeds]
    (args.out / "jobs.json").write_text(json.dumps(jobs, sort_keys=True), encoding="utf-8")
    print(f"{len(jobs)} jobs -> {args.out / 'jobs.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
