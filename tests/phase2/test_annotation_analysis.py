from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from rcqasyn.phase2.analysis import _confusion, analyze, diagnose_fixture_analysis
from rcqasyn.phase2.annotations import (
    gate_a,
    load_proposals,
    packets,
    pending_batches,
    record_review,
    review_history,
    submit_batch,
)
from rcqasyn.phase2.common import digest
from rcqasyn.phase2.contracts import HumanDecision, Proposal


def answers(cohort, protocol):
    public, _ = packets(cohort, protocol)
    return [{"blinded_review_id": r["blinded_review_id"], "proposed_label": "INDETERMINATE",
             "proposed_rationale": "Synthetic test fixture; no research judgment.",
             "supporting_evidence_ids": [], "uncertainty_or_ambiguity": "Fixture only"}
            for r in public["primary"]]


def propose(workflow, tmp_path):
    root, cws, cohort, protocol, approval = workflow
    checkpoint = tmp_path / "proposals"
    submit_batch(root, cohort, cws, protocol, approval, answers(cohort, protocol),
                 "SYNTHETIC_TEST_AGENT", "fixture-execution", checkpoint)
    return checkpoint, load_proposals(checkpoint, cohort, protocol)


def decision(p, label="INDETERMINATE", status="SUBMITTED"):
    return {**{k: p[k] for k in ("review_row_id", "occurrence_id", "payload_sha256")},
            "proposal_fingerprint": digest(p), "review_status": status,
            "human_final_label": label, "human_correction_note": "Synthetic fixture",
            "human_reviewer_reference": "SYNTHETIC_TEST_SUPERVISOR",
            "human_approval_provenance": "SYNTHETIC_TEST_ONLY"}


def test_gate_a_missing_stale_and_owner_verification_refused(fixture_workflow):
    root, cws, c, p, approval = fixture_workflow
    with pytest.raises(ValidationError):
        gate_a(root, c, cws, p, {})
    for key in ("cohort_fingerprint", "protocol_fingerprint"):
        bad = {**approval, key: "stale"}
        with pytest.raises(ValueError, match="stale"):
            gate_a(root, c, cws, p, bad)
    with pytest.raises(ValidationError):
        gate_a(root, c, cws, p, {**approval, "independent_verifier_reference":
                                approval["implementation_owner_reference"]})


def test_resume_idempotence_and_no_proposal_overwrite(fixture_workflow, tmp_path):
    root, cws, c, p, approval = fixture_workflow
    path, proposals = propose(fixture_workflow, tmp_path)
    assert len(proposals) == 2
    assert pending_batches(c, p, path) == []
    submit_batch(root, c, cws, p, approval, answers(c, p),
                 "SYNTHETIC_TEST_AGENT", "fixture-execution", path)
    assert load_proposals(path, c, p) == proposals
    with pytest.raises(ValueError, match="already exists"):
        submit_batch(root, c, cws, p, approval, answers(c, p),
                     "different-agent", "different-execution", path)
    assert all(r["human_final_label"] is None and
               r["review_status"] == "PENDING_HUMAN_APPROVAL" for r in proposals)


@pytest.mark.parametrize("label,evidence", [("UNKNOWN", []), ("INVALID", []),
                                           ("VALID", ["b3:accept"])])
def test_invalid_verdict_or_evidence_refused(fixture_workflow, tmp_path, label, evidence):
    root, cws, c, p, approval = fixture_workflow
    value = answers(c, p)[:1]
    value[0].update(proposed_label=label, supporting_evidence_ids=evidence)
    with pytest.raises(ValueError):
        submit_batch(root, c, cws, p, approval, value, "agent", "execution", tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_history_preserves_proposal_and_requires_all_explicit_approvals(fixture_workflow, tmp_path, supervisor_signer):
    root, cws, c, p, approval = fixture_workflow
    _, proposals = propose(fixture_workflow, tmp_path)
    before = copy.deepcopy(proposals)
    history = tmp_path / "history"
    with pytest.raises(ValueError):
        analyze(root, c, cws, p, approval, proposals, history, fixture_only=True)
    record_review(root, c, cws, p, approval, proposals,
                  [decision(proposals[0])], history)
    with pytest.raises(ValueError):
        analyze(root, c, cws, p, approval, proposals, history, fixture_only=True)
    record_review(root, c, cws, p, approval, proposals,
                  [decision(proposals[1], "VALID")], history)
    attestation = supervisor_signer.attest(fixture_workflow, proposals, history)
    report = diagnose_fixture_analysis(
        root, c, cws, p, approval, proposals, history,
        supervisor_attestation=attestation, fixture_anchor=supervisor_signer.anchor(history))
    assert report["official"] is False
    assert report["overall"]["b2"]["indeterminate"] == 1
    assert report["overall"]["b2"]["binary_denominator"] == 1
    assert proposals == before
    assert len(review_history(history)) == 2
    with pytest.raises(ValueError, match="protected supervisor enrollment"):
        analyze(root, c, cws, p, approval, proposals, history)


def test_foreign_occurrence_and_approval_fields_refused(fixture_workflow, tmp_path):
    root, cws, c, p, approval = fixture_workflow
    _, proposals = propose(fixture_workflow, tmp_path)
    forged = copy.deepcopy(proposals)
    forged[0]["occurrence_id"] = "foreign"
    with pytest.raises(ValueError, match="foreign occurrence"):
        record_review(root, c, cws, p, approval, forged, [decision(forged[0])],
                      tmp_path / "history")
    with pytest.raises(ValidationError):
        HumanDecision.model_validate({**decision(proposals[0]), "human_reviewer_reference": ""})
    with pytest.raises(ValidationError):
        Proposal.model_validate({**proposals[0], "human_final_label": "VALID"})


def test_correction_note_and_reopened_review(fixture_workflow, tmp_path):
    root, cws, c, p, approval = fixture_workflow
    _, proposals = propose(fixture_workflow, tmp_path)
    history = tmp_path / "history"
    changed = {**decision(proposals[0], "INVALID"), "human_correction_note": ""}
    with pytest.raises(ValueError, match="correction note"):
        record_review(root, c, cws, p, approval, proposals, [changed], history)
    record_review(root, c, cws, p, approval, proposals,
                  [decision(r) for r in proposals], history)
    record_review(root, c, cws, p, approval, proposals,
                  [decision(proposals[0], None, "UNRESOLVED")], history)
    with pytest.raises(ValueError):
        analyze(root, c, cws, p, approval, proposals, history, fixture_only=True)


def test_confusion_axes_and_indeterminate_denominator():
    rows = [{"label": label, "b2": accept} for label, accept in (
        ("INVALID", False), ("VALID", False), ("INVALID", True),
        ("VALID", True), ("INDETERMINATE", False))]
    result = _confusion(rows, "b2")
    assert (result["tp"], result["fp"], result["fn"], result["tn"]) == (1, 1, 1, 1)
    assert result["binary_denominator"] == 4 and result["indeterminate"] == 1
    assert result["false_acceptance_rate"] == result["false_rejection_rate"] == 0.5
