"""Prediction-preserving evaluation and paired, class-conditional bootstrap."""
from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from rcqasyn.metrics.utility import resolve_estimators
from rcqasyn.phase2.common import digest

METRICS = ("f1", "average_precision", "balanced_accuracy", "mcc", "auroc")


def evaluate(train: pd.DataFrame, test: pd.DataFrame, spec: Any, classifier: str,
             *, balanced: bool = False) -> dict[str, Any]:
    """Keep the frozen preprocessing/model specifications and retain predictions."""
    target = spec.target_column
    positive = str(spec.minority_label)
    labels = test[target].astype(str)
    if not set(labels) <= {"positive", "negative"}:
        raise ValueError("unsupported evaluation labels")
    base = {"training_n": len(train), "evaluation_n": len(test),
            "training_class_counts": dict(Counter(train[target].astype(str))),
            "test_positive_n": int((labels == positive).sum()),
            "test_negative_n": int((labels != positive).sum())}
    if not set(train[target].astype(str)) <= {"positive", "negative"}:
        raise ValueError("missing or fabricated training class")
    if train.empty or train[target].nunique() != 2:
        return {**base, "status": "unavailable", "reason": "TRAINING_REQUIRES_BOTH_LITERAL_CLASSES"}
    model = resolve_estimators(42)[classifier]
    if balanced:
        if classifier != "logistic_regression":
            raise ValueError("balanced comparator is logistic regression only")
        model.set_params(class_weight="balanced")
    transforms = []
    if spec.numerical_columns:
        transforms.append(("num", Pipeline([("imputer", SimpleImputer(strategy="median")),
                                           ("scale", StandardScaler())]),
                           list(spec.numerical_columns)))
    if spec.categorical_columns:
        transforms.append(("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")),
                                           ("onehot", OneHotEncoder(handle_unknown="ignore"))]),
                           list(spec.categorical_columns)))
    pipeline = Pipeline([("features", ColumnTransformer(transforms, remainder="drop")),
                         ("model", model)])
    pipeline.fit(train[list(spec.feature_columns)], train[target].astype(str))
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        predicted = pipeline.predict(test[list(spec.feature_columns)]).astype(str)
        probability = pipeline.predict_proba(test[list(spec.feature_columns)])[
            :, list(model.classes_).index(positive)]
    y = (labels == positive).to_numpy(dtype=int)
    p = (predicted == positive).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, p, labels=[0, 1]).ravel().tolist()
    two_classes = len(np.unique(y)) == 2
    values = {"f1": float(f1_score(y, p)),
              "average_precision": float(average_precision_score(y, probability)) if two_classes else None,
              "balanced_accuracy": float(balanced_accuracy_score(y, p)) if two_classes else None,
              "mcc": float(matthews_corrcoef(y, p)),
              "auroc": float(roc_auc_score(y, probability)) if two_classes else None}
    predictions = [{"row_id": int(i), "label": str(label), "predicted_label": str(pred),
                    "y": int(a), "predicted": int(b), "score": float(s)}
                   for i, label, pred, a, b, s in zip(
                       test.index, labels, predicted, y, p, probability, strict=True)]
    return {**base, "status": "ok", "reason": None, **values,
            "pr_auc": values["average_precision"], "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "mcc_degenerate_margin": not bool((tp+fp)*(tp+fn)*(tn+fp)*(tn+fn)),
            "classifier_parameters": model.get_params(), "predictions": predictions,
            "prediction_fingerprint": digest(predictions),
            "recall_wilson95": wilson(tp, tp+fn)}


def wilson(success: int, n: int) -> list[float | None]:
    if not n:
        return [None, None]
    z = 1.959963984540054
    p = success/n
    denominator = 1+z*z/n
    middle = (p+z*z/(2*n))/denominator
    radius = z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/denominator
    return [float(max(0, middle-radius)), float(min(1, middle+radius))]


