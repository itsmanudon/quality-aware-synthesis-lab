# pyright: reportAttributeAccessIssue=false, reportOperatorIssue=false, reportGeneralTypeIssues=false, reportArgumentType=false, reportCallIssue=false, reportIndexIssue=false
"""Study v4 Part A check: is the discriminator AUC an artifact of numeric precision?

LLMs write rounded numbers (e.g. 0.52); real data has full precision. A discriminator could
separate the two by formatting alone. For every unit and pool this recomputes the audit's
discriminator AUC (same space, subsample and random forest) twice: as stored, and after
rounding every numeric feature of BOTH the real minority and the pool to the coarser of their
two typical precisions (per feature, the median number of decimals; the smaller one). If the
AUC falls toward 0.5 after rounding, formatting explained it; if it stays high, the
difference is distributional. Inner TRAIN only; nothing is written back to any pool.
"""

from __future__ import annotations

import argparse
import json
import time
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score

from study.v3.claims import claim, release
from study.v3.llm_pools import load_pool
from study.v3.phase1 import SPLIT_SEEDS
from study.v3.phase3 import U2_POOLS, _u2_frame, benchmark_ids, split_frames
from study.v3.utility import Space
from study.v4.audit import DISC_MAX, LLMS, V3


def decimals(values: pd.Series) -> int:
    v = pd.to_numeric(values, errors="coerce").dropna()
    if v.empty:
        return 0
    counts = [len(f"{x:.10f}".rstrip("0").split(".")[1]) for x in v.to_numpy()]
    return int(np.median(counts))


def auc(space: Space, real: pd.DataFrame, pool: pd.DataFrame, features: list[str],
        seed: int) -> float | None:
    xs, xr = space.transform(pool[features]), space.transform(real[features])
    rng = np.random.default_rng(seed)
    m = min(len(xs), len(xr), DISC_MAX)
    if m < 10:
        return None
    a = xs[rng.choice(len(xs), m, replace=False)]
    b = xr[rng.choice(len(xr), m, replace=False)]
    x, y = np.vstack([a, b]), np.r_[np.ones(m), np.zeros(m)]
    clf = RandomForestClassifier(n_estimators=200, random_state=seed, n_jobs=4)
    cv = StratifiedKFold(5, shuffle=True, random_state=seed)
    return float(cross_val_score(clf, x, y, cv=cv, scoring="roc_auc").mean())


def run_unit(dataset: str, seed: int) -> dict[str, Any]:
    f = split_frames(dataset, seed)
    spec, inner = f["spec"], f["inner"]
    features, numerical = list(spec.feature_columns), list(spec.numerical_columns)
    target, positive = spec.target_column, str(spec.minority_label)
    real = inner[inner[target].astype(str) == positive]
    pools: dict[str, pd.DataFrame] = {}
    for g in LLMS:
        d = V3 / "llm" / g / f"{dataset}__s{seed}"
        if (d / "candidates.jsonl").exists():
            pools[g] = load_pool(d, spec)[0]
    u2 = V3 / "u2" / "units" / f"{dataset}__s{seed}.json"
    if u2.exists():
        export = json.loads(u2.read_text(encoding="utf-8"))
        for name in U2_POOLS:
            pools[name.removeprefix("pool:")] = _u2_frame(export["outputs"].get(name, {}), spec)
    space = Space(inner, spec)
    out: dict[str, Any] = {"dataset_id": dataset, "split_seed": seed, "test_used": False,
                           "pools": {}}
    for name, pool in pools.items():
        if len(pool) < 10:
            continue
        precision = {c: min(decimals(real[c]), decimals(pool[c])) for c in numerical}
        rr, pr = real.copy(), pool.copy()
        for c, d in precision.items():
            rr[c] = pd.to_numeric(rr[c], errors="coerce").round(d)
            pr[c] = pd.to_numeric(pr[c], errors="coerce").round(d)
        out["pools"][name] = {"auc_stored": auc(space, real, pool, features, seed),
                              "auc_rounded": auc(space, rr, pr, features, seed),
                              "decimals": precision}
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("study/v4/runs/phase1-precision"))
    args = parser.parse_args(argv)
    warnings.filterwarnings("ignore")
    (args.out / "units").mkdir(parents=True, exist_ok=True)
    for dataset in benchmark_ids():
        for seed in SPLIT_SEEDS:
            path = args.out / "units" / f"{dataset}__s{seed}.json"
            if path.exists() or not claim(path):
                continue
            start = time.perf_counter()
            unit = run_unit(dataset, seed)
            unit["runtime_seconds"] = time.perf_counter() - start
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(unit, sort_keys=True), encoding="utf-8")
            tmp.replace(path)
            release(path)
            print(dataset, seed, f"{unit['runtime_seconds']:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
