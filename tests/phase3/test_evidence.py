from __future__ import annotations

import copy
import json

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from rcqasyn.datasets.split import _subset_fingerprint
from rcqasyn.phase2.common import digest, envelope, write_bundle
from rcqasyn.phase3.contracts import M2Config, M2Evidence
from rcqasyn.phase3.registry import REGISTRY, run_validators
from rcqasyn.phase3.validators import TrainEvidenceModel
from rcqasyn.phase3.workflow import fit_train_only, read_results


@pytest.fixture
def specification():
    return envelope("dataset-specification-v1", {"specification": {
        "dataset_id": "fixture", "features": [
            {"name": "x", "type": "numerical", "source_declaration": "integer [0, 2]"},
            {"name": "z", "type": "numerical", "source_declaration": "real [0, 2]"},
            {"name": "category", "type": "categorical", "documented_categories": ["a", "b", "c"]}],
        "target_semantics": {"target_column": "class", "literal_labels": ["positive", "negative"]},
        "rules": [{"rule_id": "fixture:schema", "authority": "AUTHORITATIVE", "evidence": ["synthetic/schema"], "hard_rejection_allowed": True}]}})


@pytest.fixture
def records():
    return [{"x": x, "z": float(x), "category": c, "class": label}
            for x, c, label in [(0, "a", "negative"), (1, "a", "negative"),
                                (2, "b", "positive"), (2, "b", "positive")]]


@pytest.fixture
def model(specification, records):
    return TrainEvidenceModel(specification, (0, 1, 2, 3), records, M2Config(k=1))


def occurrence(**changes):
    payload = {"x": 1, "z": 1.0, "category": "a", "class": "positive", **changes}
    return {"occurrence_id": "fixture-occurrence-1", "dataset_id": "fixture",
            "payload": payload, "payload_sha256": digest(payload)}


def test_registry_and_serialization_are_deterministic(model):
    a = run_validators(model, occurrence())
    assert [r.validator_family for r in a] == list(REGISTRY)
    assert a == run_validators(model, occurrence())
    assert all(M2Evidence.model_validate_json(r.model_dump_json()) == r for r in a)
    assert all(r.authoritative_validity == "NOT_ESTABLISHED" for r in a)


@pytest.mark.parametrize("field,value,violation", [("x", 1.5, True), ("x", True, True),
    ("x", 1.0, False), ("x", 1000, False), ("category", "c", False),
    ("category", "unjustified", True), ("x", None, False)])
def test_authoritative_rules_do_not_turn_rarity_or_support_into_invalidity(model, field, value, violation):
    result = model.score(occurrence(**{field: value}))
    assert (result[0].authoritative_validity == "INVALID") == violation
    assert all(r.authoritative_validity == "NOT_ESTABLISHED" for r in result[1:])


def test_unknown_but_documented_category_abstains_globally_not_invalid(model):
    result = model.score(occurrence(category="c"))
    assert result[0].authoritative_validity == "NOT_ESTABLISHED"
    assert result[1].status == "AVAILABLE"
    assert result[2].status == "UNAVAILABLE" and result[2].raw_score is None
    assert result[2].reason_codes == ("UNSEEN_TRAIN_CATEGORY",)


@pytest.mark.parametrize("missing", ["class", "x"])
def test_absent_fields_and_separate_requested_class(model, missing):
    r = occurrence()
    del r["payload"][missing]
    r["payload_sha256"] = digest(r["payload"])
    r["requested_class"] = "positive"
    out = model.score(r)
    assert out[0].authoritative_validity == "INVALID"
    assert out[1].status == ("AVAILABLE" if missing == "class" else "UNAVAILABLE")
    if missing == "class":
        assert out[1].quantities["neighbor_declared_class_fraction"] is None


def test_duplicates_ties_and_sparse_class_are_explicit(model):
    result = model.score(occurrence(x=2, z=2.0, category="b"))[1]
    assert result.raw_score == 0
    assert result.quantities["feature_duplicate_count"] == 2
    assert result.quantities["neighbor_train_row_ids"] == [2]
    assert "NEIGHBOR_DISTANCE_TIES" in result.reason_codes
    result = model.score(occurrence(**{"class": "unseen"}))[1]
    assert result.quantities["same_class_mean_distance"] is None
    assert "SPARSE_OR_ABSENT_DECLARED_CLASS_REFERENCE" in result.reason_codes


def test_gower_distance_has_hand_checked_numeric_and_nominal_terms(model):
    # Difference to reference row 0: |1-0|/2 + |1-0|/2 + category mismatch 1, divided by 3.
    assert model.distances(occurrence(category="b")["payload"])[0] == pytest.approx(2 / 3)


@pytest.mark.parametrize("n", [0, 1])
def test_insufficient_train_abstains_without_invented_scores(specification, records, n):
    model = TrainEvidenceModel(specification, tuple(range(n)), records[:n], M2Config())
    result = model.score(occurrence())
    assert all(r.status == "UNAVAILABLE" and r.raw_score is None for r in result[1:])


