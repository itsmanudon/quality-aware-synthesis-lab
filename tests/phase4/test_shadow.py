from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from rcqasyn.phase2.common import digest, envelope, write_bundle
from rcqasyn.phase3.contracts import M2Config, M2Evidence
from rcqasyn.phase4 import calibration, workflow
from rcqasyn.phase4.calibration import fit_synthetic_fixture, pending_status
from rcqasyn.phase4.contracts import FAMILIES, Policy
from rcqasyn.phase4.fusion import decide, dependence, harmonize, mid_percentile
from rcqasyn.phase4.workflow import read_shadow, run_shadow


@pytest.fixture
def m2():
    bindings, evidence = [], []
    for i in range(20):
        b = {"occurrence_id": f"fixture:{i}", "payload_sha256": digest({"x": i}), "dataset_id": "fixture"}
        bindings.append(b)
        for f in FAMILIES:
            r = M2Evidence(**b, specification_fingerprint="a"*64, validator_family=f,
                status="AVAILABLE", raw_score=None if f == FAMILIES[0] else float(i if f == FAMILIES[1] else 19-i),
                reference_fingerprint="b"*64, configuration_fingerprint=digest(M2Config().model_dump(mode="json")),
                uncertainty="Synthetic fixture; validity not established")
            evidence.append(r.model_dump(mode="json"))
    return envelope("m2-offline-evidence-v1", {"configuration": M2Config().model_dump(mode="json"),
        "candidate_bindings": bindings, "evidence": evidence, "evidence_content_fingerprint": digest(evidence),
        "cohort_fingerprint": "c"*64, "crosswalk_fingerprints": ["d"*64], "specifications_fingerprint": "e"*64,
        "reference_populations": {"fixture": {"train_reference_fingerprint": "b"*64,
            "specification_fingerprint": "a"*64, "statistical_fit_uses_test": False,
            "train_indices": [0, 1], "recorded_train_fingerprint": "f"*64}}})


def reseal(value):
    return envelope(value["schema_version"], {k: v for k, v in value.items() if k != "fingerprint"})


def alter(m2, family, **changes):
    v = copy.deepcopy(m2)
    v["evidence"][FAMILIES.index(family)].update(changes)
    v["evidence_content_fingerprint"] = digest(v["evidence"])
    return reseal(v)


@pytest.mark.parametrize("score,reference,expected", [(1., [1., 1.], .5), (0., [1., 2.], 0.),
    (3., [1., 2.], 1.), (1., [0., 1., 1., 2.], .5)])
def test_mid_ecdf_exact_ties_direction(score, reference, expected):
    assert mid_percentile(score, reference, 2) == (expected, "AVAILABLE")


@pytest.mark.parametrize("score,reference,state", [(None, [1., 2.], "MISSING_SCORE"), (1., [1.], "SPARSE_REFERENCE")])
def test_missing_and_sparse_are_not_zero(score, reference, state):
    assert mid_percentile(score, reference, 2) == (None, state)


@pytest.mark.parametrize("score,reference", [(float("nan"), [1., 2.]), (1., [float("inf"), 2.])])
def test_nonfinite_refused(score, reference):
    with pytest.raises(ValueError):
        mid_percentile(score, reference, 2)


def test_determinism_raw_preservation_and_dependence(m2):
    before = copy.deepcopy(m2)
    a = harmonize(m2)
    assert a == harmonize(m2) and m2 == before
    assert a["vectors"][0]["normalized"]["local_support"]["raw_score"] == 0
    d = dependence(a["vectors"])["fixture"]
    assert d["spearman"] == pytest.approx(-1.)
    assert d["concern_union"] == 4 and d["concern_intersection"] == 0
    assert not d["independence_assumed"]
    assert a["vectors"][0]["fusion"]["probability_of_invalidity"] is None


def test_constant_dependence_explicit(m2):
    for r in m2["evidence"]:
        if r["validator_family"] != FAMILIES[0]:
            r["raw_score"] = 1.
    m2["evidence_content_fingerprint"] = digest(m2["evidence"])
    d = dependence(harmonize(reseal(m2))["vectors"])["fixture"]
    assert d["spearman"] is None and d["correlation_status"] == "UNDEFINED_SPARSE_OR_CONSTANT"


