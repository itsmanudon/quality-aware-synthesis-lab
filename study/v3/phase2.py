"""Phase 2: utility-aware selection on the 8 dev datasets, 5-fold cross-fit inside TRAIN.

Gate 1 decisions (user, 2026-11-01): two utility terms (U2 difficulty x stability, boundary
score), stratified 5-fold cross-fitting inside each outer TRAIN for every tuning choice, and
a separately reported integer-rounding repair variant. TEST is never read: outer TEST ids are
computed only to reproduce the declared outer split and are dropped immediately.

Per (dev dataset, outer split seed, fold) unit, with inner = TRAIN minus the held-out fold:

    pools     smote   = SMOTE/SMOTENC(inner), 4 x budget  (rcqasyn.empirical.generation)
              union   = smote + U2 native + U2 flow-gate pools of the same fold (u2_phase2.py)
              +round  = the same pool after repair_v3 (only where integer fields are declared)
    gate      fresh_geometry (q = 0.90 combined admission), unchanged
    curators  random (5 selection seeds), quality-coverage (QC)
    utility   for term in {u2, boundary beta 0 / .25 / .5 / .75}:
                top-B by the term alone; top 25% / 50% by the term, then QC inside it
    training  HYBRID_MINORITY (inner + selected minority rows); references REAL (inner only)
              and SMOTE+b (budget-sized SMOTE, no gate)
    scoring   the held-out fold, LR and RF at frozen defaults; the minority probability of
              every held-out row is stored so ``phase2_report.py`` can pool the 5 folds and
              cross-fit the decision threshold.

``jobs`` writes the per-fold jobs for ``u2_phase2.py`` (U2 venv); ``run`` needs its output.
Runs are resumable per unit; ``progress.json`` records the state.
"""

from __future__ import annotations

import argparse
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
from rcqasyn.phase6.utility import outer_frames
from rcqasyn.utils.seeds import derive_seed

from .crossfit import K_FOLDS, crossfit_folds
from .devroot import DEV, DEVROOT, sha256_file
from .phase1 import CLASSIFIERS, SELECTION_SEEDS, SPLIT_SEEDS, construct, hybrid
from .repair_v3 import repair_pool
from .utility import Space, band, boundary_share, u2_term, utility_filter

BETAS = (0.0, 0.25, 0.5, 0.75)
RHOS = (0.25, 0.5)
U2_POOLS = ("u2_native", "u2_flow_gate")


