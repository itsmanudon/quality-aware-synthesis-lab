"""Phase 1 classifier ablation with U2's five learners (U2 venv only; VALIDATION only).

Reads ``phase1_clf.py`` jobs. For every (unit, training set, learner) it uses the pinned
ml_ugo code unmodified: ``make_preprocessor`` fitted on the real inner TRAIN rows (synthetic
rows are transformed, as U2 does), ``candidate_parameters`` (U2 search spaces, default
first, N_CANDIDATES), ``make_estimator``/``fit_estimator``, ``choose_f1_threshold`` and
U2's selection rule (validation F1, then AP). Selection and scoring use the two halves of
VALIDATION as a 2-fold cross-fit: choose parameters and threshold on one half, score the
other, then swap. No outer refit and no TEST: a declared Phase 1 deviation from U2's own
protocol (which refits on outer TRAIN and scores TEST).

Usage::

    study/v3/vendor/.venv-u2/Scripts/python.exe -I study/v3/u2_classifiers.py \
        --jobs study/v3/runs/phase1/clf/jobs.json --out study/v3/runs/phase1/clf
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


def run_job(job: dict[str, Any], bench: Any, config: dict[str, Any],
            learners: tuple[str, ...]) -> dict[str, Any]:
    import numpy as np
    import pandas as pd
    from portable_ugo.models import (  # type: ignore[import-not-found]
        candidate_parameters,
        fit_estimator,
        make_estimator,
    )
    from portable_ugo.preprocessing import make_preprocessor  # type: ignore[import-not-found]

    dat = Path(job["dat_path"])
    if hashlib.sha256(dat.read_bytes()).hexdigest() != job["dat_sha256"]:
        raise SystemExit(f"{dat}: SHA-256 differs from the job")
    features, target, _ = u2_bridge.read_keel(dat)
    y_all, labels = pd.factorize(target, sort=True)
    positive = int(list(labels).index(job["minority_label"]))
    y_all = np.asarray(y_all, dtype=np.int64)
    by_lower = {str(c).lower(): c for c in features.columns}
    inner = np.asarray(job["inner_ids"], dtype=np.int64)
    halves = {"a": np.asarray(job["half_a_ids"], dtype=np.int64),
              "b": np.asarray(job["half_b_ids"], dtype=np.int64)}
    real = features.iloc[inner].reset_index(drop=True)
    pre = make_preprocessor(real)
    pre.fit(real)
    X_half = {k: pre.transform(features.iloc[v]).astype(np.float32) for k, v in halves.items()}
    y_half = {k: y_all[v] == positive for k, v in halves.items()}
    seed = int(job["split_seed"])
    rows: list[dict[str, Any]] = []
    for name, records in job["augmentations"].items():
        synthetic = pd.DataFrame(records).rename(columns=lambda c: by_lower[str(c).lower()])
        synthetic = synthetic.reindex(columns=list(features.columns))
        for column in features.columns:
            if pd.api.types.is_numeric_dtype(features[column].dtype):
                synthetic[column] = np.asarray(synthetic[column], dtype=np.float64)
        frame = pd.concat([real.astype({c: object for c in real.columns
                                        if not pd.api.types.is_numeric_dtype(real[c].dtype)}),
                           synthetic], ignore_index=True)
        X = pre.transform(frame).astype(np.float32)
        y = np.concatenate([y_all[inner], np.full(len(synthetic), positive, dtype=np.int64)])
        for learner in learners:
            candidates = candidate_parameters(learner, seed, config["N_CANDIDATES"])
            probs: dict[str, list[Any]] = {"a": [], "b": []}
            for parameters in candidates:
                model = make_estimator(learner, seed, parameters, device=config["DEVICE"],
                                       epochs=config["MLP_EPOCHS"], n_jobs=config["N_JOBS"])
                model = fit_estimator(model, X, y)
                for k, collected in probs.items():
                    collected.append(bench._positive_probability(model, X_half[k], positive))
            for select, evaluate in (("a", "b"), ("b", "a")):
                best, best_index = None, None
                for index, probability in enumerate(probs[select]):
                    threshold, score = bench.choose_f1_threshold(y_half[select], probability)
                    m = bench._metrics(y_half[select], probability, threshold)
                    item = {"threshold": threshold, "validation_f1": score,
                            "validation_ap": m["average_precision"],
                            "f1_numerator": 2 * m["tp"],
                            "f1_denominator": 2 * m["tp"] + m["fp"] + m["fn"]}
                    if bench._better(item, best):
                        best, best_index = item, index
                assert best is not None and best_index is not None
                scored = bench._metrics(y_half[evaluate], probs[evaluate][best_index],
                                        best["threshold"])
                rows.append({"method": name, "classifier": learner, "select_half": select,
                             "evaluate_half": evaluate, "selected_candidate": best_index,
                             "selected_parameters": candidates[best_index],
                             "threshold": best["threshold"], "select_f1": best["validation_f1"],
                             "f1": scored["minority_f1"], "average_precision":
                             scored["average_precision"], "mcc": scored["mcc"],
                             "minority_recall": scored["minority_recall"],
                             "train_n": len(y), "synthetic_n": len(synthetic)})
    return {"dataset_id": job["dataset_id"], "split_seed": seed, "budget": job["budget"],
            "unavailable": job["unavailable"], "rows": rows, "test_used": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--learners", nargs="+", default=list(LEARNERS))
    parser.add_argument("--limit", type=int, default=None, help="first N jobs (timing checks)")
    args = parser.parse_args()
    commit = u2_bridge.check_pin()
    bundle_sha = u2_bridge.materialize(u2_bridge.bundle_sources(), args.out / "runtime")
    from portable_ugo import benchmark as bench  # type: ignore[import-not-found]

    config = bench._configuration({"OUTPUT_DIR": str(args.out / "unused"),
                                   "DATA_HOME": str(args.out / "unused")})
    (args.out / "provenance.json").write_text(json.dumps(
        {"ml_ugo_commit": commit, "bundle_sha256": bundle_sha,
         "N_CANDIDATES": config["N_CANDIDATES"], "MLP_EPOCHS": config["MLP_EPOCHS"],
         "DEVICE": config["DEVICE"], "learners": args.learners}, indent=1), encoding="utf-8")
    jobs = json.loads(args.jobs.read_text(encoding="utf-8"))[:args.limit]
    units = args.out / "units"
    units.mkdir(parents=True, exist_ok=True)
    for done, job in enumerate(jobs, start=1):
        path = units / f"{job['dataset_id']}__s{job['split_seed']}.json"
        if not path.exists():
            start = time.perf_counter()
            result = run_job(job, bench, config, tuple(args.learners))
            result["runtime_seconds"] = time.perf_counter() - start
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(result, sort_keys=True, default=str), encoding="utf-8")
            tmp.replace(path)
            print(job["dataset_id"], job["split_seed"], len(result["rows"]),
                  f"{result['runtime_seconds']:.1f}s", flush=True)
        (args.out / "progress.json").write_text(json.dumps({"planned": len(jobs),
                                                            "finished": done}), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
