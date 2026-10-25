from __future__ import annotations

import copy
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    f1_score,
    matthews_corrcoef,
)

from rcqasyn.datasets.loader import LoadedDataset
from rcqasyn.datasets.registry import DatasetDefinition
from rcqasyn.datasets.split import make_split
from rcqasyn.empirical.evaluation import (
    aligned,
    bootstrap_metrics,
    evaluate,
    interval,
    stratified_indices,
    wilson,
)
from rcqasyn.empirical.generation import fresh_geometry, generate
from rcqasyn.empirical.study import Study
from rcqasyn.metrics.utility import _fit_score, resolve_estimators
from rcqasyn.phase2.common import digest, envelope
from rcqasyn.phase5.contracts import SelectionConfig
from rcqasyn.phase5.selection import select


def frames():
    train = pd.DataFrame({"x": np.arange(20, dtype=float), "z": np.arange(20, dtype=float)**2,
                          "class": ["negative"]*12+["positive"]*8}, index=np.arange(20)+100)
    test = pd.DataFrame({"x": [2., 15., 17.], "z": [4., 225., 289.],
                         "class": ["negative", "positive", "positive"]}, index=[200, 201, 202])
    spec = SimpleNamespace(target_column="class", minority_label="positive", dataset_id="fixture",
                           feature_columns=["x", "z"], numerical_columns=["x", "z"],
                           categorical_columns=[])
    return train, test, spec


def specification():
    return envelope("dataset-specification-v1", {"specification": {
        "dataset_id": "fixture", "features": [
            {"name": "x", "type": "numerical", "source_declaration": "real [0, 100]"},
            {"name": "z", "type": "numerical", "source_declaration": "real [0, 1000]"}],
        "target_semantics": {"target_column": "class", "literal_labels": ["positive", "negative"]},
        "rules": [{"rule_id": "fixture:schema", "authority": "AUTHORITATIVE",
                   "evidence": ["fixture/schema"], "hard_rejection_allowed": True}]}})


@pytest.mark.parametrize("classifier", ["logistic_regression", "random_forest"])
def test_predictions_recompute_frozen_metrics(classifier):
    train, test, spec = frames()
    new = evaluate(train, test, spec, classifier)
    old = _fit_score(train, test, spec, resolve_estimators(42)[classifier])
    for metric in ["f1", "average_precision", "balanced_accuracy", "mcc", "auroc"]:
        assert new[metric] == old[metric]
    assert [r["row_id"] for r in new["predictions"]] == [200, 201, 202]
    assert new["tp"]+new["fn"] == 2 and new["tn"]+new["fp"] == 1


def test_bootstrap_matches_bruteforce_including_score_ties():
    predictions = [{"y": y, "predicted": p, "score": s} for y, p, s in
                   [(0, 0, .1), (0, 1, .5), (1, 1, .5), (1, 1, .9), (1, 0, .1)]]
    y = np.array([r["y"] for r in predictions])
    indices = stratified_indices(y, 25, 13)
    values = bootstrap_metrics(predictions, indices)
    for replicate, ix in enumerate(indices):
        true = y[ix]
        predicted = np.array([r["predicted"] for r in predictions])[ix]
        scores = np.array([r["score"] for r in predictions])[ix]
        assert values["f1"][replicate] == pytest.approx(f1_score(true, predicted))
        assert values["average_precision"][replicate] == pytest.approx(average_precision_score(true, scores))
        assert values["balanced_accuracy"][replicate] == pytest.approx(balanced_accuracy_score(true, predicted))
        if len(set(predicted)) == 2:
            assert values["mcc"][replicate] == pytest.approx(matthews_corrcoef(true, predicted))
        else:
            assert np.isnan(values["mcc"][replicate])


def test_bootstrap_determinism_class_denominators_and_paired_zero():
    predictions = [{"y": i % 2, "predicted": i % 2, "score": float(i % 2)} for i in range(8)]
    y = np.array([r["y"] for r in predictions])
    a = stratified_indices(y, 2000, 79)
    assert np.array_equal(a, stratified_indices(y, 2000, 79))
    assert np.all(y[a].sum(axis=1) == 4)
    for values in bootstrap_metrics(predictions, a).values():
        assert interval(values-values)["lower"] == interval(values-values)["upper"] == 0


def test_degenerate_mcc_is_counted_undefined():
    rows = [{"y": y, "predicted": 0, "score": .1} for y in [0, 0, 1]]
    result = bootstrap_metrics(rows, stratified_indices(np.array([0, 0, 1]), 20, 1))
    assert interval(result["mcc"])["undefined_replicates"] == 20
    assert interval(result["mcc"])["lower"] is None
    assert np.all(result["f1"] == 0)
    assert wilson(1, 1)[0] < .21 and wilson(4, 4)[0] < .52
    assert "method" not in interval(result["mcc"])  # Preserve compared method identity.
    assert interval(result["mcc"])["interval_method"] == "stratified paired percentile"


