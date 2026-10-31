"""Phase 2 evaluation of fresh local LLM pools (``llm_pools.py``) on dev cross-fit folds.

Per (model, dev dataset, split seed, fold), with inner = TRAIN minus the held-out fold:

    pool      the fold's LLM candidates with exactly the declared keys, unmodified
              (+round: after repair_v3, where integer fields are declared)
    gate      structural completeness, q = 0.90 admission (fresh_geometry), copying
              diagnostics (exact copies of inner TRAIN rows, of the prompt's reference rows,
              within-pool duplicates; copying diagnostics, not privacy results)
    quota     QC with minority quota fraction = real inner minority share, 0.5 and 1.0
              (Gate 1 decision 3 ablation), random (5 seeds) as the paired reference
    training  HYBRID_MINORITY (inner + the selected minority rows), LR and RF; held-out
              scores stored per row as in ``phase2.py`` so ``phase2_report`` can pool them

TEST is never read. Resumable per unit.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from rcqasyn.empirical.addendum import budget_rule
from rcqasyn.empirical.evaluation import evaluate
from rcqasyn.empirical.generation import fresh_geometry
from rcqasyn.phase2.common import digest
from rcqasyn.phase2.specifications import dataset_specification
from rcqasyn.phase5.geometry import complete_record

from .crossfit import K_FOLDS
from .devroot import DEV, DEVROOT
from .llm_pools import load_pool, unit_dir
from .phase1 import CLASSIFIERS, SELECTION_SEEDS, SPLIT_SEEDS, construct, hybrid
from .phase2 import fold_frames
from .repair_v3 import repair_pool


def run_unit(model: str, dataset: str, split_seed: int, fold: int, pools_dir: Path
             ) -> dict[str, Any]:
    spec, loaded, inner, held, split = fold_frames(dataset, split_seed, fold)
    specification = dataset_specification(DEVROOT, dataset)
    spec_dict = specification["specification"]
    target, positive = spec.target_column, str(spec.minority_label)
    n_min = int((inner[target].astype(str) == positive).sum())
    budget = budget_rule(n_min)
    directory = unit_dir(pools_dir, model, dataset, split_seed, fold)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest["budget"] != budget or manifest["outer_split_fingerprint"] != split[
            "split_fingerprint"]:
        raise ValueError(f"{directory}: pool manifest does not match this fold")
    frame, load_counts = load_pool(directory, spec)
    unit: dict[str, Any] = {
        "model": model, "dataset_id": dataset, "split_seed": split_seed, "fold": fold,
        "budget": budget, "inner_minority_share": n_min / len(inner),
        "pool_manifest_sha256": digest(manifest), "load": load_counts, "test_used": False,
        "heldout_y": [int(v == positive) for v in held[target].astype(str)],
        "pools": {}, "scores": {}, "rows": []}
    features = list(spec.feature_columns)
    inner_rows = {digest({k: r[k] for k in features}) for r in inner.to_dict(orient="records")}
    references = {digest({k: loaded.frame.loc[i, k] for k in features})
                  for i in manifest["reference_row_ids"]}

    def add(name: str, train: pd.DataFrame, **extra: Any) -> None:
        for classifier in CLASSIFIERS:
            result: dict[str, Any]
            try:
                result = evaluate(train, held, spec, classifier)
            except (ValueError, TypeError, RuntimeError) as error:
                result = {"status": "failed", "reason": f"{type(error).__name__}: {error}"}
            unit["rows"].append({"method": name, "classifier": classifier, **extra,
                                 **{k: result.get(k) for k in ("status", "reason", "tp", "fp",
                                                               "fn", "tn")}})
            if result.get("status") == "ok":
                predictions: list[dict[str, Any]] = result["predictions"]
                unit["scores"][f"{name}|{classifier}"] = [round(float(p["score"]), 7)
                                                          for p in predictions]

    add("REAL_INNER_TRAIN", inner)
    pools = {"llm": frame}
    if any(f.get("source_declaration", "").startswith("integer") for f in spec_dict["features"]):
        repaired, outcome = repair_pool(frame, spec_dict)
        pools["llm+round"] = repaired
        unit["pools"]["llm+round"] = {"repair": outcome}
    fingerprint = digest({"outer": split["split_fingerprint"], "fold": fold,
                          "heldout": [int(i) for i in held.index]})
    for name, candidates in pools.items():
        records = candidates.to_dict(orient="records")
        digests = [digest({k: r[k] for k in features}) for r in records]
        info = unit["pools"].setdefault(name, {})
        info.update({
            "candidates_n": len(records),
            "label_counts": dict(Counter(str(r[target]) for r in records)),
            "structurally_complete_n": sum(complete_record(r, spec_dict) for r in records),
            "exact_copy_of_inner_train_n": sum(d in inner_rows for d in digests),
            "exact_copy_of_reference_n": sum(d in references for d in digests),
            "exact_duplicate_within_pool_n": len(digests) - len(set(digests))})
        if not records:
            continue
        g, admitted, concerns, _ = fresh_geometry(
            inner, candidates, specification, fingerprint,
            {"generator": f"study-v3-phase2-llm:{model}:{name}",
             "fit_row_ids": [int(i) for i in inner.index],
             "payload_fingerprint": digest(records)})
        eligible = admitted["combined"]
        info.update({f"{k}_admitted_n": len(v) for k, v in admitted.items()})
        info["combined_minority_n"] = sum(
            str(g.occurrences[i]["payload"][target]) == positive for i in eligible)
        if len(eligible) < budget:
            unit["rows"].append({"method": f"{name}/*", "status": "unavailable",
                                 "reason": "MATCHED_BUDGET_SHORTFALL",
                                 "eligible_n": len(eligible)})
            continue
        designs = [(f"{name}/random/s{s}", "random", s, None) for s in SELECTION_SEEDS]
        designs += [(f"{name}/qc-quota-{label}", "quality-coverage", 42, quota)
                    for label, quota in (("real", n_min / len(inner)), ("0.5", 0.5),
                                         ("1.0", 1.0))]
        for design, strategy, seed, quota in designs:
            built_frame, built = construct(g, eligible, concerns, strategy, budget, seed,
                                           quota if quota is not None else .5)
            if built["budget_achieved"] < budget:
                unit["rows"].append({"method": design, "status": "unavailable",
                                     "reason": "MATCHED_BUDGET_SHORTFALL", **built})
                continue
            minority_added = int((built_frame[target].astype(str) == positive).sum())
            add(design, hybrid(inner, built_frame, spec), pool=name, quota=quota,
                minority_added=minority_added,
                selected_ids_fingerprint=built["selected_ids_fingerprint"])
    return unit


def run(model: str, pools_dir: Path, out: Path, datasets: list[str], seeds: list[int],
        folds: list[int]) -> None:
    units_dir = out / "units"
    units_dir.mkdir(parents=True, exist_ok=True)
    plan = [(d, s, f) for d in datasets for s in seeds for f in folds]
    for done, (dataset, seed, fold) in enumerate(plan, start=1):
        path = units_dir / f"{dataset}__s{seed}__f{fold}.json"
        if not path.exists():
            start = time.perf_counter()
            unit = run_unit(model, dataset, seed, fold, pools_dir)
            unit["runtime_seconds"] = time.perf_counter() - start
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(unit, sort_keys=True, allow_nan=False, default=str),
                           encoding="utf-8")
            tmp.replace(path)
            print(f"{dataset} s{seed} f{fold}: {len(unit['rows'])} rows", flush=True)
        (out / "progress.json").write_text(json.dumps(
            {"planned_units": len(plan), "finished_units": done}), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--pools", type=Path, required=True, help="llm_pools.py --out")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--datasets", nargs="+", default=list(DEV))
    parser.add_argument("--seeds", type=int, nargs="+", default=list(SPLIT_SEEDS))
    parser.add_argument("--folds", type=int, nargs="+", default=list(range(K_FOLDS)))
    args = parser.parse_args(argv)
    run(args.model, args.pools, args.out, args.datasets, args.seeds, args.folds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
