from __future__ import annotations

import copy
import json

import pytest
from conftest import ROOT
from pydantic import ValidationError

from rcqasyn.phase2.annotations import annotation_protocol, packets
from rcqasyn.phase2.cohort import MASTER, build_cohort, validate_cohort
from rcqasyn.phase2.common import csv_rows, digest
from rcqasyn.phase2.contracts import Rule
from rcqasyn.phase2.specifications import specifications, validate_specifications


@pytest.fixture(scope="module")
def cohort(actual_crosswalks):
    return build_cohort(ROOT, actual_crosswalks)


def test_original_120_order_payloads_and_row94_source_binding(cohort, actual_crosswalks):
    old = csv_rows(ROOT / MASTER)
    assert len(cohort["records"]) == 120
    assert [r["payload"] for r in cohort["records"]] == [json.loads(r["candidate_json"]) for r in old]
    corrected = cohort["records"][92]
    assert corrected["original_review_row"] == 94
    assert corrected["occurrence_id"] == actual_crosswalks[0]["records"][0]["occurrence_id"]
    assert corrected["source_evidence"]["provider_seed"] == 1165294667
    assert corrected["source_evidence"]["batch_index"] == 0
    assert corrected["source_evidence"]["canonical_hash"].startswith("ee55fc63")
    assert corrected["source_evidence"]["nearest_train_distance"] == 0.3501177783211569
    assert len(cohort["changes"]) == 1
    assert set(cohort["changes"][0]["field_changes"]) == {
        "canonical_hash", "provider_seed", "batch_index",
        "nearest_train_distance", "nearest_same_class_train_distance"}
    assert len(cohort["overlap_review_row_ids"]) == 40
    assert len(set(cohort["overlap_review_row_ids"])) == 40
    assert validate_cohort(ROOT, cohort, actual_crosswalks)["supervisor_approved"] is False
    assert build_cohort(ROOT, actual_crosswalks)["fingerprint"] == cohort["fingerprint"]


def test_foreign_metadata_not_sanitized_by_refingerprinting(cohort, actual_crosswalks):
    value = copy.deepcopy(cohort)
    value["records"][92]["source_evidence"]["provider_seed"] = 1300151513
    value["fingerprint"] = digest({k: v for k, v in value.items() if k != "fingerprint"})
    with pytest.raises(ValueError, match="preserved source"):
        validate_cohort(ROOT, value, actual_crosswalks)


def test_foreign_requested_class_is_source_corrected(fixture_workflow):
    _, _, cohort, _, _ = fixture_workflow
    assert all(r["requested_class"] == "negative" for r in cohort["records"])
    assert all(c["field_changes"]["requested_class"]["original"] == "positive"
               for c in cohort["changes"])


@pytest.fixture(scope="module")
def specs():
    return specifications(ROOT)


def test_three_specs_types_source_and_train_only(specs):
    validate_specifications(ROOT, specs)
    assert len(specs["specifications"]) == 3
    for artifact in specs["specifications"]:
        spec = artifact["specification"]
        assert spec["target_semantics"]["minority_label"] == "positive"
        assert len(spec["source_identity"]["raw_sha256"]) == 64
        assert artifact["source_files"]
        assert "test_indices" not in spec["train_profile"]
        assert "test" not in json.dumps(spec["train_profile"]).lower()
        assert {r["authority"] for r in spec["rules"]} == {
            "AUTHORITATIVE", "INFERRED", "UNVERIFIED"}
        assert all(f["type"] in ("numerical", "categorical") for f in spec["features"])
    assert any(f["name"] == "sex" and f["type"] == "categorical"
               for f in specs["specifications"][2]["specification"]["features"])


def test_stale_source_inventory_rejected(specs):
    forged = copy.deepcopy(specs)
    a = forged["specifications"][0]
    a["source_files"]["data/manifests/page-blocks0/raw_schema.json"] = "bad"
    a["fingerprint"] = digest({k: v for k, v in a.items() if k != "fingerprint"})
    forged["fingerprint"] = digest({k: v for k, v in forged.items() if k != "fingerprint"})
    with pytest.raises(ValueError, match="source integrity"):
        validate_specifications(ROOT, forged)


@pytest.mark.parametrize("authority", ["INFERRED", "UNVERIFIED"])
def test_unsupported_hard_rules_rejected(authority):
    with pytest.raises(ValidationError):
        Rule(rule_id="bad", authority=authority, statement="rare is invalid",
             hard_rejection_allowed=True)


def test_blind_projection_and_overlap(cohort, specs):
    protocol = annotation_protocol(specs)
    public, private = packets(cohort, protocol)
    assert packets(cohort, protocol) == (public, private)
    assert len(public["primary"]) == 120 and len(public["overlap"]) == 40
    allowed = {"blinded_review_id", "dataset_id", "payload", "payload_sha256",
               "field_definitions", "allowed_evidence", "known_ambiguity"}
    assert all(set(row) == allowed for row in public["primary"])
    text = json.dumps(public).lower()
    for forbidden in ("b2_status", "b3_status", "provider_seed", "quality_score",
                      "threshold", "chatcmpl", "occurrence_id", "canonical_hash"):
        assert forbidden not in text
    assert [r["review_row_id"] for r in private["mapping"]] == [
        r["review_row_id"] for r in cohort["records"]]
    assert len({r["blinded_review_id"] for r in public["primary"]}) == 120