@pytest.mark.parametrize("change", ["payload", "reference", "config", "test", "duplicate", "missing", "dataset", "spec"])
def test_substituted_inputs_rejected(m2, change):
    r = m2["evidence"][0]
    if change == "payload": r["payload_sha256"] = "f"*64
    if change == "reference": r["reference_fingerprint"] = "f"*64
    if change == "config": r["configuration_fingerprint"] = "f"*64
    if change == "dataset": r["dataset_id"] = "foreign"
    if change == "spec": r["specification_fingerprint"] = "f"*64
    if change == "test": m2["reference_populations"]["fixture"]["statistical_fit_uses_test"] = True
    if change == "duplicate": m2["evidence"].append(r)
    if change == "missing": m2["evidence"].pop()
    m2["evidence_content_fingerprint"] = digest(m2["evidence"])
    with pytest.raises((ValueError, KeyError)):
        harmonize(reseal(m2))


def test_vector_tamper_detected(m2):
    v = harmonize(m2)["vectors"][0]
    v["normalized"]["local_support"]["percentile"] = 0.3
    with pytest.raises(ValueError, match="fingerprint"):
        decide(v, Policy(name="test"))


@pytest.mark.parametrize("family", ["local_support", "cross_feature"])
def test_statistical_extreme_is_review_never_hard_invalid(m2, family):
    v = harmonize(m2)["vectors"][-1 if family == "local_support" else 0]
    r = decide(v, Policy(name="test", families=(family,)))
    assert r["action"] == "REVIEW_REQUIRED"
    assert r["calibrated_probability"] is None


def test_provisional_is_not_human_valid(m2):
    v = harmonize(m2)["vectors"][10]
    r = decide(v, Policy(name="test", families=("local_support", "cross_feature")))
    assert r["action"] == "PROVISIONAL_PASS" and r["human_validity"] == "NOT_ESTABLISHED"


def test_partial_structure_review(m2):
    v = harmonize(alter(m2, FAMILIES[0], status="PARTIAL"))["vectors"][0]
    assert decide(v, Policy(name="test"))["action"] == "REVIEW_REQUIRED"


def test_missing_family_propagates_and_structural_rejection_dominates(m2):
    x = alter(m2, "local_support", status="UNAVAILABLE", raw_score=None)
    v = harmonize(x)["vectors"][0]
    assert v["fusion"]["uncalibrated_max"] is None
    assert decide(v, Policy(name="local", families=("local_support",)))["action"] == "ABSTAIN"
    assert decide(v, Policy(name="structure"))["action"] == "PROVISIONAL_PASS"
    x = alter(x, FAMILIES[0], authoritative_validity="INVALID")
    v = harmonize(x)["vectors"][0]
    assert decide(v, Policy(name="local", families=("local_support",)))["action"] == "REJECT_STRUCTURAL"


def test_unavailable_structure_abstains(m2):
    v = harmonize(alter(m2, FAMILIES[0], status="UNAVAILABLE"))["vectors"][0]
    assert decide(v, Policy(name="s"))["action"] == "ABSTAIN"


def test_sparse_reference_abstains(m2):
    v = harmonize(m2, 21)["vectors"][0]
    assert decide(v, Policy(name="s", families=("local_support",)))["action"] == "ABSTAIN"


def test_actual_unapproved_package_cannot_fit():
    result = pending_status([{"annotator_type": "AGENT", "review_status": "PENDING_HUMAN_APPROVAL", "human_final_label": None}], "a"*64)
    assert result["status"] == "NOT_ELIGIBLE_UNAPPROVED_LABELS" and result["calibrator"] is None
    with pytest.raises(ValueError):
        pending_status([{"annotator_type": "AGENT", "human_final_label": "VALID"}], "a"*64)


@pytest.fixture
def samples():
    return [{"occurrence_id": f"fixture:{i}", "dataset_id": "fixture", "label": "INVALID" if i%2 else "VALID",
        "score": float(i%2)*.8+.1, "population": "synthetic_fixture"} for i in range(20)]


