"""Phase 2 five-learner check on cross-fit folds (U2 venv only; TEST never read).

Reads ``phase2_clf.py`` jobs: per (dev dataset, split seed), 5 folds, each with inner and
held-out row ids and the selected minority rows of every design. For every (design, learner)
it uses the pinned ml_ugo code unmodified: ``make_preprocessor`` fitted on the fold's real
inner rows, ``candidate_parameters`` (U2 search spaces, default first, N_CANDIDATES),
``make_estimator``/``fit_estimator``. Every candidate is fitted on each fold's inner rows plus
the design's rows and scored on that fold's held-out rows.

Selection is cross-fitted over folds: for held-out fold f, U2's rule (``choose_f1_threshold``,
then ``_better``: validation F1, then AP) picks the candidate and threshold on the pooled
out-of-fold scores of the other 4 folds; fold f is then scored with that choice. TP/FP/FN
are pooled over the 5 folds. This replaces U2's single validation split, per Gate 1 decision 2.

Usage::

    study/v3/vendor/.venv-u2/Scripts/python.exe -I study/v3/u2_crossfit.py \
        --jobs study/v3/runs/phase2/clf/jobs.json --out study/v3/runs/phase2/clf
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

    folds = job["folds"]
    first = folds[0]
    dat = Path(first["dat_path"])
    if hashlib.sha256(dat.read_bytes()).hexdigest() != first["dat_sha256"]:
        raise SystemExit(f"{dat}: SHA-256 differs from the job")
    features, target, _ = u2_bridge.read_keel(dat)
    y_all, labels = pd.factorize(target, sort=True)
    positive = int(list(labels).index(first["minority_label"]))
    y_all = np.asarray(y_all, dtype=np.int64)
    by_lower = {str(c).lower(): c for c in features.columns}
    seed = int(job["split_seed"])
    names = sorted(set.intersection(*(set(f["augmentations"]) for f in folds)))
    # probs[(name, learner)][candidate][fold] -> held-out minority probabilities
    probs: dict[tuple[str, str], list[list[Any]]] = {}
    y_held: list[Any] = []
    for fold in folds:
        inner = np.asarray(fold["inner_ids"], dtype=np.int64)
        held = np.asarray(fold["heldout_ids"], dtype=np.int64)
        if set(inner.tolist()) & set(held.tolist()):
            raise ValueError("inner and held-out rows overlap")
        real = features.iloc[inner].reset_index(drop=True)
        pre = make_preprocessor(real)
        pre.fit(real)
        X_held = pre.transform(features.iloc[held]).astype(np.float32)
        y_held.append(y_all[held] == positive)
        for name in names:
            synthetic = pd.DataFrame(fold["augmentations"][name]).rename(
                columns=lambda c: by_lower[str(c).lower()])
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
                slot = probs.setdefault((name, learner), [[] for _ in candidates])
                for index, parameters in enumerate(candidates):
                    model = make_estimator(learner, seed, parameters, device=config["DEVICE"],
                                           epochs=config["MLP_EPOCHS"], n_jobs=config["N_JOBS"])
                    model = fit_estimator(model, X, y)
                    slot[index].append(bench._positive_probability(model, X_held, positive))
    rows = []
    for (name, learner), per_candidate in sorted(probs.items()):
        counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
        aps, chosen = [], []
        for f in range(len(folds)):
            rest_y = np.concatenate([y_held[j] for j in range(len(folds)) if j != f])
            best, best_index = None, None
            for index, by_fold in enumerate(per_candidate):
                rest_p = np.concatenate([by_fold[j] for j in range(len(folds)) if j != f])
                threshold, score = bench.choose_f1_threshold(rest_y, rest_p)
                m = bench._metrics(rest_y, rest_p, threshold)
                item = {"threshold": threshold, "validation_f1": score,
                        "validation_ap": m["average_precision"],
                        "f1_numerator": 2 * m["tp"],
                        "f1_denominator": 2 * m["tp"] + m["fp"] + m["fn"]}
                if bench._better(item, best):
                    best, best_index = item, index
            assert best is not None and best_index is not None
            scored = bench._metrics(y_held[f], per_candidate[best_index][f], best["threshold"])
            for key in counts:
                counts[key] += int(scored[key])
            if scored["average_precision"] is not None:
                aps.append(float(scored["average_precision"]))
            chosen.append({"fold": f, "candidate": best_index, "threshold": best["threshold"]})
        tp, fp, fn, tn = counts["tp"], counts["fp"], counts["fn"], counts["tn"]
        denominator = float((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
        rows.append({"method": name, "classifier": learner,
                     "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0,
                     "mcc": (tp * tn - fp * fn) / denominator ** 0.5 if denominator else 0.0,
                     "average_precision": float(np.mean(aps)) if aps else None,
                     "minority_recall": tp / (tp + fn) if tp + fn else None,
                     "counts": counts, "chosen": chosen})
    return {"dataset_id": job["dataset_id"], "split_seed": seed, "rows": rows,
            "designs": names,
            "unavailable": {f"f{i}:{k}": v for i, fold in enumerate(folds)
                            for k, v in fold["unavailable"].items()},
            "test_used": False}


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
