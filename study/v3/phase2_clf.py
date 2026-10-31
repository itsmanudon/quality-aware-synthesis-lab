"""Phase 2 five-learner check, main-venv side: export cross-fit training sets per fold.

For named designs from a finished ``phase2.py run`` this rebuilds, per (dataset, split seed,
fold), exactly the same selection (same pool seed, same admission, same curator and utility
filter) and checks that its ``selected_ids_fingerprint`` equals the one recorded by the run,
so the learners see the very rows that the LR/RF screen scored. It exports the selected
minority rows (exact native values) with the inner and held-out row ids. ``u2_crossfit.py``
(U2 venv) then trains U2's five learners. TEST is never exported.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from rcqasyn.empirical.addendum import budget_rule
from rcqasyn.empirical.generation import fresh_geometry, generate
from rcqasyn.phase2.common import digest
from rcqasyn.phase2.specifications import dataset_specification

from .crossfit import K_FOLDS
from .devroot import DEV, DEVROOT, sha256_file
from .phase1 import SPLIT_SEEDS, construct
from .phase2 import RHOS, _u2_frame, fold_frames
from .repair_v3 import repair_pool
from .utility import Space, band, boundary_share, u2_term, utility_filter


def _minority_records(frame: pd.DataFrame, spec: Any) -> list[dict[str, Any]]:
    rows = frame.loc[frame[spec.target_column] == spec.minority_label,
                     list(spec.feature_columns)]
    return [{k: v.item() if hasattr(v, "item") else v for k, v in r.items()}
            for r in rows.to_dict(orient="records")]


def export_fold(dataset: str, split_seed: int, fold: int, designs: list[str], u2_dir: Path,
                run_dir: Path) -> dict[str, Any]:
    spec, loaded, inner, held, split = fold_frames(dataset, split_seed, fold)
    specification = dataset_specification(DEVROOT, dataset)
    target, positive = spec.target_column, spec.minority_label
    budget = budget_rule(int((inner[target] == positive).sum()))
    recorded = json.loads((run_dir / "units" / f"{dataset}__s{split_seed}__f{fold}.json")
                          .read_text(encoding="utf-8"))
    fingerprints = {r["method"]: r.get("selected_ids_fingerprint") for r in recorded["rows"]
                    if r.get("status") == "ok"}
    export = json.loads((u2_dir / "units" / f"{dataset}__s{split_seed}__f{fold}.json")
                        .read_text(encoding="utf-8"))
    anchors = {int(k): v for k, v in export["anchors"].items()}
    method = "SMOTENC" if spec.categorical_columns else "SMOTE"
    pool_seed = recorded["pool_seed"]
    augment: dict[str, Any] = {"REAL_INNER_TRAIN": []}
    unavailable: dict[str, str] = {}
    smote_b, _ = generate(inner, spec, method, budget, pool_seed)
    augment[method + "+b"] = _minority_records(smote_b, spec)
    smote_pool, provenance = generate(inner, spec, method, 4 * budget, pool_seed)
    u2_pool = _u2_frame(export, spec)
    raw_pools = {"smote": smote_pool,
                 "union": pd.concat([smote_pool, u2_pool], ignore_index=True)
                 if not u2_pool.empty else smote_pool}
    spec_dict = specification["specification"]
    if any(f.get("source_declaration", "").startswith("integer") for f in spec_dict["features"]):
        for name in list(raw_pools):
            raw_pools[name + "+round"] = repair_pool(raw_pools[name], spec_dict)[0]
    space = Space(inner, spec)
    fingerprint = digest({"outer": split["split_fingerprint"], "fold": fold,
                          "heldout": [int(i) for i in held.index]})
    wanted: dict[str, list[str]] = {}
    for design in designs:
        pool, _, rest = design.partition("/")
        wanted.setdefault(pool, []).append(rest)
    for pool, rests in wanted.items():
        if pool not in raw_pools:
            for rest in rests:
                unavailable[f"{pool}/{rest}"] = "POOL_NOT_BUILT_FOR_THIS_DATASET"
            continue
        candidates = raw_pools[pool]
        g, admitted, concerns, _ = fresh_geometry(
            inner, candidates, specification, fingerprint,
            {"generator": f"study-v3-phase2:{pool}", "fit_row_ids": provenance["fit_row_ids"],
             "payload_fingerprint": digest(candidates.to_dict(orient="records"))})
        eligible = admitted["combined"]
        payloads = pd.DataFrame([g.occurrences[i]["payload"] for i in eligible],
                                columns=pd.Index([*spec.feature_columns, target]))
        ids = {i: g.occurrences[i]["occurrence_id"] for i in eligible}
        for rest in rests:
            name = f"{pool}/{rest}"
            if name not in fingerprints:
                unavailable[name] = "NOT_OK_IN_RECORDED_RUN"
                continue
            parts = rest.split("/")
            if parts[0] == "random":
                subset, strategy, seed = eligible, "random", int(parts[1][1:])
            elif parts[0] == "quality-coverage":
                subset, strategy, seed = eligible, "quality-coverage", 42
            else:
                term, how = parts
                if term == "u2":
                    values_arr = u2_term(space, inner, payloads, target, positive, anchors)[0]
                else:
                    share = boundary_share(space, inner, payloads, target, positive)
                    values_arr = band(share, float(term.removeprefix("boundary")))
                values = dict(zip(eligible, values_arr.tolist(), strict=True))
                rho = 0.0 if how == "top" else float(how.removeprefix("rho").removesuffix("+qc"))
                if rho and rho not in RHOS:
                    raise ValueError(f"{name}: rho not in the declared grid")
                subset = utility_filter(eligible, values, rho, budget, ids)
                strategy, seed = ("random", 42) if how == "top" else ("quality-coverage", 42)
            frame, info = construct(g, subset, concerns, strategy, budget, seed)
            if info["selected_ids_fingerprint"] != fingerprints[name]:
                raise ValueError(f"{dataset} s{split_seed} f{fold} {name}: selection differs "
                                 "from the recorded run")
            augment[name] = _minority_records(frame, spec)
    return {"dataset_id": dataset, "split_seed": split_seed, "fold": fold, "budget": budget,
            "dat_path": str(Path(loaded.path).resolve()),
            "dat_sha256": sha256_file(Path(loaded.path)), "minority_label": positive,
            "feature_columns": list(spec.feature_columns),
            "inner_ids": [int(i) for i in inner.index],
            "heldout_ids": [int(i) for i in held.index],
            "augmentations": augment, "unavailable": unavailable}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True, help="finished phase2.py run")
    parser.add_argument("--u2", type=Path, required=True, help="u2_phase2.py output")
    parser.add_argument("--designs", nargs="+", required=True,
                        help="pool/design names as recorded, e.g. smote/quality-coverage")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--datasets", nargs="+", default=list(DEV))
    parser.add_argument("--seeds", type=int, nargs="+", default=list(SPLIT_SEEDS))
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    jobs = []
    for dataset in args.datasets:
        for seed in args.seeds:
            folds = [export_fold(dataset, seed, f, args.designs, args.u2, args.run)
                     for f in range(K_FOLDS)]
            jobs.append({"dataset_id": dataset, "split_seed": seed, "folds": folds})
            print(dataset, seed, {k: len(v) for k, v in folds[0]["augmentations"].items()},
                  flush=True)
    (args.out / "jobs.json").write_text(json.dumps(jobs, sort_keys=True), encoding="utf-8")
    print(f"{len(jobs)} jobs -> {args.out / 'jobs.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