def fold_frames(dataset: str, split_seed: int, fold: int
                ) -> tuple[Any, Any, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    registry = DatasetRegistry(project_root=DEVROOT)
    spec = registry.get(dataset)
    loaded = load_dataset(spec, registry)
    split = make_split(loaded, split_seed).to_dict()
    train, _test_not_used = outer_frames(loaded.frame, split)
    del _test_not_used  # TEST is never scored before Gate 2
    folds = crossfit_folds(train, spec.target_column, dataset, split_seed)
    held = folds[fold]
    inner_ids = sorted({int(i) for i in train.index} - set(held))
    return spec, loaded, train.loc[inner_ids], train.loc[held], split


def jobs(out: Path, datasets: list[str], seeds: list[int]) -> None:
    rows = []
    for dataset in datasets:
        for seed in seeds:
            for fold in range(K_FOLDS):
                spec, loaded, inner, held, _ = fold_frames(dataset, seed, fold)
                n_min = int((inner[spec.target_column] == spec.minority_label).sum())
                budget = budget_rule(n_min)
                rows.append({"dataset_id": dataset, "split_seed": seed, "fold": fold,
                             "dat_path": str(Path(loaded.path).resolve()),
                             "dat_sha256": sha256_file(Path(loaded.path)),
                             "minority_label": spec.minority_label, "budget": budget,
                             "pool_target": 4 * budget,
                             "inner_ids": [int(i) for i in inner.index],
                             "heldout_ids": [int(i) for i in held.index]})
    out.mkdir(parents=True, exist_ok=True)
    (out / "jobs.json").write_text(json.dumps(rows, sort_keys=True), encoding="utf-8")
    print(f"{len(rows)} jobs -> {out / 'jobs.json'}")


def _u2_frame(export: dict[str, Any], spec: Any) -> pd.DataFrame:
    frames = []
    by_lower = {c.lower(): c for c in spec.feature_columns}
    for method in U2_POOLS:
        pool = export["methods"].get(method, {})
        if pool.get("status") != "ok" or not pool["records"]:
            continue
        frame = pd.DataFrame(pool["records"]).rename(columns=lambda c: by_lower[str(c).lower()])
        frame = frame.reindex(columns=list(spec.feature_columns))
        frame[spec.target_column] = pool["labels"]
        frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def run_unit(dataset: str, split_seed: int, fold: int, u2_dir: Path) -> dict[str, Any]:
    spec, _loaded, inner, held, split = fold_frames(dataset, split_seed, fold)
    specification = dataset_specification(DEVROOT, dataset)
    spec_dict = specification["specification"]
    target, positive = spec.target_column, spec.minority_label
    n_min = int((inner[target] == positive).sum())
    budget = budget_rule(n_min)
    export_path = u2_dir / "units" / f"{dataset}__s{split_seed}__f{fold}.json"
    export = json.loads(export_path.read_text(encoding="utf-8"))
    if export["job"]["budget"] != budget:
        raise ValueError(f"{export_path}: budget differs from this fold")
    anchors = {int(k): v for k, v in export["anchors"].items()}
    method = "SMOTENC" if spec.categorical_columns else "SMOTE"
    pool_seed = derive_seed(split_seed, f"study-v3-crossfit-pool:{dataset}", fold) % (2 ** 32)
    unit: dict[str, Any] = {
        "dataset_id": dataset, "split_seed": split_seed, "fold": fold, "budget": budget,
        "generator": method, "pool_seed": pool_seed,
        "outer_split_fingerprint": split["split_fingerprint"],
        "inner_n": len(inner), "inner_minority_n": n_min, "heldout_n": len(held),
        "heldout_minority_n": int((held[target] == positive).sum()),
        "heldout_ids_fingerprint": digest([int(i) for i in held.index]),
        "u2_export_sha256": sha256_file(export_path), "test_used": False,
        "heldout_y": [int(v == positive) for v in held[target]],
        "pools": {}, "scores": {}, "rows": []}

    def add(name: str, frame: pd.DataFrame, **extra: Any) -> None:
        for classifier in CLASSIFIERS:
            result: dict[str, Any]
            try:
                result = evaluate(frame, held, spec, classifier)
            except (ValueError, TypeError, RuntimeError) as error:
                result = {"status": "failed", "reason": f"{type(error).__name__}: {error}"}
            row = {"method": name, "classifier": classifier, **extra,
                   **{k: result.get(k) for k in ("status", "reason", "tp", "fp", "fn", "tn")}}
            unit["rows"].append(row)
            if result.get("status") == "ok":
                predictions: list[dict[str, Any]] = result["predictions"]
                unit["scores"][f"{name}|{classifier}"] = [
                    round(float(p["score"]), 7) for p in predictions]

    add("REAL_INNER_TRAIN", inner)
    try:
        smote_b, _ = generate(inner, spec, method, budget, pool_seed)
        add(method + "+b", hybrid(inner, smote_b, spec))
    except (ValueError, TypeError, RuntimeError) as error:
        unit["rows"].append({"method": method + "+b", "status": "failed",
                             "reason": f"{type(error).__name__}: {error}"})
    smote_pool, provenance = generate(inner, spec, method, 4 * budget, pool_seed)
    if set(provenance["fit_row_ids"]) & {int(i) for i in held.index}:
        raise ValueError("generator fit identities overlap the held-out fold")
    u2_pool = _u2_frame(export, spec)
    pools = {"smote": smote_pool,
             "union": pd.concat([smote_pool, u2_pool], ignore_index=True)
             if not u2_pool.empty else smote_pool}
    unit["pool_sources"] = {"smote_n": len(smote_pool), "u2_n": len(u2_pool),
                            "u2_status": {m: (export["methods"].get(m, {}).get("status"),
                                              export["methods"].get(m, {}).get("n"))
                                          for m in U2_POOLS}}
    if any(f.get("source_declaration", "").startswith("integer")
           for f in spec_dict["features"]):
        for name in list(pools):
            repaired, outcome = repair_pool(pools[name], spec_dict)
            pools[name + "+round"] = repaired
            unit["pools"][name + "+round"] = {"repair": outcome}
    space = Space(inner, spec)
    fingerprint = digest({"outer": split["split_fingerprint"], "fold": fold,
                          "heldout": [int(i) for i in held.index]})
    for name, candidates in pools.items():
        g, admitted, concerns, _ = fresh_geometry(
            inner, candidates, specification, fingerprint,
            {"generator": f"study-v3-phase2:{name}", "fit_row_ids": provenance["fit_row_ids"],
             "payload_fingerprint": digest(candidates.to_dict(orient="records"))})
        info = unit["pools"].setdefault(name, {})
        info.update({"candidates_n": len(candidates),
                     **{f"{k}_n": len(v) for k, v in admitted.items()}})
        eligible = admitted["combined"]
        if len(eligible) < budget:
            unit["rows"].append({"method": f"{name}/*", "status": "unavailable",
                                 "reason": "MATCHED_BUDGET_SHORTFALL",
                                 "eligible_n": len(eligible)})
            continue
        payloads = pd.DataFrame([g.occurrences[i]["payload"] for i in eligible],
                                columns=pd.Index([*spec.feature_columns, target]))
        ids = {i: g.occurrences[i]["occurrence_id"] for i in eligible}
        share = boundary_share(space, inner, payloads, target, positive)
        u2_values, anchor_ids = u2_term(space, inner, payloads, target, positive, anchors)
        terms = {"u2": dict(zip(eligible, u2_values.tolist(), strict=True))}
        for beta in BETAS:
            terms[f"boundary{beta:g}"] = dict(zip(eligible, band(share, beta).tolist(),
                                                  strict=True))
        info.update({"boundary_share_mean": float(share.mean()),
                     "boundary_share_histogram": dict(Counter(np.round(share, 2).tolist())),
                     "u2_term_mean": float(u2_values.mean()),
                     "u2_distinct_anchors": len(set(anchor_ids.tolist()))})
        designs: list[tuple[str, list[int], str, int, dict[str, Any]]] = [
            (f"{name}/random/s{s}", eligible, "random", s, {}) for s in SELECTION_SEEDS]
        designs.append((f"{name}/quality-coverage", eligible, "quality-coverage", 42, {}))
        for term, values in terms.items():
            top = utility_filter(eligible, values, 0.0, budget, ids)
            designs.append((f"{name}/{term}/top", top, "random", 42,
                            {"term": term, "rho": 0.0}))
            for rho in RHOS:
                kept = utility_filter(eligible, values, rho, budget, ids)
                designs.append((f"{name}/{term}/rho{rho:g}+qc", kept, "quality-coverage", 42,
                                {"term": term, "rho": rho}))
        for design, subset, strategy, sel_seed, extra in designs:
            frame, built = construct(g, subset, concerns, strategy, budget, sel_seed)
            if built["budget_achieved"] < budget:
                unit["rows"].append({"method": design, "status": "unavailable",
                                     "reason": "MATCHED_BUDGET_SHORTFALL", **built})
                continue
            add(design, hybrid(inner, frame, spec), pool=name, selection_seed=sel_seed,
                selected_ids_fingerprint=built["selected_ids_fingerprint"], **extra)
    return unit


def run(u2_dir: Path, out: Path, datasets: list[str], seeds: list[int]) -> None:
    units_dir = out / "units"
    units_dir.mkdir(parents=True, exist_ok=True)
    plan = [(d, s, f) for d in datasets for s in seeds for f in range(K_FOLDS)]
    for done, (dataset, seed, fold) in enumerate(plan, start=1):
        path = units_dir / f"{dataset}__s{seed}__f{fold}.json"
        if not path.exists():
            start = time.perf_counter()
            unit = run_unit(dataset, seed, fold, u2_dir)
            unit["runtime_seconds"] = time.perf_counter() - start
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(unit, sort_keys=True, allow_nan=False, default=str),
                           encoding="utf-8")
            tmp.replace(path)
            print(f"{dataset} s{seed} f{fold}: {len(unit['rows'])} rows, "
                  f"{unit['runtime_seconds']:.1f}s", flush=True)
        (out / "progress.json").write_text(json.dumps(
            {"planned_units": len(plan), "finished_units": done,
             "last": [dataset, seed, fold]}, sort_keys=True), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    j = sub.add_parser("jobs")
    j.add_argument("--out", type=Path, required=True)
    j.add_argument("--datasets", nargs="+", default=list(DEV))
    j.add_argument("--seeds", type=int, nargs="+", default=list(SPLIT_SEEDS))
    r = sub.add_parser("run")
    r.add_argument("--u2", type=Path, required=True, help="u2_phase2.py output directory")
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("--datasets", nargs="+", default=list(DEV))
    r.add_argument("--seeds", type=int, nargs="+", default=list(SPLIT_SEEDS))
    args = parser.parse_args(argv)
    if args.command == "jobs":
        jobs(args.out, args.datasets, args.seeds)
    else:
        run(args.u2, args.out, args.datasets, args.seeds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