def aligned(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> None:
    if len({r["row_id"] for r in a}) != len(a):
        raise ValueError("duplicate TEST row identity")
    if [(r["row_id"], r["label"], r["y"]) for r in a] != [
            (r["row_id"], r["label"], r["y"]) for r in b]:
        raise ValueError("paired TEST row/label alignment mismatch")


def stratified_indices(y: np.ndarray, replicates: int, seed: int) -> np.ndarray:
    if replicates < 1 or not np.all(np.isin(y, [0, 1])):
        raise ValueError("invalid bootstrap population/configuration")
    groups = [np.flatnonzero(y == value) for value in [0, 1]]
    if any(not len(group) for group in groups):
        raise ValueError("stratified bootstrap requires both observed classes")
    rng = np.random.default_rng(seed)
    return np.concatenate([rng.choice(g, (replicates, len(g)), replace=True)
                           for g in groups], axis=1).astype(np.int32)


def bootstrap_metrics(predictions: list[dict[str, Any]], indices: np.ndarray) -> dict[str, np.ndarray]:
    """Recompute counts and tie-aware AP for every sampled example population.

    Vectorization changes only execution, not the step-integral AP definition.
    Undefined MCC margins retain NaN here, independently of sklearn's point value 0.
    """
    y = np.array([r["y"] for r in predictions])
    pred = np.array([r["predicted"] for r in predictions])
    score = np.array([r["score"] for r in predictions])
    if indices.ndim != 2 or indices.shape[1] != len(y):
        raise ValueError("foreign bootstrap denominator")
    if np.any(indices < 0) or np.any(indices >= len(y)) or not np.isfinite(score).all():
        raise ValueError("invalid bootstrap indices or predictions")
    truth, guessed = y[indices], pred[indices]
    tp = np.sum((truth == 1) & (guessed == 1), axis=1).astype(float)
    fp = np.sum((truth == 0) & (guessed == 1), axis=1).astype(float)
    fn = np.sum((truth == 1) & (guessed == 0), axis=1).astype(float)
    tn = np.sum((truth == 0) & (guessed == 0), axis=1).astype(float)
    weights = np.zeros((len(indices), len(y)), dtype=float)
    np.add.at(weights, (np.arange(len(indices))[:, None], indices), 1)
    order = np.argsort(-score, kind="stable")
    starts = np.r_[0, np.flatnonzero(np.diff(score[order]))+1]
    positive = np.add.reduceat(weights[:, order]*y[order], starts, axis=1)
    total = np.add.reduceat(weights[:, order], starts, axis=1)
    cumulative_positive = np.cumsum(positive, axis=1)
    cumulative_total = np.cumsum(total, axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        precision = np.divide(cumulative_positive, cumulative_total,
                              out=np.zeros_like(total), where=cumulative_total > 0)
        ap = np.sum(positive*precision, axis=1)/(tp+fn)
        ap[(tp+fn == 0) | (tn+fp == 0)] = np.nan
        denominator = np.sqrt((tp+fp)*(tp+fn)*(tn+fp)*(tn+fn))
        f1 = np.divide(2*tp, 2*tp+fp+fn, out=np.zeros_like(tp), where=2*tp+fp+fn > 0)
        return {"f1": f1, "average_precision": ap,
                "balanced_accuracy": .5*(tp/(tp+fn)+tn/(tn+fp)),
                "mcc": (tp*tn-fp*fn)/denominator}


def interval(values: np.ndarray, confidence: float = .95) -> dict[str, Any]:
    good = values[np.isfinite(values)]
    alpha = (1-confidence)/2
    bounds = [float(v) for v in np.quantile(good, [alpha, 1-alpha])] if len(good) else [None, None]
    return {"lower": bounds[0], "upper": bounds[1], "valid_replicates": len(good),
            "undefined_replicates": len(values)-len(good), "confidence": confidence,
            "method": "stratified paired percentile",
            "status": "ok" if len(good) else "undefined"}