def test_constant_features_and_singular_covariance_are_finite(specification, records):
    records = [{**r, "x": 1, "z": 1.0} for r in records]
    model = TrainEvidenceModel(specification, tuple(range(4)), records, M2Config())
    result = model.score(occurrence(x=200))
    assert result[0].authoritative_validity == "NOT_ESTABLISHED"
    assert all(r.raw_score is None or np.isfinite(r.raw_score) for r in result)
    assert set(result[1].quantities["constant_numeric_fields"]) == {"x", "z"}


def test_missing_reference_rows_are_excluded_explicitly(specification, records):
    model = TrainEvidenceModel(specification, tuple(range(4)), [{**r, "z": None} for r in records], M2Config())
    out = model.score(occurrence())
    assert out[1].status == "UNAVAILABLE" and out[1].quantities["excluded_train_rows"] == 4


def test_real_test_perturbation_cannot_change_fit_or_scores(specification, records):
    frame = pd.DataFrame([*records, {"x": 500, "z": 600.0, "category": "c", "class": "positive"}])
    split = {"dataset_id": "fixture", "train_indices": [0, 1, 2, 3], "test_indices": [4],
             "train_fingerprint": _subset_fingerprint(frame, [0, 1, 2, 3])}
    first = fit_train_only(specification, frame, split, M2Config())
    changed = frame.copy()
    changed.loc[4] = [-999999, 999999.0, "TEST_ONLY_SENTINEL", "TEST_ONLY_CLASS"]
    second = fit_train_only(specification, changed, split, M2Config())
    assert first.reference == second.reference
    assert first.score(occurrence()) == second.score(occurrence())
    assert "TEST_ONLY_SENTINEL" not in json.dumps(second.categories)
    with pytest.raises(ValueError, match="TRAIN values"):
        changed.loc[0, "z"] = -1.0
        fit_train_only(specification, changed, split, M2Config())


def test_invalid_reference_membership_or_stale_occurrence_rejected(specification, records, model):
    with pytest.raises(ValueError, match="unique"):
        TrainEvidenceModel(specification, (0, 0, 1, 2), records, M2Config())
    bad = occurrence()
    bad["payload"]["x"] = 0
    with pytest.raises(ValueError, match="changed payload"):
        model.score(bad)
    bad = occurrence(); bad["dataset_id"] = "foreign"
    with pytest.raises(ValueError, match="foreign"):
        model.score(bad)


def test_statistics_cannot_grant_validity_or_nonfinite_scores(model):
    raw = model.score(occurrence())[1].model_dump(mode="json")
    for change in ({"authoritative_validity": "INVALID"}, {"raw_score": float("nan")},
                   {"quantities": {"unsafe": float("inf")}}, {"status": "UNAVAILABLE"}):
        with pytest.raises((ValidationError, ValueError)):
            M2Evidence.model_validate_json(json.dumps({**raw, **change}))


def test_evidence_bundle_reader_checks_completeness_bindings_and_seal(model, tmp_path):
    out = [r.model_dump(mode="json") for r in model.score(occurrence())]
    data = {"configuration": model.config.model_dump(mode="json"), "evidence": out,
            "candidate_bindings": [{k: occurrence()[k] for k in ("occurrence_id", "payload_sha256", "dataset_id")}],
            "reference_populations": {"fixture": {"train_reference_fingerprint": model.reference,
                                                    "specification_fingerprint": model.specification["fingerprint"]}}}
    value = envelope("m2-offline-evidence-v1", data)
    path = tmp_path / "valid"
    write_bundle(path, value)
    assert read_results(path) == value
    for i, invalid in enumerate((out[:2], out + out[:1], [{**out[0], "payload_sha256": "0" * 64}, *out[1:]])):
        value = envelope("m2-offline-evidence-v1", {**data, "evidence": invalid})
        path = tmp_path / f"invalid-{i}"
        write_bundle(path, value)
        with pytest.raises(ValueError):
            read_results(path)
    # File modification must invalidate the existing storage seal.
    (tmp_path / "valid/artifact.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        read_results(tmp_path / "valid")


def test_k_sensitivity_changes_diagnostic_not_structural_label(specification, records):
    a = TrainEvidenceModel(specification, (0, 1, 2, 3), records, M2Config(k=1))
    b = TrainEvidenceModel(specification, (0, 1, 2, 3), records, M2Config(k=4))
    assert a.score(occurrence())[1].raw_score != b.score(occurrence())[1].raw_score
    assert a.score(occurrence())[0].authoritative_validity == b.score(occurrence())[0].authoritative_validity
    assert a.reference == b.reference
    assert a.configuration != b.configuration


def test_scoring_does_not_modify_reference_or_candidate(model):
    candidate = occurrence()
    original = copy.deepcopy(candidate)
    records = copy.deepcopy(model.records)
    model.score(candidate)
    assert candidate == original and model.records == records