@pytest.mark.parametrize("change", ["order", "label", "duplicate"])
def test_paired_alignment_rejects_mismatches(change):
    a = [{"row_id": i, "label": str(i % 2), "y": i % 2} for i in range(3)]
    b = copy.deepcopy(a)
    if change == "order":
        b.reverse()
    elif change == "label":
        b[0]["label"] = "positive"
    else:
        a[1] = a[0]
    with pytest.raises(ValueError):
        aligned(a, b)


@pytest.mark.parametrize("y", [[0, 0], [1, 1], [0, 2]])
def test_invalid_bootstrap_population_refused(y):
    with pytest.raises(ValueError):
        stratified_indices(np.array(y), 5, 1)


@pytest.mark.parametrize("method", ["SMOTE", "RandomOverSampler"])
def test_generator_is_train_only_budget_matched_and_deterministic(method):
    train, test, spec = frames()
    generated, provenance = generate(train, spec, method, 24, 29)
    again, other = generate(train, spec, method, 24, 29)
    pd.testing.assert_frame_equal(generated, again)
    assert provenance == other and len(generated) == 24
    assert not set(provenance["fit_row_ids"]) & set(test.index)
    assert set(provenance["fit_row_ids"]) == set(train.index)
    assert set(generated["class"]) == {"positive"}
    if method == "SMOTE":
        assert np.any(generated.x != generated.x.astype(int))  # No integer truncation.
    else:
        assert set(generated.x) <= set(train.loc[train["class"] == "positive", "x"])


def test_mixed_sampler_preserves_declared_categories_and_refuses_plain_smote():
    train, _, spec = frames()
    train["category"] = ["a", "b"]*10
    spec.feature_columns += ["category"]
    spec.categorical_columns = ["category"]
    generated, _ = generate(train, spec, "SMOTENC", 20, 43)
    assert set(generated.category) <= {"a", "b"}
    with pytest.raises(ValueError, match="incompatible"):
        generate(train, spec, "SMOTE", 20, 43)


def test_fresh_evidence_and_selection_bind_split_and_do_not_reuse_historical_candidates():
    train, _, spec = frames()
    candidates, provenance = generate(train, spec, "SMOTE", 40, 61)
    g, pools, concerns, evidence = fresh_geometry(train, candidates, specification(), "split-a", provenance)
    other, _, _, _ = fresh_geometry(train, candidates, specification(), "split-b", provenance)
    assert not {r["occurrence_id"] for r in g.occurrences} & {r["occurrence_id"] for r in other.occurrences}
    assert all(r["occurrence_id"].startswith("offline:") for r in g.occurrences)
    assert evidence["train_reference"]["train_indices"] == list(train.index)
    result = select(g, pools["combined"], concerns, SelectionConfig(strategy="quality-coverage", budget=8))
    assert len(result["selected_indices"]) == 8
    assert set(result["selected_indices"]) <= set(pools["schema"])
    assert result["budget_achieved"] == 8


def test_split_is_deterministic_stratified_and_source_bound(tmp_path):
    train, _, _ = frames()
    frame = train.reset_index(drop=True)
    spec = DatasetDefinition(dataset_id="fixture", display_name="fixture", raw_path=tmp_path/"raw.dat",
                             target_column="class", minority_label="positive", feature_columns=["x", "z"],
                             numerical_columns=["x", "z"])
    loaded = LoadedDataset(spec, tmp_path/"raw.dat", frame, digest(frame.to_dict()), 0)
    first = make_split(loaded, 13)
    assert first == make_split(loaded, 13) and first != make_split(loaded, 29)
    assert not set(first.train_indices) & set(first.test_indices)
    assert set(frame.loc[list(first.test_indices), "class"]) == {"negative", "positive"}


def test_score_keeps_pure_tstr_and_empty_hybrid_unavailable(tmp_path):
    train, test, spec = frames()
    study = object.__new__(Study)
    study.rows, study.config, study.output = [], {"classifiers": ["logistic_regression"]}, tmp_path
    minority = train.loc[train["class"] == "positive"]
    study.score({}, train, test, minority, spec, ("TSTR", "HYBRID_MINORITY"))
    assert study.rows[0]["status"] == "unavailable"
    assert study.rows[1]["status"] == "ok" and study.rows[1]["training_n"] == 28
    study.score({}, train, test, train.iloc[:1], spec, ("HYBRID_MINORITY",))
    assert study.rows[-1]["reason"] == "NO_SYNTHETIC_MINORITY_AUGMENTATION"


def test_unlabeled_records_cannot_be_fabricated_by_evaluation():
    train, test, spec = frames()
    train.loc[100, "class"] = "nan"
    with pytest.raises(ValueError, match="fabricated"):
        evaluate(train, test, spec, "logistic_regression")
