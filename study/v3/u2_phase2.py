"""Phase 2 per-fold U2 export: anchor table + U2 pools at fixed defaults (U2 venv only).

For every cross-fit fold job written by ``phase2.py jobs`` (inner = outer TRAIN minus the
held-out fold) this runs the pinned ml_ugo code UNMODIFIED on the inner rows:

* anchor table, for each inner minority row: U2's uMMA difficulty (``calculate_umma`` on the
  probabilities of U2's logistic regression at default parameters, fitted on inner rows),
  its within-class percentile exactly as ``GroupAllocator.allocate`` computes it, and the
  stability of its ``prepare_u2`` support group (KMeans-8, five 80% subsamples);
* pools ``u2_native`` (group alpha 0.5, the AllocationConfig default) and ``u2_flow_gate``
  (alpha 0.5, tau 0.5, the ``run_u2`` default), grown by ``pool_target`` minority rows.

Nothing is chosen on the held-out fold: alpha and tau are fixed defaults (Phase 1 picked them
on validation; that is not repeated inside cross-fitting). The held-out ids are passed to
U2's flow-role bookkeeping only, which records them and checks disjointness but never reads
their rows. TEST ids are never in a job.

Usage (repository root)::

    study/v3/vendor/.venv-u2/Scripts/python.exe -I study/v3/u2_phase2.py \
        --jobs study/v3/runs/phase2/u2/jobs.json --out study/v3/runs/phase2/u2
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I drops the script directory
import u2_bridge
from u2_pools import _jsonable, inverse_records

ALPHA = 0.5
TAU = 0.5


def run_job(job: dict[str, Any], bench: Any, config: dict[str, Any]) -> dict[str, Any]:
    import numpy as np
    import pandas as pd
    import torch  # type: ignore[import-not-found]  (U2 venv only)
    from portable_ugo.models import fit_estimator, make_estimator  # type: ignore[import-not-found]
    from portable_ugo.preprocessing import (  # type: ignore[import-not-found]
        categorical_columns,
        make_preprocessor,
    )
    from portable_ugo.u2 import prepare_u2, run_u2  # type: ignore[import-not-found]
    from portable_ugo.ugo import (  # type: ignore[import-not-found]
        calculate_umma,
        predict_probabilities,
    )
    from scipy.stats import rankdata

    dat = Path(job["dat_path"])
    if hashlib.sha256(dat.read_bytes()).hexdigest() != job["dat_sha256"]:
        raise SystemExit(f"{dat}: SHA-256 differs from the job")
    features, target, _nominal = u2_bridge.read_keel(dat)
    y_all, labels = pd.factorize(target, sort=True)
    positive = int(list(labels).index(job["minority_label"]))
    y_all = np.asarray(y_all, dtype=np.int64)
    inner = np.asarray(job["inner_ids"], dtype=np.int64)
    heldout = np.asarray(job["heldout_ids"], dtype=np.int64)
    if set(inner.tolist()) & set(heldout.tolist()):
        raise ValueError("inner rows and the held-out fold overlap")
    seed = int(job["split_seed"])
    pre = make_preprocessor(features.iloc[inner])
    X = pre.fit_transform(features.iloc[inner]).astype(np.float32)
    y = y_all[inner]
    counts = {int(c): int((y == c).sum()) for c in np.unique(y)}
    targets = {**counts, positive: counts[positive] + int(job["pool_target"])}
    categorical = categorical_columns(pre)
    device = config["DEVICE"]

    def train_round(Xs: Any, ys: Any) -> Any:
        model = make_estimator("logistic_regression", seed, {}, device=device,
                               epochs=config["MLP_EPOCHS"], n_jobs=config["N_JOBS"])
        return fit_estimator(model, Xs, ys)

    result: dict[str, Any] = {"job": {k: v for k, v in job.items()
                                      if k not in ("inner_ids", "heldout_ids")},
                              "alpha": ALPHA, "tau": TAU, "methods": {}, "test_used": False}

    # Anchor table: the same prepared groups feed the U2 pools below.
    prepared = prepare_u2(X, y, seed, targets, {"group_alpha": ALPHA})
    model = train_round(X, y)
    X_t, y_t = torch.as_tensor(X), torch.as_tensor(y)
    umma = calculate_umma(predict_probabilities(model, X_t), y_t).detach().cpu().numpy()
    minority = np.flatnonzero(y == positive)
    percentile = (rankdata(umma[minority], method="average") - 0.5) / len(minority)
    group_of = prepared["row_group_ids"]
    groups = prepared["groups"]
    anchors = {}
    for position, value in zip(minority.tolist(), percentile.tolist(), strict=True):
        group = groups[int(group_of[position])]
        anchors[str(int(inner[position]))] = {
            "umma": float(umma[position]), "difficulty_percentile": float(value),
            "group_id": int(group["id"]), "stability": float(group["stability"]),
            "group_real_support": int(group["real_support"]),
            "group_distinct_coordinates": int(group["distinct_coordinates"])}
    result["anchors"] = anchors

    def keep(method: str, sampled: Any, audit: dict[str, Any]) -> None:
        to = (lambda t: t.cpu().numpy() if hasattr(t, "cpu") else np.asarray(t))
        Xr, yr = to(sampled.X), to(sampled.y)
        if not (np.array_equal(Xr[:len(y)], X) and np.array_equal(yr[:len(y)], y)):
            raise ValueError("sampler output does not start with the unchanged real rows")
        Xs, ys = Xr[len(y):], yr[len(y):]
        records = inverse_records(pre, Xs)
        result["methods"][method] = {
            "status": "ok", "n": len(records), "labels": [str(labels[int(c)]) for c in ys],
            "records": records, "audit": _jsonable(audit)}

    def u2(parameters: dict[str, Any], gate: Any = None) -> Any:
        return run_u2(X, y, train_round, seed=seed, targets=targets, parameters=parameters,
                      max_iterations=config["MAX_ROUNDS"], device=device,
                      categorical_columns=categorical, prepared=prepared, flow_support=gate)

    try:
        sampled = u2({"group_alpha": ALPHA})
        keep("u2_native", sampled, {"stop_reason": sampled.stop_reason})
    except Exception as error:  # noqa: BLE001  recorded as the method's failure
        result["methods"]["u2_native"] = {"status": "failed",
                                          "reason": f"{type(error).__name__}: {error}",
                                          "traceback": traceback.format_exc(limit=3)}
    try:
        dataset = {"X": features, "y": y_all, "row_ids": np.arange(len(y_all), dtype=np.int64)}
        split = {"fit": inner, "validation": heldout,
                 "train": np.sort(np.concatenate([inner, heldout])),
                 "test": np.empty(0, dtype=np.int64)}
        outer = make_preprocessor(features.iloc[split["train"]])
        outer.fit(features.iloc[split["train"]])
        gates, evidence = bench._flow_roles(dataset, split, {"inner": pre, "outer": outer},
                                            seed, config)
        sampled = u2({"group_alpha": ALPHA, "f1_tau": TAU}, gates[0])
        keep("u2_flow_gate", sampled, {"stop_reason": sampled.stop_reason,
                                       "flow_evidence": evidence})
    except Exception as error:  # noqa: BLE001  recorded as the method's failure
        result["methods"]["u2_flow_gate"] = {"status": "failed",
                                             "reason": f"{type(error).__name__}: {error}",
                                             "traceback": traceback.format_exc(limit=3)}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None, help="first N jobs (timing checks)")
    args = parser.parse_args()
    commit = u2_bridge.check_pin()
    bundle_sha = u2_bridge.materialize(u2_bridge.bundle_sources(), args.out / "runtime")
    from portable_ugo import benchmark as bench  # type: ignore[import-not-found]

    config = bench._configuration({"OUTPUT_DIR": str(args.out / "unused"),
                                   "DATA_HOME": str(args.out / "unused")})
    jobs = json.loads(args.jobs.read_text(encoding="utf-8"))[:args.limit]
    units = args.out / "units"
    units.mkdir(parents=True, exist_ok=True)
    (args.out / "provenance.json").write_text(json.dumps(
        {"ml_ugo_commit": commit, "bundle_sha256": bundle_sha, "alpha": ALPHA, "tau": TAU,
         "config": _jsonable(config), "in_loop_learner": "logistic_regression default"},
        indent=1, sort_keys=True), encoding="utf-8")
    for done, job in enumerate(jobs, start=1):
        path = units / f"{job['dataset_id']}__s{job['split_seed']}__f{job['fold']}.json"
        if not path.exists():
            start = time.perf_counter()
            result = run_job(job, bench, config)
            result["runtime_seconds"] = time.perf_counter() - start
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(result, sort_keys=True, allow_nan=False), encoding="utf-8")
            tmp.replace(path)
            status = {m: (v["status"], v.get("n")) for m, v in result["methods"].items()}
            print(job["dataset_id"], job["split_seed"], job["fold"], len(result["anchors"]),
                  status, f"{result['runtime_seconds']:.1f}s", flush=True)
        (args.out / "progress.json").write_text(json.dumps(
            {"planned": len(jobs), "finished": done}), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
