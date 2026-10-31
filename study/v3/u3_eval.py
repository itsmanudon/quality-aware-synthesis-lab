"""Phase 3 final evaluation on REAL TEST (U2 venv only; runs only on a frozen protocol).

Reads ``phase3.py curate`` units. For every (method, learner) it follows U2's own protocol
with the pinned ml_ugo code, unmodified:

1. ``make_preprocessor`` fitted on the real inner TRAIN rows; every candidate of
   ``candidate_parameters`` (U2 search spaces, default first, N_CANDIDATES) is fitted on
   inner TRAIN (minus the method's removals) plus the method's synthetic minority rows and
   scored on VALIDATION; U2's rule (``choose_f1_threshold``, then ``_better``) picks the
   candidate and the decision threshold;
2. outer refit: a preprocessor fitted on the real outer TRAIN rows; the chosen candidate is
   fitted on TRAIN (minus removals) plus the same synthetic rows; REAL TEST is scored at
   the chosen threshold.

Declared size policy: an SVM cell whose training set exceeds ``SVM_MAX_ROWS`` rows is
reported unavailable (``SVM_SIZE_LIMIT``); RBF SVC with probability estimates does not finish
on the largest datasets on this machine. ``class-weighted`` adds ``class_weight="balanced"``
(LR, RF, SVM) or ``scale_pos_weight`` (XGBoost) to every candidate; the MLP has no class
weight in U2's code and is reported unavailable for that method.

The protocol SHA-256 recorded at the Gate 2 freeze must match ``protocol.json``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I drops the script directory
import u2_bridge

LEARNERS = ("logistic_regression", "random_forest", "xgboost", "mlp", "svm")
SVM_MAX_ROWS = 20000
HERE = Path(__file__).resolve().parent


def frozen_sha() -> str:
    data = (HERE / "protocol.json").read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def run_unit(unit: dict[str, Any], bench: Any, config: dict[str, Any],
             learners: tuple[str, ...], methods: list[str] | None) -> dict[str, Any]:
    import numpy as np
    import pandas as pd
    from portable_ugo.models import (  # type: ignore[import-not-found]
        candidate_parameters,
        fit_estimator,
        make_estimator,
    )
    from portable_ugo.preprocessing import make_preprocessor  # type: ignore[import-not-found]

    dat = Path(unit["dat_path"])
    if hashlib.sha256(dat.read_bytes()).hexdigest() != unit["dat_sha256"]:
        raise SystemExit(f"{dat}: SHA-256 differs from the unit")
    features, target, _ = u2_bridge.read_keel(dat)
    y_all, labels = pd.factorize(target, sort=True)
    positive = int(list(labels).index("positive"))
    y_all = np.asarray(y_all, dtype=np.int64)
    inner = np.asarray(unit["inner_ids"], dtype=np.int64)
    validation = np.asarray(unit["validation_ids"], dtype=np.int64)
    test = np.asarray(unit["test_ids"], dtype=np.int64)
    train = np.sort(np.concatenate([inner, validation]))
    for a, b in ((inner, validation), (train, test)):
        if set(a.tolist()) & set(b.tolist()):
            raise ValueError("partition overlap")
    by_lower = {str(c).lower(): c for c in features.columns}
    seed = int(unit["split_seed"])
    numeric = [c for c in features.columns if pd.api.types.is_numeric_dtype(features[c].dtype)]
    rows: list[dict[str, Any]] = []

    def frame_of(real_ids: Any, records: list[dict[str, Any]]) -> tuple[Any, Any]:
        real = features.iloc[real_ids].reset_index(drop=True)
        synthetic = pd.DataFrame(records).rename(columns=lambda c: by_lower[str(c).lower()])
        synthetic = synthetic.reindex(columns=list(features.columns))
        for column in numeric:
            synthetic[column] = np.asarray(pd.to_numeric(synthetic[column], errors="coerce"),
                                           dtype=np.float64)
        frame = pd.concat([real.astype({c: object for c in real.columns if c not in numeric}),
                           synthetic], ignore_index=True)
        y = np.concatenate([y_all[real_ids], np.full(len(synthetic), positive, dtype=np.int64)])
        return frame, y

    chosen_methods = [m for m in sorted(unit["methods"]) if not methods or m in methods]
    for method in chosen_methods:
        spec = unit["methods"][method]
        removed = {int(i) for i in spec.get("remove_ids", [])}
        inner_kept = np.asarray([i for i in inner if int(i) not in removed], dtype=np.int64)
        train_kept = np.asarray([i for i in train if int(i) not in removed], dtype=np.int64)
        fit_frame, y_fit = frame_of(inner_kept, spec["add"])
        out_frame, y_out = frame_of(train_kept, spec["add"])
        pre_in = make_preprocessor(features.iloc[inner])
        pre_in.fit(features.iloc[inner])
        pre_out = make_preprocessor(features.iloc[train])
        pre_out.fit(features.iloc[train])
        X_fit = pre_in.transform(fit_frame).astype(np.float32)
        X_val = pre_in.transform(features.iloc[validation]).astype(np.float32)
        X_out = pre_out.transform(out_frame).astype(np.float32)
        X_test = pre_out.transform(features.iloc[test]).astype(np.float32)
        y_val, y_test = y_all[validation] == positive, y_all[test] == positive
        for learner in learners:
            base = {"method": method, "classifier": learner, "train_n": len(y_out),
                    "synthetic_n": len(spec["add"]), "removed_n": len(removed)}
            if learner == "svm" and len(y_out) > SVM_MAX_ROWS:
                rows.append({**base, "status": "unavailable", "reason": "SVM_SIZE_LIMIT"})
                continue
            weighted = bool(spec.get("class_weight"))
            if weighted and learner == "mlp":
                rows.append({**base, "status": "unavailable",
                             "reason": "NO_CLASS_WEIGHT_IN_U2_MLP"})
                continue
            start = time.perf_counter()
            candidates = candidate_parameters(learner, seed, config["N_CANDIDATES"])
            if weighted:
                ratio = float((y_fit != positive).sum()) / max(1, int((y_fit == positive).sum()))
                extra = ({"scale_pos_weight": ratio} if learner == "xgboost"
                         else {"class_weight": "balanced"})
                candidates = [{**c, **extra} for c in candidates]
            best, best_index = None, None
            for index, parameters in enumerate(candidates):
                model = make_estimator(learner, seed, parameters, device=config["DEVICE"],
                                       epochs=config["MLP_EPOCHS"], n_jobs=config["N_JOBS"])
                model = fit_estimator(model, X_fit, y_fit)
                probability = bench._positive_probability(model, X_val, positive)
                threshold, score = bench.choose_f1_threshold(y_val, probability)
                m = bench._metrics(y_val, probability, threshold)
                item = {"threshold": threshold, "validation_f1": score,
                        "validation_ap": m["average_precision"],
                        "f1_numerator": 2 * m["tp"],
                        "f1_denominator": 2 * m["tp"] + m["fp"] + m["fn"]}
                if bench._better(item, best):
                    best, best_index = item, index
            assert best is not None and best_index is not None
            model = make_estimator(learner, seed, candidates[best_index],
                                   device=config["DEVICE"], epochs=config["MLP_EPOCHS"],
                                   n_jobs=config["N_JOBS"])
            model = fit_estimator(model, X_out, y_out)
            probability = bench._positive_probability(model, X_test, positive)
            m = bench._metrics(y_test, probability, best["threshold"])
            rows.append({**base, "status": "ok", "selected_candidate": best_index,
                         "threshold": best["threshold"], "validation_f1": best["validation_f1"],
                         "f1": m["minority_f1"], "mcc": m["mcc"],
                         "average_precision": m["average_precision"],
                         "minority_recall": m["minority_recall"],
                         "minority_precision": m["minority_precision"],
                         "f1_at_0_5": m["f1_at_0_5"], "tp": m["tp"], "fp": m["fp"],
                         "fn": m["fn"], "tn": m["tn"],
                         "seconds": time.perf_counter() - start})
    return {"dataset_id": unit["dataset_id"], "split_seed": seed, "rows": rows,
            "unavailable": unit["unavailable"], "test_minority_n": int(
                (y_all[test] == positive).sum()), "protocol_sha256": frozen_sha()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--units", type=Path, required=True, help="phase3 curate output")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--learners", nargs="+", default=list(LEARNERS))
    parser.add_argument("--methods", nargs="*", default=None)
    parser.add_argument("--only", nargs="*", default=None, help="dataset ids")
    args = parser.parse_args()
    if frozen_sha() != args.expected_protocol_sha256:
        raise SystemExit("protocol.json differs from the frozen SHA-256; refusing TEST")
    commit = u2_bridge.check_pin()
    bundle_sha = u2_bridge.materialize(u2_bridge.bundle_sources(), args.out / "runtime")
    from portable_ugo import benchmark as bench  # type: ignore[import-not-found]

    config = bench._configuration({"OUTPUT_DIR": str(args.out / "unused"),
                                   "DATA_HOME": str(args.out / "unused")})
    (args.out / "units").mkdir(parents=True, exist_ok=True)
    (args.out / "provenance.json").write_text(json.dumps(
        {"ml_ugo_commit": commit, "bundle_sha256": bundle_sha, "protocol_sha256": frozen_sha(),
         "N_CANDIDATES": config["N_CANDIDATES"], "MLP_EPOCHS": config["MLP_EPOCHS"],
         "SVM_MAX_ROWS": SVM_MAX_ROWS, "learners": args.learners}, indent=1), encoding="utf-8")
    files = sorted((args.units / "units").glob("*.json"))
    files = [f for f in files if not args.only or f.name.split("__")[0] in args.only]
    for done, path in enumerate(files, start=1):
        target = args.out / "units" / path.name
        if not target.exists():
            unit = json.loads(path.read_text(encoding="utf-8"))
            start = time.perf_counter()
            result = run_unit(unit, bench, config, tuple(args.learners), args.methods)
            result["runtime_seconds"] = time.perf_counter() - start
            result["curated_unit_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            tmp = target.with_suffix(".tmp")
            tmp.write_text(json.dumps(result, sort_keys=True, default=str), encoding="utf-8")
            tmp.replace(target)
            print(path.stem, len(result["rows"]), f"{result['runtime_seconds']:.0f}s",
                  flush=True)
        (args.out / "progress.json").write_text(json.dumps(
            {"planned": len(files), "finished": done}), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
