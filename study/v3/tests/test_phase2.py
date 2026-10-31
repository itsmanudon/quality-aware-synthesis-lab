"""Offline tests for Phase 2 cross-fitting, utility terms and the v3 rounding variant."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from study.v3.crossfit import choose_f1_threshold, crossfit_folds, pooled_scores
from study.v3.repair_v3 import repair_pool, round_integers
from study.v3.utility import Space, band, boundary_share, u2_term, utility_filter


def _train(n_pos: int = 12, n_neg: int = 40) -> pd.DataFrame:
    labels = ["positive"] * n_pos + ["negative"] * n_neg
    return pd.DataFrame({"x": np.arange(len(labels), dtype=float), "Class": labels},
                        index=pd.Index(range(100, 100 + len(labels))))


def test_crossfit_folds_partition_stratified_and_deterministic() -> None:
    train = _train()
    folds = crossfit_folds(train, "Class", "toy", 13)
    assert folds == crossfit_folds(train, "Class", "toy", 13)
    assert folds != crossfit_folds(train, "Class", "toy", 29)
    flat = [i for f in folds for i in f]
    assert sorted(flat) == sorted(int(i) for i in train.index) and len(flat) == len(set(flat))
    for label in ("positive", "negative"):
        sizes = [int((train.loc[f, "Class"] == label).sum()) for f in folds]
        assert max(sizes) - min(sizes) <= 1
    # The round-robin offset spreads leftovers: fold sizes differ by at most one overall.
    assert max(map(len, folds)) - min(map(len, folds)) <= 1


def test_crossfit_folds_refuse_a_class_smaller_than_k() -> None:
    with pytest.raises(ValueError, match="fewer than 5 folds"):
        crossfit_folds(_train(n_pos=4), "Class", "toy", 13)


def test_choose_f1_threshold_matches_u2_rule() -> None:
    y = [1, 1, 0, 1, 0, 0]
    p = [0.9, 0.8, 0.7, 0.45, 0.2, 0.1]
    threshold, f1 = choose_f1_threshold(y, p)
    assert threshold == pytest.approx(0.45) and f1 == pytest.approx(6 / 7)
    # An exact F1 tie with .5 keeps .5 (closest to .5 wins).
    assert choose_f1_threshold(y, [0.9, 0.8, 0.7, 0.6, 0.2, 0.1])[0] == 0.5
    # All-tied scores: the only cut point and .5 give the same F1; .5 wins the tie.
    assert choose_f1_threshold([1, 0], [0.5, 0.5])[0] == 0.5


def test_pooled_scores_choose_each_threshold_without_its_own_fold() -> None:
    folds = [{"y": [1, 0], "score": [0.9, 0.1]},
             {"y": [1, 0], "score": [0.3, 0.2]},
             {"y": [1, 0], "score": [0.4, 0.35]}]
    pooled = pooled_scores(folds)
    assert pooled["counts_default"] == {"tp": 1, "fp": 0, "fn": 2, "tn": 3}
    # Fold 0's threshold is chosen on folds 1-2 only: positives 0.3, 0.4 vs negatives 0.2, 0.35.
    assert pooled["thresholds"][0] == pytest.approx(0.3)
    assert pooled["minority_n"] == 3 and pooled["f1_default"] == pytest.approx(0.5)


def _int_spec() -> dict:
    return {"dataset_id": "toy", "rules": [],
            "target_semantics": {"target_column": "Class",
                                 "literal_labels": ["positive", "negative"]},
            "features": [{"name": "a", "type": "numerical", "source_declaration": "integer"},
                         {"name": "b", "type": "numerical", "source_declaration": "integer"},
                         {"name": "c", "type": "numerical", "source_declaration": "real"}]}


def test_round_integers_rounds_every_integer_field_half_even_only() -> None:
    spec = _int_spec()
    repaired, edited, reason = round_integers({"a": 2.5, "b": 3.4999, "c": 0.25,
                                               "Class": "positive"}, spec)
    assert reason is None and edited == 2
    assert repaired == {"a": 2, "b": 3, "c": 0.25, "Class": "positive"}
    untouched = {"a": 2, "b": 3, "c": 0.7, "Class": "positive"}
    assert round_integers(untouched, spec) == (untouched, 0, None)


def test_round_integers_keeps_the_original_when_a_guard_still_fails() -> None:
    spec = _int_spec()
    payload = {"a": 1.2, "b": 2.0, "c": 0.1, "Class": "unknown"}
    repaired, edited, reason = round_integers(payload, spec)
    assert repaired is payload and edited == 1
    assert reason == "OTHER_UNRESOLVED_LABELED_RECORD_REQUIREMENT"


def test_repair_pool_counts_outcomes() -> None:
    frame = pd.DataFrame([{"a": 1.4, "b": 2.6, "c": 0.0, "Class": "positive"},
                          {"a": 1.0, "b": 2.0, "c": 0.5, "Class": "positive"}])
    repaired, outcome = repair_pool(frame, _int_spec())
    assert repaired.iloc[0].to_dict() == {"a": 1, "b": 3, "c": 0.0, "Class": "positive"}
    assert outcome["outcomes"] == {"recovered": 1, "complete_unchanged": 1}
    assert (outcome["complete_before_n"], outcome["complete_after_n"]) == (1, 2)


def _space_inputs() -> tuple[SimpleNamespace, pd.DataFrame]:
    spec = SimpleNamespace(numerical_columns=("x",), categorical_columns=("k",))
    inner = pd.DataFrame({"x": [0.0, 1.0, 2.0, 10.0, 11.0, 12.0],
                          "k": ["u", "u", "u", "v", "v", "v"],
                          "Class": ["positive"] * 3 + ["negative"] * 3},
                         index=pd.Index([5, 6, 7, 8, 9, 10]))
    return spec, inner


def test_boundary_share_counts_majority_neighbours() -> None:
    spec, inner = _space_inputs()
    space = Space(inner, spec)
    candidates = pd.DataFrame({"x": [1.0, 11.0], "k": ["u", "v"]})
    share = boundary_share(space, inner, candidates, "Class", "positive", k=3)
    assert share.tolist() == [0.0, 1.0]
    assert band(share, 0.0).tolist() == [0.0, -1.0]


def test_u2_term_uses_the_nearest_minority_anchor() -> None:
    spec, inner = _space_inputs()
    space = Space(inner, spec)
    anchors = {5: {"difficulty_percentile": 0.2, "stability": 0.5},
               6: {"difficulty_percentile": 0.5, "stability": 1.0},
               7: {"difficulty_percentile": 0.9, "stability": 0.5}}
    values, nearest = u2_term(space, inner, pd.DataFrame({"x": [2.1, 0.9], "k": ["u", "u"]}),
                              "Class", "positive", anchors)
    assert nearest.tolist() == [7, 6] and values.tolist() == pytest.approx([0.45, 0.5])
    with pytest.raises(ValueError, match="lacks 1 inner minority rows"):
        u2_term(space, inner, pd.DataFrame({"x": [1.0], "k": ["u"]}), "Class", "positive",
                {5: anchors[5], 6: anchors[6]})


def test_utility_filter_keeps_at_least_the_budget() -> None:
    eligible = [0, 1, 2, 3, 4, 5, 6, 7]
    values = {i: float(i % 4) for i in eligible}
    ids = {i: f"id{i}" for i in eligible}
    assert utility_filter(eligible, values, 0.0, 2, ids) == [3, 7]
    assert len(utility_filter(eligible, values, 0.5, 2, ids)) == 4
    assert len(utility_filter(eligible, values, 0.25, 3, ids)) == 3
