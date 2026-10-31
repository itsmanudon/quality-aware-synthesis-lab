"""Phase 2 utility terms for selecting from an admitted candidate pool (Gate 1 decision 1).

Two terms, both computed from inner TRAIN only (never the held-out fold, never TEST):

``u2``        U2's anchor difficulty x group stability. Each candidate is assigned to its
              nearest real minority row of inner TRAIN (its anchor); the term is that row's
              within-class uMMA difficulty percentile times the stability of the U2 support
              group it belongs to. Percentiles and stabilities come from the pinned ml_ugo
              code (``u2_phase2.py``, U2 venv); only the anchor assignment is done here.
``boundary``  share of majority rows among the candidate's k nearest inner TRAIN rows (both
              classes), as in Borderline-SMOTE's danger test. Selection uses closeness to a
              target share ``beta``: -|share - beta|; beta = 0 prefers safe interior
              candidates, beta = 0.5 borderline ones.

Distances use one fixed space fitted on inner TRAIN: numerical fields median-imputed and
z-scored, categorical fields one-hot (unknown categories ignored). This space is a Phase 2
design choice, not part of U2.

Selection (``utility_filter``) keeps the top share ``rho`` of the admitted pool by the term
(never fewer than the budget) and leaves the final choice to an existing curator, so the
utility term is a separate column next to the quality gate and is never merged into the
concern index.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

BOUNDARY_K = 5


class Space:
    """Inner-TRAIN-fitted numeric space for nearest-neighbour lookups."""

    def __init__(self, inner: pd.DataFrame, spec: Any) -> None:
        self.numerical = list(spec.numerical_columns)
        self.categorical = list(spec.categorical_columns)
        transforms: list[tuple[str, Any, list[str]]] = []
        if self.numerical:
            transforms.append(("num", Pipeline([("impute", SimpleImputer(strategy="median")),
                                                ("scale", StandardScaler())]), self.numerical))
        if self.categorical:
            transforms.append(("cat", Pipeline([
                ("impute", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]),
                self.categorical))
        self.columns = ColumnTransformer(transforms, remainder="drop", sparse_threshold=0)
        self.columns.fit(self._frame(inner))

    def _frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(index=frame.index)
        for name in self.numerical:
            out[name] = pd.Series(pd.to_numeric(frame[name], errors="coerce"),
                                  index=frame.index, dtype=float)
        for name in self.categorical:
            out[name] = frame[name].astype(object).where(frame[name].notna(), np.nan)
        return out

    def transform(self, frame: pd.DataFrame) -> np.ndarray:
        return np.asarray(self.columns.transform(self._frame(frame)), dtype=np.float64)


def boundary_share(space: Space, inner: pd.DataFrame, candidates: pd.DataFrame, target: str,
                   positive: str, k: int = BOUNDARY_K) -> np.ndarray:
    """Share of non-minority rows among each candidate's k nearest inner TRAIN rows."""
    if candidates.empty:
        return np.empty(0)
    reference = space.transform(inner)
    k = min(k, len(inner))
    neighbours = NearestNeighbors(n_neighbors=k).fit(reference)
    _, index = neighbours.kneighbors(space.transform(candidates))
    majority = (inner[target].astype(str).to_numpy() != str(positive))
    return majority[index].mean(axis=1)


def u2_term(space: Space, inner: pd.DataFrame, candidates: pd.DataFrame, target: str,
            positive: str, anchors: dict[int, dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    """(difficulty percentile x group stability of the nearest minority anchor, anchor ids)."""
    if candidates.empty:
        return np.empty(0), np.empty(0, dtype=np.int64)
    minority = inner.loc[inner[target].astype(str) == str(positive)]
    ids = np.asarray([int(i) for i in minority.index], dtype=np.int64)
    missing = [int(i) for i in ids if int(i) not in anchors]
    if missing:
        raise ValueError(f"U2 anchor table lacks {len(missing)} inner minority rows")
    neighbours = NearestNeighbors(n_neighbors=1).fit(space.transform(minority))
    _, index = neighbours.kneighbors(space.transform(candidates))
    nearest = ids[index[:, 0]]
    value = np.asarray([anchors[int(i)]["difficulty_percentile"] * anchors[int(i)]["stability"]
                        for i in nearest], dtype=np.float64)
    return value, nearest


def band(share: np.ndarray, beta: float) -> np.ndarray:
    return -np.abs(np.asarray(share, dtype=np.float64) - beta)


def utility_filter(eligible: list[int], values: dict[int, float], rho: float, budget: int,
                   ids: dict[int, str]) -> list[int]:
    """Top ``max(budget, ceil(rho * n))`` eligible indices by value; ties by SHA-256 of the id."""
    keep = min(len(eligible), max(budget, math.ceil(rho * len(eligible))))
    order = sorted(eligible, key=lambda i: (-values[i],
                                            hashlib.sha256(ids[i].encode()).hexdigest()))
    return sorted(order[:keep])
