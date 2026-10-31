"""Phase 3 U2-side generation per benchmark (dataset, split) (U2 venv only; TEST never read).

Jobs come from ``phase3.py jobs``: inner TRAIN (outer TRAIN minus the stratified 20%
validation carve), validation ids, budget B and the verified converted file. U2's
preprocessor is fitted on inner rows; every sampler is the pinned ml_ugo code, unmodified;
synthetic rows are mapped back to raw space (``u2_pools.inverse_records``).

Pools for the merged method (4 x B minority rows each, fixed Phase 2 settings):
    pool:smote          resample_control("smote")
    pool:u2_native      group alpha 0.5
    pool:u2_flow_gate   alpha 0.5, tau 0.5
Comparators at the shared budget B (minority rows added):
    smote, kmeans_smote, rwo     resample_control (U2's adapters, categorical-aware)
    original_ugo                 paper-derived UGO
    u2                           U2 with the FlowGMM gate; alpha and tau chosen on VALIDATION
                                 by U2's rule, as in U2's own protocol
The in-loop learner of UGO/U2 is U2's logistic regression at default parameters (declared
simplification carried over from Phases 1-2: one generation shared by the five learners).
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

ALPHA, TAU = 0.5, 0.5


def run_job(job: dict[str, Any], bench: Any, config: dict[str, Any]) -> dict[str, Any]:
    import numpy as np
    import pandas as pd
    from portable_ugo.models import fit_estimator, make_estimator  # type: ignore[import-not-found]
    from portable_ugo.preprocessing import (  # type: ignore[import-not-found]
        categorical_columns,
        make_preprocessor,
    )
    from portable_ugo.sampling import (  # type: ignore[import-not-found]
        SAMPLER_DEFAULTS,
        resample_control,
    )
    from portable_ugo.u2 import prepare_u2, run_u2  # type: ignore[import-not-found]
    from portable_ugo.ugo_original import (  # type: ignore[import-not-found]
        OriginalUGOConfig,
        original_ugo,
    )

    dat = Path(job["dat_path"])
    if hashlib.sha256(dat.read_bytes()).hexdigest() != job["dat_sha256"]:
        raise SystemExit(f"{dat}: SHA-256 differs from the job")
    features, target, _ = u2_bridge.read_keel(dat)
    y_all, labels = pd.factorize(target, sort=True)
    positive = int(list(labels).index("positive"))
    y_all = np.asarray(y_all, dtype=np.int64)
    inner = np.asarray(job["inner_ids"], dtype=np.int64)
    validation = np.asarray(job["validation_ids"], dtype=np.int64)
    if set(inner.tolist()) & set(validation.tolist()):
        raise ValueError("inner TRAIN and VALIDATION overlap")
    seed = int(job["split_seed"])
    budget = int(job["budget"])
    pre = make_preprocessor(features.iloc[inner])
    X = pre.fit_transform(features.iloc[inner]).astype(np.float32)
    X_val = pre.transform(features.iloc[validation]).astype(np.float32)
    y, y_val = y_all[inner], y_all[validation]
    counts = {int(c): int((y == c).sum()) for c in np.unique(y)}
    groups = bench._categorical_groups(pre)
    categorical = categorical_columns(pre)
    device = config["DEVICE"]

    def targets(extra: int) -> dict[int, int]:
        return {**counts, positive: counts[positive] + extra}

    def train_round(Xs: Any, ys: Any) -> Any:
        model = make_estimator("logistic_regression", seed, {}, device=device,
                               epochs=config["MLP_EPOCHS"], n_jobs=config["N_JOBS"])
        return fit_estimator(model, Xs, ys)

    def arrays(sampled: Any) -> tuple[Any, Any]:
        to = (lambda t: t.cpu().numpy() if hasattr(t, "cpu") else np.asarray(t))
        return to(sampled.X), to(sampled.y)

    result: dict[str, Any] = {"job": {k: v for k, v in job.items()
                                      if k not in ("inner_ids", "validation_ids")},
                              "outputs": {}, "test_used": False}

    def keep(name: str, Xr: Any, yr: Any, audit: dict[str, Any]) -> None:
        Xr, yr = np.asarray(Xr), np.asarray(yr)
        if not (np.array_equal(Xr[:len(y)], X) and np.array_equal(yr[:len(y)], y)):
            raise ValueError("sampler output does not start with the unchanged real rows")
        Xs, ys = Xr[len(y):], yr[len(y):]
        result["outputs"][name] = {"status": "ok", "n": len(Xs),
                                   "labels": [str(labels[int(c)]) for c in ys],
                                   "records": inverse_records(pre, Xs), "audit": _jsonable(audit)}

    def attempt(name: str, fn: Any) -> None:
        start = time.perf_counter()
        try:
            fn()
        except Exception as error:  # noqa: BLE001  recorded as unavailable, never retried here
            result["outputs"][name] = {"status": "failed",
                                       "reason": f"{type(error).__name__}: {error}"[:500],
                                       "traceback": traceback.format_exc(limit=3)}
        result["outputs"].setdefault(name, {})["seconds"] = time.perf_counter() - start

    for method in ("smote", "kmeans_smote", "rwo"):
        for name, extra in ((f"pool:{method}", 4 * budget), (method, budget)):
            if name == "pool:kmeans_smote" or name == "pool:rwo":
                continue  # the merged pool uses SMOTE and U2 only (Phase 2 design)
            def control(m: str = method, e: int = extra, n: str = name) -> None:
                Xr, yr, audit = resample_control(
                    m, X, y, targets(e), seed, categorical_groups=groups,
                    n_jobs=config["N_JOBS"], parameters=SAMPLER_DEFAULTS[m])
                keep(n, Xr, yr, {"sampler": _jsonable(audit)})

            attempt(name, control)

    def ugo() -> None:
        options = OriginalUGOConfig(max_iterations=config["MAX_ROUNDS"], random_state=seed,
                                    device=device, categorical_columns=categorical,
                                    categorical_projection=bool(categorical))
        sampled = original_ugo(X, y, train_round, options, target_counts=targets(budget))
        keep("original_ugo", *arrays(sampled), {"stop_reason": sampled.stop_reason})

    attempt("original_ugo", ugo)

    prepared_pool = prepare_u2(X, y, seed, targets(4 * budget), {"group_alpha": ALPHA})
    prepared_b = prepare_u2(X, y, seed, targets(budget), {"group_alpha": ALPHA})

    def u2(parameters: dict[str, Any], extra: int, prepared: Any, gate: Any = None) -> Any:
        return run_u2(X, y, train_round, seed=seed, targets=targets(extra),
                      parameters=parameters, max_iterations=config["MAX_ROUNDS"], device=device,
                      categorical_columns=categorical, prepared=prepared, flow_support=gate)

    attempt("pool:u2_native", lambda: keep("pool:u2_native", *arrays(
        u2({"group_alpha": ALPHA}, 4 * budget, prepared_pool)), {"alpha": ALPHA}))
    gates: list[Any] = []

    def flow() -> None:
        dataset = {"X": features, "y": y_all, "row_ids": np.arange(len(y_all), dtype=np.int64)}
        split = {"fit": inner, "validation": validation,
                 "train": np.sort(np.concatenate([inner, validation])),
                 "test": np.empty(0, dtype=np.int64)}
        outer = make_preprocessor(features.iloc[split["train"]])
        outer.fit(features.iloc[split["train"]])
        built, evidence = bench._flow_roles(dataset, split, {"inner": pre, "outer": outer},
                                            seed, config)
        gates.extend(built)
        result["flow_evidence"] = _jsonable(evidence)
        keep("pool:u2_flow_gate", *arrays(u2({"group_alpha": ALPHA, "f1_tau": TAU},
                                             4 * budget, prepared_pool, built[0])),
             {"alpha": ALPHA, "tau": TAU})

    attempt("pool:u2_flow_gate", flow)

    def validation_item(Xs: Any, ys: Any, extra: dict[str, Any]) -> dict[str, Any]:
        model = train_round(Xs, ys)
        probability = bench._positive_probability(model, X_val, positive)
        threshold, score = bench.choose_f1_threshold(y_val == positive, probability)
        m = bench._metrics(y_val == positive, probability, threshold)
        return {**extra, "validation_f1": score, "validation_ap": m["average_precision"],
                "f1_numerator": 2 * m["tp"], "f1_denominator": 2 * m["tp"] + m["fp"] + m["fn"]}

    def u2_alone() -> None:
        if not gates:
            raise RuntimeError("flow gate unavailable")
        best, best_out, tried = None, None, []
        for alpha in config["GROUP_ALPHAS"]:
            for tau in config["GATE_TAUS"]:
                sampled = u2({"group_alpha": alpha, "f1_tau": tau}, budget, prepared_b, gates[0])
                Xr, yr = arrays(sampled)
                item = validation_item(Xr, yr, {"group_alpha": alpha, "f1_tau": tau})
                tried.append(item)
                if bench._better(item, best):
                    best, best_out = item, (Xr, yr)
        assert best is not None and best_out is not None
        keep("u2", *best_out, {"selected": best, "tried": tried})

    attempt("u2", u2_alone)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--only", nargs="*", default=None, help="dataset ids")
    parser.add_argument("--device", default="auto",
                        help="U2 DEVICE; cpu keeps the GPU free for local LLM generation")
    args = parser.parse_args()
    commit = u2_bridge.check_pin()
    bundle_sha = u2_bridge.materialize(u2_bridge.bundle_sources(), args.out / "runtime")
    from portable_ugo import benchmark as bench  # type: ignore[import-not-found]

    config = bench._configuration({"OUTPUT_DIR": str(args.out / "unused"),
                                   "DATA_HOME": str(args.out / "unused"),
                                   "DEVICE": args.device})
    jobs = [j for j in json.loads(args.jobs.read_text(encoding="utf-8"))
            if not args.only or j["dataset_id"] in args.only]
    units = args.out / "units"
    units.mkdir(parents=True, exist_ok=True)
    (args.out / "provenance.json").write_text(json.dumps(
        {"ml_ugo_commit": commit, "bundle_sha256": bundle_sha, "alpha": ALPHA, "tau": TAU,
         "config": _jsonable(config)}, indent=1, sort_keys=True), encoding="utf-8")
    for done, job in enumerate(jobs, start=1):
        path = units / f"{job['dataset_id']}__s{job['split_seed']}.json"
        if not path.exists():
            start = time.perf_counter()
            result = run_job(job, bench, config)
            result["runtime_seconds"] = time.perf_counter() - start
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(result, sort_keys=True, allow_nan=False), encoding="utf-8")
            tmp.replace(path)
            status = {m: (v.get("status"), v.get("n")) for m, v in result["outputs"].items()}
            print(job["dataset_id"], job["split_seed"], status,
                  f"{result['runtime_seconds']:.1f}s", flush=True)
        (args.out / "progress.json").write_text(json.dumps(
            {"planned": len(jobs), "finished": done}), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
