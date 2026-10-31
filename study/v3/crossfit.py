"""Stratified K-fold cross-fitting inside an outer TRAIN (Gate 1 decision 2).

Every Phase 2 tuning choice is fitted on K-1 folds of outer TRAIN and scored on the held-out
fold, over all K folds, so each choice sees every TRAIN minority row once as a held-out row
(the single 20% carve of Phase 1 saw 3-53). Fold membership is ordered by SHA-256 exactly as
``make_split`` orders TEST, so it is deterministic and independent of Python's ``hash``.

Thresholds are cross-fitted too: the decision threshold applied to fold f is chosen (by U2's
rule, ported in ``choose_f1_threshold``) on the out-of-fold scores of the other K-1 folds.
Pooled F1 sums TP/FP/FN over folds. TEST is never an input here.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

from rcqasyn.utils.seeds import derive_seed

K_FOLDS = 5


def crossfit_folds(train: pd.DataFrame, target: str, dataset: str, split_seed: int,
                   k: int = K_FOLDS) -> list[list[int]]:
    """K stratified folds of TRAIN row ids; each class is dealt round-robin in SHA-256 order.

    The round-robin offset carries over between classes so that the extra rows of each class
    do not all land in fold 0.
    """
    seed = derive_seed(split_seed, f"study-v3-crossfit:{dataset}")
    labels = train[target].astype("string").fillna("<MISSING>")
    folds: list[list[int]] = [[] for _ in range(k)]
    offset = 0
    for label in sorted(labels.unique().tolist()):
        group = sorted((int(i) for i, v in zip(labels.index.to_numpy(dtype=np.int64),
                                                  labels.to_numpy(dtype=object), strict=True)
                        if v == label),
                       key=lambda i: hashlib.sha256(f"{seed}:{label}:{i}".encode()).hexdigest())
        if len(group) < k:
            raise ValueError(f"{dataset} s{split_seed}: class {label!r} has {len(group)} TRAIN "
                             f"rows, fewer than {k} folds")
        for position, row in enumerate(group):
            folds[(offset + position) % k].append(row)
        offset += len(group)
    return [sorted(f) for f in folds]


def choose_f1_threshold(y_true: Sequence[int] | np.ndarray,
                        probability: Sequence[float] | np.ndarray) -> tuple[float, float]:
    """U2's rule (ml_ugo@a6710ea benchmark.choose_f1_threshold), ported line for line.

    Candidates are observed score cut points and .5; exact F1 ties prefer the threshold
    closest to .5, then the higher one. Returns (threshold, F1 at that threshold).
    """
    y = np.asarray(y_true, dtype=np.int64)
    p = np.asarray(probability, dtype=np.float64)
    if y.ndim != 1 or p.shape != y.shape or not len(y):
        raise ValueError("Threshold selection requires aligned nonempty vectors")
    positives = int(y.sum())
    if not positives:
        raise ValueError("Threshold selection requires the minority class")
    order = np.argsort(-p, kind="stable")
    ordered = p[order]
    ends = np.r_[np.flatnonzero(ordered[:-1] != ordered[1:]), len(y) - 1]
    cumulative = np.cumsum(y[order])
    at_half = p >= .5
    best = (int(y[at_half].sum()), int(at_half.sum()) + positives, .5)
    for end in ends:
        item = (int(cumulative[end]), int(end) + 1 + positives, float(ordered[end]))
        comparison = item[0] * best[1] - best[0] * item[1]
        if comparison > 0 or (comparison == 0 and
                              (-abs(item[2] - .5), item[2]) > (-abs(best[2] - .5), best[2])):
            best = item
    return best[2], 2 * best[0] / best[1]


def _counts(y: np.ndarray, predicted: np.ndarray) -> dict[str, int]:
    return {"tp": int(((y == 1) & (predicted == 1)).sum()),
            "fp": int(((y == 0) & (predicted == 1)).sum()),
            "fn": int(((y == 1) & (predicted == 0)).sum()),
            "tn": int(((y == 0) & (predicted == 0)).sum())}


def _f1_mcc(c: dict[str, int]) -> tuple[float, float]:
    tp, fp, fn, tn = c["tp"], c["fp"], c["fn"], c["tn"]
    f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0
    denominator = float((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    mcc = (tp * tn - fp * fn) / np.sqrt(denominator) if denominator else 0.0
    return float(f1), float(mcc)


def pooled_scores(folds: list[dict[str, Any]]) -> dict[str, Any]:
    """Pool out-of-fold predictions of one method.

    ``folds`` holds, per fold, ``y`` (0/1) and ``score`` (minority probability) for the
    held-out rows. Returns pooled F1/MCC at the default 0.5 threshold and at the
    cross-fitted threshold, plus the mean per-fold average precision.
    """
    from sklearn.metrics import average_precision_score

    ys = [np.asarray(f["y"], dtype=np.int64) for f in folds]
    ps = [np.asarray(f["score"], dtype=np.float64) for f in folds]
    default = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    tuned = dict(default)
    thresholds = []
    aps = []
    for index, (y, p) in enumerate(zip(ys, ps, strict=True)):
        for key, value in _counts(y, (p >= .5).astype(np.int64)).items():
            default[key] += value
        rest_y = np.concatenate([v for j, v in enumerate(ys) if j != index])
        rest_p = np.concatenate([v for j, v in enumerate(ps) if j != index])
        threshold, _ = choose_f1_threshold(rest_y, rest_p)
        thresholds.append(threshold)
        for key, value in _counts(y, (p >= threshold).astype(np.int64)).items():
            tuned[key] += value
        if 0 < y.sum() < len(y):
            aps.append(float(average_precision_score(y, p)))
    f1_default, mcc_default = _f1_mcc(default)
    f1_tuned, mcc_tuned = _f1_mcc(tuned)
    return {"f1_default": f1_default, "mcc_default": mcc_default, "f1": f1_tuned,
            "mcc": mcc_tuned, "average_precision": float(np.mean(aps)) if aps else None,
            "thresholds": thresholds, "counts_default": default, "counts": tuned,
            "minority_n": int(sum(int(y.sum()) for y in ys)),
            "minority_recall": tuned["tp"] / (tuned["tp"] + tuned["fn"])
            if tuned["tp"] + tuned["fn"] else None}
