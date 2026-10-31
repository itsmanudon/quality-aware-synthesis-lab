"""Offline tests for the U2 pool exporter's raw-space mapping (no U2 venv, no data)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import u2_pools


def _preprocessor(frame: pd.DataFrame) -> Pipeline:
    """Same named steps as ml_ugo's make_preprocessor (columns -> numeric/categorical)."""
    columns = ColumnTransformer([
        ("numeric", Pipeline([("impute", SimpleImputer(strategy="median")),
                              ("scale", StandardScaler())]), ["a", "b"]),
        ("categorical", Pipeline([("impute", SimpleImputer(strategy="most_frequent")),
                                  ("encode", OneHotEncoder(sparse_output=False))]), ["c"])],
        sparse_threshold=0)
    return Pipeline([("columns", columns)]).fit(frame)


def test_inverse_records_round_trips_numeric_and_one_hot() -> None:
    frame = pd.DataFrame({"a": [1.0, 2.5, 4.0], "b": [10.0, 20.0, 35.0], "c": ["F", "M", "I"]})
    pre = _preprocessor(frame)
    records = u2_pools.inverse_records(pre, pre.transform(frame))
    assert [r["c"] for r in records] == ["F", "M", "I"]
    assert np.allclose([r["a"] for r in records], frame["a"])
    assert np.allclose([r["b"] for r in records], frame["b"])


def test_non_one_hot_category_is_none_not_coerced() -> None:
    frame = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0], "c": ["F", "M"]})
    pre = _preprocessor(frame)
    matrix = pre.transform(frame)
    matrix[0, 2:] = [0.6, 0.4]  # an interpolated, non-one-hot block
    records = u2_pools.inverse_records(pre, matrix)
    assert records[0]["c"] is None and records[1]["c"] == "M"


def test_empty_pool_is_an_empty_list() -> None:
    frame = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0], "c": ["F", "M"]})
    pre = _preprocessor(frame)
    assert u2_pools.inverse_records(pre, np.empty((0, 4))) == []
