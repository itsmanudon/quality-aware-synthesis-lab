"""Offline tests for the Phase 1 validation carve (no data files, no network)."""

from __future__ import annotations

import pandas as pd

from study.v3.phase1 import carve_validation


def _train() -> pd.DataFrame:
    labels = ["positive"] * 20 + ["negative"] * 80
    return pd.DataFrame({"x": range(100), "class": labels}, index=range(1000, 1100))


def test_validation_is_stratified_disjoint_and_covers_train() -> None:
    train = _train()
    inner, validation = carve_validation(train, "class", "toy", 13)
    assert set(inner).isdisjoint(validation)
    assert set(inner) | set(validation) == set(train.index)
    counts = train.loc[validation, "class"].value_counts().to_dict()
    assert counts == {"positive": 4, "negative": 16}


def test_validation_is_deterministic_and_seed_dependent() -> None:
    train = _train()
    assert carve_validation(train, "class", "toy", 13) == carve_validation(train, "class", "toy", 13)
    assert carve_validation(train, "class", "toy", 13) != carve_validation(train, "class", "toy", 29)
    # The dataset id is part of the derived seed, so two datasets never share an ordering.
    assert carve_validation(train, "class", "toy", 13) != carve_validation(train, "class", "o", 13)


def test_singleton_class_stays_in_inner_train() -> None:
    train = pd.DataFrame({"x": range(6), "class": ["positive"] + ["negative"] * 5})
    inner, validation = carve_validation(train, "class", "toy", 13)
    assert 0 in inner and 0 not in validation
