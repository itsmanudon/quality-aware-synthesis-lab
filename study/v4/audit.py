# pyright: reportAttributeAccessIssue=false, reportOperatorIssue=false, reportGeneralTypeIssues=false, reportArgumentType=false, reportCallIssue=false, reportIndexIssue=false
"""Study v4 Part A: audit of generated minority records against inner TRAIN only.

Per benchmark unit (dataset x split seed) and generator pool (3 LLMs from Study v3 Phase 3,
and the U2-side pools: SMOTE, U2 native, U2 with FlowGMM gate), every metric uses inner TRAIN
(outer TRAIN minus the 20% VALIDATION carve) as its only reference. VALIDATION and TEST are
never read. Records are taken exactly as stored; nothing is repaired, clipped or imputed.

Metrics (descriptive; no test, no threshold claim):
- output health (LLM): requests, ok/failed calls, parse failures, finish reasons
  (truncation), tokens, records returned vs requested;
- validity: declared-schema completeness (``complete_record``), records not of the requested
  class, categories never seen in inner TRAIN, numeric values outside the inner-TRAIN range;
- copying diagnostics (never privacy results): exact copies of inner-TRAIN rows, of the
  prompt's reference rows (LLM), within-pool duplicates;
- fidelity vs inner-TRAIN minority: per-feature KS (numeric) and total variation
  (categorical), mean absolute difference of numeric correlations, discriminator AUC
  (random forest, 5-fold, real minority vs synthetic, balanced subsample);
- distances in the inner-TRAIN-fitted space: nearest inner-TRAIN row (median, exact-zero
  share), nearest other pool record, real-minority coverage at the real minority's own
  median nearest-neighbour distance;
- gate support (outer TRAIN <= SIZE_LIMIT rows): all pools of a unit pooled and scored by one
  RC-QASyn gate fit; per generator the share admitted (schema / local / global / combined)
  and the median raw support scores.

Run any number of copies; units are claimed with lock files (``study.v3.claims``).
"""

from __future__ import annotations

import argparse
import json
import time
import warnings
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.neighbors import NearestNeighbors

from rcqasyn.empirical.generation import fresh_geometry
from rcqasyn.phase2.common import digest
from rcqasyn.phase2.specifications import dataset_specification
from rcqasyn.phase5.geometry import complete_record
from study.v3.claims import claim, release
from study.v3.llm_pools import _lines, load_pool
from study.v3.phase1 import SPLIT_SEEDS
from study.v3.phase3 import BENCHROOT, U2_POOLS, _nulls, _u2_frame, benchmark_ids, split_frames
from study.v3.repair_v3 import repair_pool
from study.v3.utility import Space

V3 = Path("study/v3/runs/phase3")
LLMS = ("claude-haiku-5-5", "gpt-6-luna", "muse-spark-1.3")
SIZE_LIMIT = 50_000  # outer TRAIN rows; declared in PLAN.md before any result
DISC_MAX = 2_000
NN_REF_MAX = 20_000


def _key(row: dict[str, Any], features: list[str], numerical: set[str]) -> tuple:
    out = []
    for f in features:
        v = row.get(f)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            out.append(None)
        elif f in numerical:
            try:
                out.append(round(float(v), 6))
            except (TypeError, ValueError):
                out.append(("str", str(v)))
        else:
            out.append(str(v))
    return tuple(out)


