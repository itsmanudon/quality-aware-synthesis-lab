# pyright: reportArgumentType=false, reportAttributeAccessIssue=false
from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    f1_score,
    matthews_corrcoef,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from rcqasyn.datasets import DatasetDefinition

SUPPORTED_CLASSIFIERS = ("logistic_regression", "random_forest")


def resolve_estimators(seed: int = 0) -> dict[str, Any]:
    """Construct the frozen M1 estimators for execution and policy identity."""
    return {
        # liblinear is stable for the very small minority classes in the pilot
        # and avoids the overflow warnings seen with the default lbfgs solver
        # on the large integer-valued page-blocks features.
        "logistic_regression": LogisticRegression(max_iter=300, random_state=seed, solver="liblinear"),
        "random_forest": RandomForestClassifier(n_estimators=50, random_state=seed),
    }


def utility_metrics(real_train: pd.DataFrame, real_test: pd.DataFrame, synthetic: pd.DataFrame, spec: DatasetDefinition, *, seed: int = 0, classifiers: tuple[str, ...] = SUPPORTED_CLASSIFIERS) -> dict[str, Any]:
    unknown = sorted(set(classifiers) - set(SUPPORTED_CLASSIFIERS))
    if unknown:
        raise ValueError(f"unsupported classifiers: {unknown}; supported: {list(SUPPORTED_CLASSIFIERS)}")
    if not classifiers:
        raise ValueError("at least one classifier must be configured")
    result: dict[str, Any] = {"status": "ok", "TRTR": {}, "TSTR": {}}
    models = resolve_estimators(seed)
    for name in classifiers:
        model = models[name]
        result["TRTR"][name] = _fit_score(real_train, real_test, spec, model)
        result["TSTR"][name] = _fit_score(synthetic, real_test, spec, model)
    return result


def _fit_score(train: pd.DataFrame, test: pd.DataFrame, spec: DatasetDefinition, model: Any) -> dict[str, Any]:
    if train.empty or test.empty:
        return {"status": "empty", "f1": None, "average_precision": None, "pr_auc": None, "mcc": None, "balanced_accuracy": None, "auroc": None}
    target = spec.target_column
    x_train = train[list(spec.feature_columns)]
    y_train = train[target].astype(str)
    x_test = test[list(spec.feature_columns)]
    y_test = test[target].astype(str)
    if y_train.nunique() < 2 or y_test.nunique() < 1:
        return {"status": "undefined", "reason": "insufficient classes", "f1": None, "average_precision": None, "pr_auc": None, "mcc": None, "balanced_accuracy": None, "auroc": None}
    numeric = list(spec.numerical_columns)
    categorical = list(spec.categorical_columns)
    transformers: list[tuple[str, Any, list[str]]] = []
    if numeric:
        transformers.append(("num", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), numeric))
    if categorical:
        transformers.append(("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), categorical))
    pipeline = Pipeline([("features", ColumnTransformer(transformers=transformers, remainder="drop")), ("model", model)])
    try:
        pipeline.fit(x_train, y_train)
        # Some NumPy/BLAS combinations emit benign matmul overflow warnings
        # while sklearn consumes finite, standardized values.  Inputs and
        # coefficients are checked by sklearn; keep the pilot report readable.
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*matmul.*")
            predicted = pipeline.predict(x_test)
            probabilities = pipeline.predict_proba(x_test) if hasattr(pipeline, "predict_proba") else None
    except (ValueError, TypeError) as error:
        return {"status": "undefined", "reason": str(error), "f1": None, "average_precision": None, "pr_auc": None, "mcc": None, "balanced_accuracy": None, "auroc": None}
    positive = _positive_label(spec, y_train)
    binary = y_test == positive
    predicted_binary = predicted.astype(str) == positive
    if probabilities is not None and hasattr(pipeline[-1], "classes_"):
        classes = list(pipeline[-1].classes_)
        probability = probabilities[:, classes.index(positive)] if positive in classes else None
    else:
        probability = None
    metric_reasons: dict[str, str] = {}
    result: dict[str, Any] = {
        "status": "ok", "f1": _metric(lambda: f1_score(binary, predicted_binary) if y_train.nunique() == 2 else f1_score(y_test, predicted, average="weighted"), reasons=metric_reasons, name="f1"),
        "average_precision": _metric(lambda: average_precision_score(binary, probability), reasons=metric_reasons, name="average_precision") if probability is not None and binary.nunique() > 1 else None,
        "mcc": _metric(lambda: matthews_corrcoef(y_test, predicted), reasons=metric_reasons, name="mcc"),
        "balanced_accuracy": _metric(lambda: balanced_accuracy_score(y_test, predicted), reasons=metric_reasons, name="balanced_accuracy"),
        "auroc": _metric(lambda: roc_auc_score(binary, probability), reasons=metric_reasons, name="auroc") if probability is not None and binary.nunique() > 1 else None,
    }
    result["pr_auc"] = result["average_precision"]
    if result["average_precision"] is None:
        metric_reasons.setdefault("average_precision", "undefined_for_evaluation_population")
        metric_reasons["pr_auc"] = metric_reasons["average_precision"]
    if result["auroc"] is None:
        metric_reasons.setdefault("auroc", "undefined_for_evaluation_population")
    result["metric_reasons"] = metric_reasons
    return result


def _positive_label(spec: DatasetDefinition, y: pd.Series) -> str:
    if spec.minority_label is not None and str(spec.minority_label) in set(y):
        return str(spec.minority_label)
    return max(y.unique().tolist())


def _metric(fn: Any, *, reasons: dict[str, str] | None = None, name: str = "") -> float | None:
    try:
        value = float(fn())
        if not np.isfinite(value) and reasons is not None:
            reasons[name] = "nonfinite"
        return value if np.isfinite(value) else None
    except (ValueError, TypeError, ZeroDivisionError) as error:
        if reasons is not None:
            reasons[name] = f"metric_exception:{type(error).__name__}: {error}"
        return None