def test_synthetic_fit_deterministic_and_separated(samples):
    ids = [r["occurrence_id"] for r in samples]
    a = fit_synthetic_fixture(samples, ids[:10], ids[10:])
    assert a == fit_synthetic_fixture(samples, ids[:10], ids[10:])
    assert a["status"] == "FITTED_SYNTHETIC_FIXTURE_ONLY" and a["fixture_only"]
    assert a["evaluation_brier"] == 0.


@pytest.mark.parametrize("failure", ["overlap", "duplicate", "foreign", "unknown", "test", "real_identity", "nonfinite", "pooled"])
def test_calibration_refuses_invalid_sources_and_partitions(samples, failure):
    ids = [r["occurrence_id"] for r in samples]; a, b = ids[:10], ids[10:]
    if failure == "overlap": b[0] = a[0]
    if failure == "duplicate": samples.append(samples[0])
    if failure == "foreign": a[0] = "foreign"
    if failure == "unknown": samples[0]["label"] = "NEGATIVE"
    if failure == "test": samples[0]["population"] = "REAL_TEST"
    if failure == "real_identity": samples[0]["occurrence_id"] = "real:1"
    if failure == "nonfinite": samples[0]["score"] = float("nan")
    if failure == "pooled": samples[0]["dataset_id"] = "other"
    with pytest.raises(ValueError):
        fit_synthetic_fixture(samples, a, b)


@pytest.mark.parametrize("mode", ["oneclass", "indeterminate", "missing", "constant"])
def test_calibration_refuses_inadequate_support(samples, mode):
    ids = [r["occurrence_id"] for r in samples]
    if mode == "oneclass":
        for r in samples: r["label"] = "VALID"
    if mode == "indeterminate": samples[0]["label"] = "INDETERMINATE"
    if mode == "missing": samples[0]["score"] = None
    if mode == "constant":
        for r in samples: r["score"] = .5
    a = fit_synthetic_fixture(samples, ids[:10], ids[10:])
    assert a["status"].startswith("NOT_ELIGIBLE") and not a["fitted"]
    if mode == "indeterminate": assert a["excluded_indeterminate"]["calibration"] == 1


def test_confirmed_path_cannot_bypass_ledger_gate(monkeypatch, tmp_path):
    def refuse(*args):
        raise ValueError("unapproved/mismatched ledger")
    monkeypatch.setattr(calibration, "confirm_research_ledger", refuse)
    with pytest.raises(ValueError, match="ledger"):
        calibration.fit_confirmed_research(tmp_path, {}, [], {}, {}, [], {}, {}, [], [], [], "fixture", m2_path=tmp_path)


def test_shadow_offline_replay_no_control_mutation_and_seal(m2, monkeypatch, tmp_path):
    occurrences = [{**b, "payload": {"x": i, "class": "positive"}, "source_artifact": "fixture",
        "source_artifact_sha256": "1"*64, "source_occurrence_ordinal": i+1,
        "controls": {k: {"decision": {"accepted": bool(i%2)}} for k in ("b1", "b2", "b3")}}
        for i, b in enumerate(m2["candidate_bindings"])]
    before = copy.deepcopy(occurrences)
    monkeypatch.setattr(workflow, "validate_preparation", lambda *a: None)
    monkeypatch.setattr(workflow, "validate_input", lambda *a: occurrences)
    inp = tmp_path/"m2"; write_bundle(inp, m2)
    review = tmp_path/"review"
    write_bundle(review, envelope("fixture-review-v1", {}), {"review.json": json.dumps([
        {"annotator_type": "AGENT", "review_status": "PENDING_HUMAN_APPROVAL", "human_final_label": None}])})
    plan = {"schema_version": "phase4-experiment-plan-v1", "normalization": "candidate-mid-ecdf-v1",
        "calibration": "INACTIVE_PENDING_CONFIRMED_HUMAN_LEDGER", "minimum_reference_size": 10,
        "m2_input": "fixture", "policies": [{"name": "structure-only", "families": [], "review_cutoff": .9},
        {"name": "combined-review", "families": ["local_support", "cross_feature"], "review_cutoff": .9}]}
    root = Path(__file__).resolve().parents[2]
    a = run_shadow(tmp_path, tmp_path, inp, review, tmp_path/"out", plan, root)
    b = run_shadow(tmp_path, tmp_path, inp, review, tmp_path/"replay", plan, root)
    assert a["decision_content_fingerprint"] == b["decision_content_fingerprint"]
    assert a["harmonized"] == b["harmonized"] and len(a["decisions"]) == 40
    assert occurrences == before
    assert read_shadow(tmp_path/"out", inp) == a
    write_bundle(tmp_path/"out", a)  # identical resumable write
    with pytest.raises(FileExistsError): write_bundle(tmp_path/"out", b)
    (tmp_path/"out"/"decisions.csv").write_text("tampered")
    with pytest.raises(ValueError): read_shadow(tmp_path/"out", inp)