def _numeric(frame: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    return pd.DataFrame({c: pd.to_numeric(frame[c], errors="coerce") for c in cols},
                        index=frame.index)


def llm_health(directory: Path) -> dict[str, Any]:
    calls = _lines(directory / "calls.jsonl")
    seen: dict[str, dict[str, Any]] = {}
    for c in calls:  # a twice-collected batch repeats lines; count each call once
        seen.setdefault(json.dumps(c, sort_keys=True), c)
    calls = list(seen.values())
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    ok = [c for c in calls if c["status"] == "ok"]
    return {"planned_requests": manifest["planned_requests"],
            "requested_records": manifest["pool_factor"] * manifest["budget"],
            "ok_calls": len({c["custom_id"] for c in ok}),
            "failed_call_lines": sum(c["status"] == "failed" for c in calls),
            "returned": sum(c.get("returned") or 0 for c in ok),
            "parse_failures": sum(c.get("parse_failures") or 0 for c in ok),
            "finish_reasons": dict(Counter(str(c.get("finish_reason")) for c in ok)),
            "input_tokens": sum(c.get("input_tokens") or 0 for c in ok),
            "output_tokens": sum(c.get("output_tokens") or 0 for c in ok),
            "reasoning_tokens": sum(c.get("reasoning_tokens") or 0 for c in ok),
            "reference_row_ids": manifest["reference_row_ids"]}


def pool_metrics(pool: pd.DataFrame, inner: pd.DataFrame, spec: Any, spec_dict: dict,
                 space: Space, train_keys: set, ref_keys: set, ref_nn: dict[str, Any],
                 seed: int) -> dict[str, Any]:
    features = list(spec.feature_columns)
    numerical, categorical = list(spec.numerical_columns), list(spec.categorical_columns)
    target, positive = spec.target_column, str(spec.minority_label)
    records = pool.to_dict(orient="records")
    n = len(records)
    out: dict[str, Any] = {"n": n}
    if n == 0:
        return out
    real = inner[inner[target].astype(str) == positive]
    keys = [_key(r, features, set(numerical)) for r in records]
    integer = any(x.get("source_declaration", "").startswith("integer")
                  for x in spec_dict["features"])
    rounded = repair_pool(pool, spec_dict)[0] if integer else pool
    out.update({
        "complete": int(sum(complete_record(r, spec_dict) for r in _nulls(pool).to_dict(
            orient="records"))),
        # Interpolating generators emit non-integer values for integer-declared fields; the
        # v3 rounding variant shows how many records only fail on that.
        "complete_after_integer_rounding": int(sum(
            complete_record(r, spec_dict) for r in _nulls(rounded).to_dict(orient="records"))),
        "not_requested_class": int(sum(str(r.get(target)) != positive for r in records)),
        "exact_copy_of_inner_train": int(sum(k in train_keys for k in keys)),
        "exact_copy_of_reference": int(sum(k in ref_keys for k in keys)) if ref_keys else None,
        "within_pool_duplicates": n - len(set(keys))})
    unseen = 0
    for c in categorical:
        seen = set(inner[c].dropna().astype(str))
        unseen += int(sum(r.get(c) is not None and str(r.get(c)) not in seen for r in records))
    out["unseen_category_cells"] = unseen
    out_of_range = 0
    ks, tv = [], []
    num_pool, num_real = _numeric(pool, numerical), _numeric(real, numerical)
    num_inner = _numeric(inner, numerical)
    for c in numerical:
        lo, hi = num_inner[c].min(), num_inner[c].max()
        v = num_pool[c].dropna()
        out_of_range += int(((v < lo) | (v > hi)).sum())
        r = num_real[c].dropna()
        if len(v) and len(r):
            ks.append(float(stats.ks_2samp(v, r).statistic))
    for c in categorical:
        p = pool[c].dropna().astype(str).value_counts(normalize=True)
        q = real[c].dropna().astype(str).value_counts(normalize=True)
        if len(p) and len(q):
            tv.append(float(0.5 * p.subtract(q, fill_value=0).abs().sum()))
    out.update({"out_of_train_range_cells": out_of_range,
                "mean_ks": float(np.mean(ks)) if ks else None,
                "mean_tv": float(np.mean(tv)) if tv else None})
    if len(numerical) >= 2 and len(num_pool.dropna()) >= 5 and len(num_real.dropna()) >= 5:
        cp, cr = num_pool.corr().to_numpy(), num_real.corr().to_numpy()
        iu = np.triu_indices_from(cp, k=1)
        diff = np.abs(cp[iu] - cr[iu])
        out["corr_mean_abs_diff"] = float(np.nanmean(diff)) if np.isfinite(diff).any() else None
    complete_pool = pool[[*features]].copy()
    xs = space.transform(complete_pool)
    xr = space.transform(real[features])
    rng = np.random.default_rng(seed)
    m = min(len(xs), len(xr), DISC_MAX)
    if m >= 10:
        a = xs[rng.choice(len(xs), m, replace=False)]
        b = xr[rng.choice(len(xr), m, replace=False)]
        x = np.vstack([a, b])
        y = np.r_[np.ones(m), np.zeros(m)]
        clf = RandomForestClassifier(n_estimators=200, random_state=seed, n_jobs=4)
        cv = StratifiedKFold(5, shuffle=True, random_state=seed)
        out["discriminator_auc"] = float(cross_val_score(clf, x, y, cv=cv,
                                                         scoring="roc_auc").mean())
    dist_train, _ = ref_nn["train"].kneighbors(xs, n_neighbors=1)
    out["dcr_median"] = float(np.median(dist_train))
    out["dcr_zero_share"] = float(np.mean(dist_train[:, 0] < 1e-9))
    out["dcr_below_real_nn_share"] = float(np.mean(dist_train[:, 0] < ref_nn["real_median"]))
    if len(xs) >= 2:
        within = NearestNeighbors(n_neighbors=2).fit(xs).kneighbors(xs)[0][:, 1]
        out["within_pool_nn_median"] = float(np.median(within))
        cover = NearestNeighbors(n_neighbors=1).fit(xs).kneighbors(xr)[0][:, 0]
        out["real_minority_coverage"] = float(np.mean(cover <= ref_nn["real_median"]))
    out["real_minority_nn_median"] = ref_nn["real_median"]
    return out


def gate_metrics(pools: dict[str, pd.DataFrame], inner: pd.DataFrame, specification: dict,
                 split_fingerprint: str) -> dict[str, Any]:
    names = [n for n, p in pools.items() if len(p)]
    if not names:
        return {}
    union = pd.concat([pools[n] for n in names], ignore_index=True)
    source = np.concatenate([[n] * len(pools[n]) for n in names])
    _, admitted, _, evidence = fresh_geometry(
        _nulls(inner), _nulls(union), specification,
        digest({"outer": split_fingerprint, "audit": "study-v4"}),
        {"generator": "study-v4-audit:" + "+".join(names),
         "fit_row_ids": [int(i) for i in inner.index],
         "payload_fingerprint": digest(_nulls(union).to_dict(orient="records"))})
    raw: dict[str, list[float | None]] = {"local_support": [], "cross_feature": []}
    for es in evidence["scores"]:
        for fam, values in raw.items():
            values.append(next((e["raw_score"] for e in es if e["validator_family"] == fam),
                               None))
    out: dict[str, Any] = {}
    for n in names:
        idx = np.flatnonzero(source == n)
        sets = {k: set(v) for k, v in admitted.items()}
        row: dict[str, Any] = {f"{k}_admitted_share": float(np.mean([i in s for i in idx]))
                               for k, s in sets.items()}
        for fam, values in raw.items():
            v = [values[i] for i in idx if values[i] is not None]
            row[f"{fam}_raw_median"] = float(np.median(v)) if v else None
        out[n] = row
    return out


def run_unit(dataset: str, seed: int) -> dict[str, Any]:
    f = split_frames(dataset, seed)
    spec, inner, split = f["spec"], f["inner"], f["split"]
    specification = dataset_specification(BENCHROOT, dataset)
    spec_dict = specification["specification"]
    features = list(spec.feature_columns)
    numerical = set(spec.numerical_columns)
    target, positive = spec.target_column, str(spec.minority_label)
    outer_n = len(f["train"])
    unit: dict[str, Any] = {"dataset_id": dataset, "split_seed": seed, "outer_train_n": outer_n,
                            "inner_n": len(inner),
                            "inner_minority_n": int((inner[target].astype(str) == positive).sum()),
                            "features": len(features), "categorical": len(spec.categorical_columns),
                            "inner_missing_cells": int(inner[features].isna().sum().sum()),
                            "validation_used": False, "test_used": False,
                            "pools": {}, "health": {}, "unavailable": {}}
    pools: dict[str, pd.DataFrame] = {}
    for g in LLMS:
        d = V3 / "llm" / g / f"{dataset}__s{seed}"
        if not (d / "manifest.json").exists():
            unit["unavailable"][g] = "NO_LLM_UNIT"
            continue
        unit["health"][g] = llm_health(d)
        if (d / "candidates.jsonl").exists():
            frame, counts = load_pool(d, spec)
            unit["health"][g]["load"] = counts
            pools[g] = frame
        else:
            pools[g] = pd.DataFrame(columns=pd.Index([*features, target]))
            unit["unavailable"][g] = "NO_PARSED_RECORDS"
    u2_path = V3 / "u2" / "units" / f"{dataset}__s{seed}.json"
    if u2_path.exists():
        export = json.loads(u2_path.read_text(encoding="utf-8"))
        for name in U2_POOLS:
            pools[name.removeprefix("pool:")] = _u2_frame(export["outputs"].get(name, {}), spec)
    else:
        for name in U2_POOLS:
            unit["unavailable"][name.removeprefix("pool:")] = "NO_U2_UNIT"
    space = Space(inner, spec)
    x_inner = space.transform(inner[features])
    rng = np.random.default_rng(seed)
    ref_idx = (rng.choice(len(x_inner), NN_REF_MAX, replace=False) if len(x_inner) > NN_REF_MAX
               else np.arange(len(x_inner)))
    real_mask = (inner[target].astype(str) == positive).to_numpy()
    xr = x_inner[real_mask]
    real_nn = NearestNeighbors(n_neighbors=2).fit(xr).kneighbors(xr)[0][:, 1]
    ref_nn = {"train": NearestNeighbors(n_neighbors=1).fit(x_inner[ref_idx]),
              "real_median": float(np.median(real_nn))}
    train_keys = {_key(r, features, numerical) for r in inner.to_dict(orient="records")}
    for name, pool in pools.items():
        ref_keys: set = set()
        if name in unit["health"]:
            ids = unit["health"][name]["reference_row_ids"]
            ref_keys = {_key(r, features, numerical)
                        for r in f["loaded"].frame.loc[ids].to_dict(orient="records")}
        unit["pools"][name] = pool_metrics(pool, inner, spec, spec_dict, space, train_keys,
                                           ref_keys, ref_nn, seed)
    if outer_n <= SIZE_LIMIT:
        unit["gate"] = gate_metrics(pools, inner, specification, split["split_fingerprint"])
    else:
        unit["gate"] = {}
        unit["unavailable"]["gate"] = "SIZE_LIMIT"
    return unit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("study/v4/runs/phase1"))
    parser.add_argument("--datasets", nargs="+", default=None)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(SPLIT_SEEDS))
    args = parser.parse_args(argv)
    warnings.filterwarnings("ignore")
    (args.out / "units").mkdir(parents=True, exist_ok=True)
    for dataset in args.datasets or benchmark_ids():
        for seed in args.seeds:
            path = args.out / "units" / f"{dataset}__s{seed}.json"
            if path.exists() or not claim(path):
                continue
            start = time.perf_counter()
            unit = run_unit(dataset, seed)
            unit["runtime_seconds"] = time.perf_counter() - start
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(unit, sort_keys=True, default=str), encoding="utf-8")
            tmp.replace(path)
            release(path)
            print(dataset, seed, f"{unit['runtime_seconds']:.0f}s",
                  {k: v.get("n") for k, v in unit["pools"].items()}, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
