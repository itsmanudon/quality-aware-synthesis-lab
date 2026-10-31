"""Export U2 / UGO / U2-side SMOTE candidate pools for Phase 1 dev splits (U2 venv only).

Runs inside ``study/v3/vendor/.venv-u2`` (imports nothing from ``rcqasyn``). For every job
written by ``study/v3/phase1_u2.py jobs`` it fits U2's own preprocessor on the job's inner
TRAIN rows, runs the pinned ml_ugo samplers UNMODIFIED, and maps the synthetic rows back to
raw feature space (numeric: the fitted StandardScaler inverse; categorical: the one-hot
argmax). VALIDATION rows are used only as U2 itself uses them: to pick U2's group alpha and
flow-gate tau by validation minority F1. TEST rows are never read: the job carries no TEST
identities, and U2's flow-role check is given an empty TEST set.

Methods (U2 names): smote, kmeans_smote, rwo (``resample_control``), original_ugo,
u2_native (group alpha chosen on validation) and u2_flow_gate (that alpha, tau chosen on
validation). The in-loop learner is U2's logistic regression at its default (candidate 0)
parameters, because U2's uncertainty-guided methods need a fitted learner; this is a
declared Phase 1 simplification, not U2's per-classifier selection. Targets: the minority
class is grown by the job's ``pool_target`` rows (4 x budget), the majority is unchanged.

Usage (repository root)::

    study/v3/vendor/.venv-u2/Scripts/python.exe -I study/v3/u2_pools.py \
        --jobs study/v3/runs/phase1/u2-pools/jobs.json --out study/v3/runs/phase1/u2-pools
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

METHODS = ("smote", "kmeans_smote", "rwo", "original_ugo", "u2_native", "u2_flow_gate")


def _jsonable(value: Any) -> Any:
    import numpy as np

    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def inverse_records(pre: Any, matrix: Any) -> list[dict[str, Any]]:
    """Raw-space records from U2's preprocessed rows (no rounding, no clipping)."""
    import numpy as np

    if len(matrix) == 0:
        # A sampler that accepted nothing yields an empty pool (n=0), not a failure;
        # sklearn's inverse_transform refuses zero rows.
        return []
    columns = pre.named_steps["columns"]
    out: dict[str, Any] = {}
    numeric_names = list(columns.transformers_[0][2])
    block = columns.output_indices_["numeric"]
    if numeric_names:
        scaler = columns.named_transformers_["numeric"].named_steps["scale"]
        values = scaler.inverse_transform(np.asarray(matrix[:, block], dtype=np.float64))
        for i, name in enumerate(numeric_names):
            out[name] = values[:, i]
    categorical_names = list(columns.transformers_[1][2])
    if categorical_names:
        encoder = columns.named_transformers_["categorical"].named_steps["encode"]
        start = columns.output_indices_["categorical"].start
        for name, categories in zip(categorical_names, encoder.categories_, strict=True):
            part = np.asarray(matrix[:, start:start + len(categories)], dtype=np.float64)
            start += len(categories)
            # U2 copies whole one-hot blocks from a real partner; anything else is recorded
            # as non-one-hot (None) rather than coerced to the nearest category.
            exact = np.isclose(part.sum(axis=1), 1) & np.isclose(part.max(axis=1), 1)
            out[name] = [str(categories[int(np.argmax(r))]) if ok else None
                         for r, ok in zip(part, exact, strict=True)]
    names = numeric_names + categorical_names
    return [{n: _jsonable(out[n][i]) for n in names} for i in range(len(matrix))]


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
    features, target, _nominal = u2_bridge.read_keel(dat)
    y_all, labels = pd.factorize(target, sort=True)
    positive = int(list(labels).index(job["minority_label"]))
    y_all = np.asarray(y_all, dtype=np.int64)
    inner = np.asarray(job["inner_ids"], dtype=np.int64)
    validation = np.asarray(job["validation_ids"], dtype=np.int64)
    if set(inner.tolist()) & set(validation.tolist()):
        raise ValueError("inner TRAIN and VALIDATION overlap")
    seed = int(job["split_seed"])
    pre = make_preprocessor(features.iloc[inner])
    X = pre.fit_transform(features.iloc[inner]).astype(np.float32)
    X_val = pre.transform(features.iloc[validation]).astype(np.float32)
    y, y_val = y_all[inner], y_all[validation]
    counts = {int(c): int((y == c).sum()) for c in np.unique(y)}
    targets = {**counts, positive: counts[positive] + int(job["pool_target"])}
    groups = bench._categorical_groups(pre)
    categorical = categorical_columns(pre)
    device = config["DEVICE"]

    def train_round(Xs: Any, ys: Any) -> Any:
        model = make_estimator("logistic_regression", seed, {}, device=device,
                               epochs=config["MLP_EPOCHS"], n_jobs=config["N_JOBS"])
        return fit_estimator(model, Xs, ys)

    def validation_item(Xs: Any, ys: Any, extra: dict[str, Any]) -> dict[str, Any]:
        model = train_round(Xs, ys)
        probability = bench._positive_probability(model, X_val, positive)
        threshold, score = bench.choose_f1_threshold(y_val == positive, probability)
        m = bench._metrics(y_val == positive, probability, threshold)
        return {**extra, "validation_f1": score, "validation_ap": m["average_precision"],
                "f1_numerator": 2 * m["tp"], "f1_denominator": 2 * m["tp"] + m["fp"] + m["fn"],
                "threshold": threshold}

    def synthetic(Xr: Any, yr: Any) -> tuple[Any, Any]:
        Xr, yr = np.asarray(Xr), np.asarray(yr)
        if not (np.array_equal(Xr[:len(y)], X) and np.array_equal(yr[:len(y)], y)):
            raise ValueError("sampler output does not start with the unchanged real rows")
        return Xr[len(y):], yr[len(y):]

    result: dict[str, Any] = {"job": {k: v for k, v in job.items()
                                      if k not in ("inner_ids", "validation_ids")},
                              "targets": targets, "positive_code": positive, "methods": {}}

    def keep(method: str, Xr: Any, yr: Any, audit: dict[str, Any]) -> None:
        Xs, ys = synthetic(Xr, yr)
        records = inverse_records(pre, Xs)
        result["methods"][method] = {
            "status": "ok", "n": len(records), "labels": [str(labels[int(c)]) for c in ys],
            "records": records, "audit": _jsonable(audit)}

    for method in ("smote", "kmeans_smote", "rwo"):
        try:
            Xr, yr, audit = resample_control(method, X, y, targets, seed, categorical_groups=groups,
                                             n_jobs=config["N_JOBS"],
                                             parameters=SAMPLER_DEFAULTS[method])
            keep(method, Xr, yr, audit)
        except Exception as error:  # noqa: BLE001  any sampler failure is recorded, never retried
            result["methods"][method] = {"status": "failed",
                                         "reason": f"{type(error).__name__}: {error}"}
    try:
        options = OriginalUGOConfig(max_iterations=config["MAX_ROUNDS"], random_state=seed,
                                    device=device, categorical_columns=categorical,
                                    categorical_projection=bool(categorical))
        sampled = original_ugo(X, y, train_round, options, target_counts=targets)
        keep("original_ugo", sampled.X.cpu().numpy() if hasattr(sampled.X, "cpu") else sampled.X,
             sampled.y.cpu().numpy() if hasattr(sampled.y, "cpu") else sampled.y,
             {"stop_reason": sampled.stop_reason})
    except Exception as error:  # noqa: BLE001  recorded as the method's failure
        result["methods"]["original_ugo"] = {"status": "failed",
                                             "reason": f"{type(error).__name__}: {error}"}

    def u2(sampler: dict[str, Any], prepared: Any, gate: Any = None) -> Any:
        return run_u2(X, y, train_round, seed=seed, targets=targets, parameters=sampler,
                      max_iterations=config["MAX_ROUNDS"], device=device,
                      categorical_columns=categorical, prepared=prepared, flow_support=gate)

    def arrays(sampled: Any) -> tuple[Any, Any]:
        to = (lambda t: t.cpu().numpy() if hasattr(t, "cpu") else np.asarray(t))
        return to(sampled.X), to(sampled.y)

    try:
        prepared = prepare_u2(X, y, seed, targets, {"group_alpha": config["GROUP_ALPHAS"][0]})
        best, best_sampled, tried = None, None, []
        for alpha in config["GROUP_ALPHAS"]:
            sampled = u2({"group_alpha": alpha}, prepared)
            Xr, yr = arrays(sampled)
            item = validation_item(Xr, yr, {"group_alpha": alpha,
                                            "stop_reason": sampled.stop_reason})
            tried.append(item)
            if bench._better(item, best):
                best, best_sampled = item, (Xr, yr)
        assert best is not None and best_sampled is not None
        keep("u2_native", *best_sampled, {"selected": best, "tried": tried})
        dataset = {"X": features, "y": y_all, "row_ids": np.arange(len(y_all), dtype=np.int64)}
        split = {"fit": inner, "validation": validation,
                 "train": np.sort(np.concatenate([inner, validation])),
                 "test": np.empty(0, dtype=np.int64)}
        outer = make_preprocessor(features.iloc[split["train"]])
        outer.fit(features.iloc[split["train"]])
        gates, evidence = bench._flow_roles(dataset, split, {"inner": pre, "outer": outer},
                                            seed, config)
        gbest, gbest_sampled, gtried = None, None, []
        for tau in config["GATE_TAUS"]:
            sampled = u2({"group_alpha": best["group_alpha"], "f1_tau": tau}, prepared, gates[0])
            Xr, yr = arrays(sampled)
            item = validation_item(Xr, yr, {"group_alpha": best["group_alpha"], "f1_tau": tau,
                                            "stop_reason": sampled.stop_reason})
            gtried.append(item)
            if bench._better(item, gbest):
                gbest, gbest_sampled = item, (Xr, yr)
        assert gbest is not None and gbest_sampled is not None
        keep("u2_flow_gate", *gbest_sampled, {"selected": gbest, "tried": gtried,
                                              "flow_evidence": evidence})
    except Exception as error:  # noqa: BLE001  recorded as the method's failure
        for method in ("u2_native", "u2_flow_gate"):
            result["methods"].setdefault(method, {
                "status": "failed", "reason": f"{type(error).__name__}: {error}",
                "traceback": traceback.format_exc(limit=3)})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    commit = u2_bridge.check_pin()
    bundle_sha = u2_bridge.materialize(u2_bridge.bundle_sources(), args.out / "runtime")
    from portable_ugo import benchmark as bench  # type: ignore[import-not-found]

    config = bench._configuration({"OUTPUT_DIR": str(args.out / "unused"),
                                   "DATA_HOME": str(args.out / "unused")})
    jobs = json.loads(args.jobs.read_text(encoding="utf-8"))
    units = args.out / "units"
    units.mkdir(parents=True, exist_ok=True)
    provenance = {"ml_ugo_commit": commit, "bundle_sha256": bundle_sha,
                  "notebook_sha256": hashlib.sha256(u2_bridge.NOTEBOOK.read_bytes()).hexdigest(),
                  "config": _jsonable(config), "in_loop_learner": "logistic_regression default"}
    (args.out / "provenance.json").write_text(json.dumps(provenance, indent=1, sort_keys=True),
                                              encoding="utf-8")
    for done, job in enumerate(jobs, start=1):
        path = units / f"{job['dataset_id']}__s{job['split_seed']}.json"
        if not path.exists():
            start = time.perf_counter()
            result = run_job(job, bench, config)
            result["runtime_seconds"] = time.perf_counter() - start
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(result, sort_keys=True, allow_nan=False), encoding="utf-8")
            tmp.replace(path)
            status = {m: (v["status"], v.get("n")) for m, v in result["methods"].items()}
            print(job["dataset_id"], job["split_seed"], status,
                  f"{result['runtime_seconds']:.1f}s", flush=True)
        (args.out / "progress.json").write_text(json.dumps(
            {"planned": len(jobs), "finished": done}), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