def test_cli_source_root_option():
    from typer.testing import CliRunner

    from rcqasyn.phase4.cli import app
    result = CliRunner().invoke(app, ["shadow", "--help"])
    assert result.exit_code == 0 and "source-root" in result.stdout


def test_source_reference_membership_checked(m2, monkeypatch, tmp_path):
    cohort = {"fingerprint": m2["cohort_fingerprint"]}
    cws = [{"fingerprint": "d"*64, "records": m2["candidate_bindings"]}]
    specs = {"fingerprint": "e"*64, "specifications": [
        {"fingerprint": "a"*64, "specification": {"dataset_id": "fixture"}}]}
    monkeypatch.setattr(workflow, "load_preparation", lambda _: (cohort, cws, {}, specs))
    path = tmp_path/"data/manifests/fixture/split_manifest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"train_indices": [0, 1], "train_fingerprint": "f"*64}))
    assert len(workflow.validate_input(m2, tmp_path, tmp_path)) == 20
    m2["reference_populations"]["fixture"]["train_indices"] = [2, 3]
    with pytest.raises(ValueError, match="TEST"):
        workflow.validate_input(m2, tmp_path, tmp_path)


def test_future_review_payload_mismatch_refused(m2, monkeypatch, tmp_path):
    monkeypatch.setattr(calibration, "confirm_research_ledger", lambda *a: {"fixture_gate": True})
    monkeypatch.setattr(calibration, "read_results", lambda _: m2)
    cohort = {"population_kind": "research", "fingerprint": "c"*64}
    cws = [{"fingerprint": "d"*64, "records": m2["candidate_bindings"]}]
    path = tmp_path/"data/manifests/fixture/split_manifest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"train_indices": [0, 1], "train_fingerprint": "f"*64}))
    ledger = {"rows": [{"occurrence_id": "fixture:0", "dataset_id": "fixture", "payload_sha256": "0"*64, "human_final_label": "VALID"}]}
    with pytest.raises(ValueError, match="source mismatch"):
        calibration.fit_confirmed_research(tmp_path, cohort, cws,
            {"specifications_fingerprint": "e"*64}, {}, [], ledger, {}, harmonize(m2)["vectors"],
            ["fixture:0"], ["fixture:1"], "fixture", m2_path=tmp_path)


def test_report_content_determinism_and_population_identity():
    import runpy
    root = Path(__file__).resolve().parents[2]
    report = runpy.run_path(str(root/"scripts/report_phase4.py"))["report_data"]
    path = root/"artifacts/reports/phase4/shadow-v1"
    replay = root/"artifacts/reports/phase4/shadow-replay-v1"
    a = report(root, path, replay)
    assert a == report(root, path, replay)
    assert a["candidate_count"] == 601 and a["decision_count"] == 3606
    assert a["replay_identical"] and a["calibration"]["calibrator"] is None
    assert all(sum(r[action] for action in ("REJECT_STRUCTURAL", "REVIEW_REQUIRED", "PROVISIONAL_PASS", "ABSTAIN")) == r["n"] for r in a["results"])
