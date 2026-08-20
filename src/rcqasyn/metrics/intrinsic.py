# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportCallIssue=false, reportOperatorIssue=false
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy.spatial.distance import jensenshannon
from scipy.stats import entropy, ks_2samp, wasserstein_distance

from rcqasyn.datasets import DatasetDefinition


def intrinsic_metrics(real_train: pd.DataFrame, synthetic: pd.DataFrame, spec: DatasetDefinition) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "ok", "numeric": {}, "categorical": {}, "correlations": {}, "diversity": {}}
    for column in spec.numerical_columns:
        real = pd.to_numeric(real_train[column], errors="coerce").dropna().to_numpy(dtype=float)
        synth = pd.to_numeric(synthetic[column], errors="coerce").dropna().to_numpy(dtype=float) if column in synthetic else np.array([])
        result["numeric"][column] = _numeric(real, synth)
    for column in [*spec.categorical_columns, spec.target_column]:
        result["categorical"][column] = _categorical(real_train[column], synthetic[column] if column in synthetic else pd.Series(dtype=object))
    for method in ("pearson", "spearman"):
        result["correlations"][method] = _correlation_error(real_train, synthetic, spec, method)
    result["diversity"] = _diversity(synthetic, real_train, spec)
    result["class_conditional"] = _class_conditional(real_train, synthetic, spec)
    return result


def _class_conditional(real: pd.DataFrame, synthetic: pd.DataFrame, spec: DatasetDefinition) -> dict[str, Any]:
    if spec.target_column not in real or spec.target_column not in synthetic:
        return {"status": "empty", "classes": {}}
    classes = sorted(set(real[spec.target_column].dropna().astype(str)) | set(synthetic[spec.target_column].dropna().astype(str)))
    output: dict[str, Any] = {}
    for label in classes:
        r = real[real[spec.target_column].astype(str) == label]
        s = synthetic[synthetic[spec.target_column].astype(str) == label]
        synthetic_count = len(s)
        duplicate_count = _duplicate_summary(s)["exact_duplicate_count"]
        output[label] = {
            "status": "ok" if len(r) > 0 and synthetic_count > 0 else "empty",
            "real_count": len(r),
            "synthetic_count": synthetic_count,
            "exact_duplicate_count": duplicate_count,
            "exact_duplicate_rate": duplicate_count / synthetic_count if synthetic_count else None,
            "numeric": {column: _numeric(pd.to_numeric(r[column], errors="coerce").dropna().to_numpy(dtype=float), pd.to_numeric(s[column], errors="coerce").dropna().to_numpy(dtype=float)) for column in spec.numerical_columns},
            "categorical": {column: _categorical(r[column], s[column]) for column in [*spec.categorical_columns]},
        }
    return {"status": "ok" if any(item["status"] == "ok" for item in output.values()) else "empty", "classes": output}


def _numeric(real: np.ndarray, synth: np.ndarray) -> dict[str, Any]:
    if not len(real) or not len(synth):
        return {"status": "empty", "ks": None, "ks_statistic": None, "wasserstein": None, "wasserstein_distance": None}
    if np.all(real == real[0]) and np.all(synth == synth[0]):
        ks = float(ks_2samp(real, synth).statistic)
        distance = float(abs(real[0] - synth[0]))
        return {"status": "degenerate", "ks": ks, "ks_statistic": ks, "wasserstein": distance, "wasserstein_distance": distance}
    ks = float(ks_2samp(real, synth).statistic)
    distance = float(wasserstein_distance(real, synth))
    return {"status": "ok", "ks": ks, "ks_statistic": ks, "wasserstein": distance, "wasserstein_distance": distance}


def _categorical(real: pd.Series, synth: pd.Series) -> dict[str, Any]:
    real_values = real.dropna().astype(str)
    synth_values = synth.dropna().astype(str)
    if not len(real_values) or not len(synth_values):
        return {"status": "empty", "tvd": None, "jsd": None, "jensen_shannon_divergence": None}
    keys = sorted(set(real_values) | set(synth_values))
    rp = np.array([float((real_values == key).mean()) for key in keys])
    sp = np.array([float((synth_values == key).mean()) for key in keys])
    jsd = float(jensenshannon(rp, sp, base=2) ** 2)
    return {"status": "ok", "tvd": float(0.5 * np.abs(rp - sp).sum()), "jsd": jsd, "jensen_shannon_divergence": jsd}


def _correlation_error(real: pd.DataFrame, synth: pd.DataFrame, spec: DatasetDefinition, method: str) -> dict[str, Any]:
    cols = list(spec.numerical_columns)
    if len(cols) < 2 or synth.empty:
        return {"status": "empty", "mean_abs_error": None}
    r = real[cols].apply(pd.to_numeric, errors="coerce").corr(method=method)
    s = synth[cols].apply(pd.to_numeric, errors="coerce").corr(method=method)
    pairs = [(a, b) for i, a in enumerate(cols) for b in cols[i + 1 :]]
    values = [abs(float(r.loc[a, b]) - float(s.loc[a, b])) for a, b in pairs if pd.notna(r.loc[a, b]) and pd.notna(s.loc[a, b])]
    return {"status": "ok" if values else "degenerate", "mean_abs_error": float(np.mean(values)) if values else None}


def _diversity(frame: pd.DataFrame, reference: pd.DataFrame, spec: DatasetDefinition) -> dict[str, Any]:
    if frame.empty:
        return {"status": "empty", "rows": 0, "unique_rows": 0, "exact_duplicate_count": 0, "exact_duplicate_rate": None, "duplicate_rate": None, "categorical_entropy": {}, "numeric_variance_ratio": {}, "unique_categorical_combinations": None}
    duplicate_summary = _duplicate_summary(frame)
    duplicate_count = duplicate_summary["exact_duplicate_count"]
    result: dict[str, Any] = {
        "status": "ok", "rows": len(frame), "unique_rows": duplicate_summary["unique_count"],
        "exact_duplicate_count": duplicate_count, "exact_duplicate_rate": duplicate_count / len(frame), "duplicate_rate": duplicate_count / len(frame),
        "categorical_entropy": {}, "numeric_variance_ratio": {},
        "unique_categorical_combinations": int(frame[list(spec.categorical_columns)].astype(str).drop_duplicates().shape[0]) if spec.categorical_columns else None,
    }
    for column in spec.categorical_columns:
        counts = frame[column].dropna().astype(str).value_counts(normalize=True)
        result["categorical_entropy"][column] = float(entropy(counts.to_numpy(), base=2)) if len(counts) else None
    for column in spec.numerical_columns:
        real_var = pd.to_numeric(reference[column], errors="coerce").var(ddof=1)
        synth_var = pd.to_numeric(frame[column], errors="coerce").var(ddof=1)
        result["numeric_variance_ratio"][column] = None if pd.isna(synth_var) else float(synth_var / real_var) if real_var and not pd.isna(real_var) else None
    return result


def _canonical_rows(frame: pd.DataFrame) -> pd.Series:
    """Canonical row strings shared by global and class-conditional duplicate metrics."""
    if frame.empty:
        return pd.Series(dtype="string", index=frame.index)
    canonical = frame.astype(object).where(frame.notna(), "<NULL>").astype(str).agg("|".join, axis=1)
    if not isinstance(canonical, pd.Series):
        raise TypeError("canonical row aggregation did not produce a Series")
    return canonical


def _duplicate_summary(frame: pd.DataFrame) -> dict[str, int]:
    canonical = _canonical_rows(frame)
    unique_count = int(canonical.nunique())
    return {"exact_duplicate_count": int(len(frame) - unique_count), "unique_count": unique_count}
