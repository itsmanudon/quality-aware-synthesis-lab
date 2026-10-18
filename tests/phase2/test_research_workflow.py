"""Synthetic-only coverage of the streamlined personal-review gates."""
from __future__ import annotations

import copy
import json

import pytest
from typer.testing import CliRunner

from rcqasyn.phase2.analysis import analyze_research, comparison_metrics, research_report
from rcqasyn.phase2.annotations import packets
from rcqasyn.phase2.approval import authenticate_review
from rcqasyn.phase2.common import csv_text, digest, read_bundle, write_bundle
from rcqasyn.phase2.research import (
    bindings,
    confirm_research_ledger,
    export_research_review,
    import_research_review,
    load_research_proposals,
    read_review_rows,
    submit_research_batch,
    validate_research_ledger,
    validate_scope,
)


@pytest.fixture
def research_case(fixture_workflow, tmp_path):
    root, cws, cohort, protocol, _ = fixture_workflow
    scope = {"schema_version": "research-scope-approval-v1", "purpose": "COHORT_AND_RUBRIC_ONLY",
             "decision": "APPROVED", **bindings(cohort, protocol),
             "supervisor_reference": "SYNTHETIC_TEST_SUPERVISOR",
             "implementation_owner_reference": "SYNTHETIC_TEST_OWNER",
             "approval_provenance": "SYNTHETIC_TEST_ONLY; not an actual human approval",
             "scientific_decisions": "Synthetic-only conservative ambiguity handling"}
    answers = [{"blinded_review_id": p["blinded_review_id"], "proposed_label": "VALID",
                "proposed_rationale": "Synthetic schema evidence only; not a real annotation",
                "supporting_evidence_ids": ["page-blocks0:schema"],
                "uncertainty_or_ambiguity": "Synthetic fixture; no scientific ground truth"}
               for p in packets(cohort, protocol)[0]["primary"]]
    checkpoint = tmp_path / "proposals"
    submit_research_batch(root, cohort, cws, protocol, scope, answers,
                           "SYNTHETIC_TEST_AGENT", "SYNTHETIC_TEST_ONLY", checkpoint)
    proposals = load_research_proposals(checkpoint, cohort, protocol, scope)
    pending = export_research_review(root, cohort, cws, protocol, scope, proposals)
    rows = copy.deepcopy(pending["rows"])
    for row in rows:
        row.update(human_review_status="REVIEWED", human_final_label="VALID",
                   human_reviewer_reference=scope["supervisor_reference"])
    ledger = import_research_review(root, cohort, cws, protocol, scope, proposals, rows,
                                    "SYNTHETIC_TEST_ONLY")
    confirmation = {"schema_version": "research-ledger-confirmation-v1",
                    "decision": "CONFIRM_ALL_REVIEWED_LABELS_FOR_RESEARCH_ANALYSIS",
                    "reviewed_ledger_fingerprint": ledger["fingerprint"],
                    "scope_approval_fingerprint": digest(scope),
                    "supervisor_reference": scope["supervisor_reference"],
                    "confirmation_provenance": "SYNTHETIC_TEST_ONLY"}
    return root, cws, cohort, protocol, scope, proposals, pending, ledger, confirmation, answers, checkpoint


def test_personal_review_is_separate_from_proposals_and_confirmation(research_case):
    root, cws, cohort, protocol, scope, proposals, pending, ledger, confirmed, _, _ = research_case
    assert all(r["human_final_label"] is None and r["human_review_status"] == "PENDING"
               and r["human_reviewer_reference"] == "" for r in pending["rows"])
    assert not any("controls" in r for r in pending["rows"])
    assert pending["production_approval"] is False
    assert ledger["validation_status"] == "REVIEWED_AWAITING_EXPLICIT_CONFIRMATION"
    with pytest.raises(ValueError):
        confirm_research_ledger(root, cohort, cws, protocol, scope, proposals, pending, confirmed)
    with pytest.raises(ValueError):
        analyze_research(root, cohort, cws, protocol, scope, proposals, ledger, {},
                          implementation_revision="e" * 40)
    assert confirm_research_ledger(root, cohort, cws, protocol, scope, proposals, ledger, confirmed)
    with pytest.raises(ValueError, match="official approval disabled"):
        authenticate_review(root, cohort, cws, protocol, scope, proposals, root / "history", None)


@pytest.mark.parametrize("field", ["cohort_fingerprint", "crosswalk_fingerprints",
                                   "protocol_fingerprint", "specifications_fingerprint",
                                   "research_rubric_fingerprint", "decision"])
def test_scope_must_explicitly_approve_exact_cohort_and_rubric(research_case, field):
    root, cws, cohort, protocol, scope, *_ = research_case
    bad = {**scope, field: ["0" * 64] if field == "crosswalk_fingerprints" else "0" * 64}
    with pytest.raises(ValueError):
        validate_scope(root, cohort, cws, protocol, bad)


def test_known_agent_or_implementation_owner_cannot_self_approve(research_case):
    root, cws, cohort, protocol, scope, proposals, _, _, _, answers, checkpoint = research_case
    bad = {**scope, "supervisor_reference": " synthetic_test_owner "}
    with pytest.raises(ValueError, match="self-approve"):
        validate_scope(root, cohort, cws, protocol, bad)
    bad = {**scope, "supervisor_reference": " synthetic_test_agent "}
    with pytest.raises(ValueError, match="self-approval"):
        export_research_review(root, cohort, cws, protocol, bad, proposals)
    with pytest.raises(ValueError, match="self-approval"):
        submit_research_batch(root, cohort, cws, protocol, bad, answers,
                               "SYNTHETIC_TEST_AGENT", "test", checkpoint)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "foreign", "payload", "proposal",
                                       "context", "pending", "no_label", "no_reviewer",
                                       "agent", "changed_without_note"])
def test_review_import_rejects_incomplete_stale_or_implicit_decisions(research_case, mutation):
    root, cws, cohort, protocol, scope, proposals, _, ledger, *_ = research_case
    rows = copy.deepcopy(ledger["rows"])
    if mutation == "missing":
        rows.pop()
    elif mutation == "duplicate":
        rows[1] = copy.deepcopy(rows[0])
    elif mutation == "foreign":
        rows[0]["review_row_id"] = "foreign"
    elif mutation == "payload":
        rows[0]["payload_sha256"] = "0" * 64
    elif mutation == "proposal":
        rows[0]["proposal_fingerprint"] = "0" * 64
    elif mutation == "context":
        rows[0]["proposed_rationale"] = "changed"
    elif mutation == "pending":
        rows[0]["human_review_status"] = "PENDING"
    elif mutation == "no_label":
        rows[0]["human_final_label"] = None
    elif mutation == "no_reviewer":
        rows[0]["human_reviewer_reference"] = ""
    elif mutation == "agent":
        rows[0]["human_reviewer_reference"] = "SYNTHETIC_TEST_AGENT"
    else:
        rows[0]["human_final_label"] = "INVALID"
    with pytest.raises(ValueError):
        import_research_review(root, cohort, cws, protocol, scope, proposals, rows, "test")


@pytest.mark.parametrize("field", ["reviewed_ledger_fingerprint", "scope_approval_fingerprint",
                                   "supervisor_reference", "decision"])
def test_confirmation_is_exact_and_cannot_reuse_an_old_ledger(research_case, field):
    root, cws, cohort, protocol, scope, proposals, _, ledger, confirmed, *_ = research_case
    bad = {**confirmed, field: "0" * 64}
    with pytest.raises(ValueError):
        confirm_research_ledger(root, cohort, cws, protocol, scope, proposals, ledger, bad)


def test_corrections_preserve_previous_version_and_require_new_confirmation(research_case, tmp_path):
    root, cws, cohort, protocol, scope, proposals, _, ledger, confirmed, *_ = research_case
    original = copy.deepcopy(ledger)
    write_bundle(tmp_path / "review-v1", ledger)
    rows = copy.deepcopy(ledger["rows"])
    rows[0].update(human_final_label="INDETERMINATE", human_correction_note="Synthetic ambiguity")
    revised = import_research_review(root, cohort, cws, protocol, scope, proposals, rows,
                                     "SYNTHETIC_CORRECTION", previous=ledger)
    assert ledger == original
    assert revised["ledger_version"] == 2
    assert revised["previous_ledger_fingerprint"] == ledger["fingerprint"]
    with pytest.raises(FileExistsError):
        write_bundle(tmp_path / "review-v1", revised)
    with pytest.raises(ValueError):
        confirm_research_ledger(root, cohort, cws, protocol, scope, proposals, revised, confirmed)
    confirmed = {**confirmed, "reviewed_ledger_fingerprint": revised["fingerprint"]}
    result = analyze_research(root, cohort, cws, protocol, scope, proposals, revised, confirmed,
                              implementation_revision="e" * 40)
    assert result["label_counts"] == {"INDETERMINATE": 1, "VALID": 1}
    assert all(m["binary_denominator"] == 1 for m in result["overall"].values())
    assert result["production_approval"] is result["cryptographically_authenticated"] is False
    assert result["population_kind"] == "synthetic_fixture"
    assert "not cryptographically authenticated" in research_report(result)
    assert "inter-rater agreement" in result["overlap_interpretation"]


def test_csv_and_json_round_trip_preserve_review_context(research_case, tmp_path):
    root, cws, cohort, protocol, scope, proposals, _, ledger, *_ = research_case
    for suffix, content in (("csv", csv_text(ledger["rows"])), ("json", json.dumps(ledger["rows"]))):
        path = tmp_path / f"review.{suffix}"
        path.write_text(content, encoding="utf-8-sig", newline="")
        rows = read_review_rows(path)
        assert rows == ledger["rows"]
        assert import_research_review(root, cohort, cws, protocol, scope, proposals, rows,
                                       "SYNTHETIC_TEST_ONLY") == ledger


def test_proposal_retry_is_idempotent_and_different_overlap_is_rejected(research_case):
    root, cws, cohort, protocol, scope, proposals, _, _, _, answers, checkpoint = research_case
    first = submit_research_batch(root, cohort, cws, protocol, scope, answers,
                                   "SYNTHETIC_TEST_AGENT", "SYNTHETIC_TEST_ONLY", checkpoint)
    assert read_bundle(first)["proposals"] == proposals
    altered = copy.deepcopy(answers)
    altered[0]["proposed_rationale"] = "Changed synthetic proposal"
    with pytest.raises(ValueError, match="already exists"):
        submit_research_batch(root, cohort, cws, protocol, scope, altered,
                               "SYNTHETIC_TEST_AGENT", "SYNTHETIC_TEST_ONLY", checkpoint)
    with pytest.raises(ValueError, match="complete cohort"):
        export_research_review(root, cohort, cws, protocol, scope, proposals[:1])


def test_analysis_preserves_false_acceptance_rejection_and_abstention_accounting():
    rows = [{"occurrence_id": str(i), "dataset_id": "fixture", "requested_class": "positive",
             "label": label, "b2": b2, "b3": b3, "b3_recorded_verdict": verdict}
            for i, (label, b2, b3, verdict) in enumerate([
                ("VALID", True, False, "FAIL"), ("INVALID", True, False, "ABSTAIN"),
                ("INDETERMINATE", False, True, "PASS")])]
    metrics = comparison_metrics(rows)
    assert metrics["overall"]["b2"] == {
        "positive_class": "INVALID", "tp": 0, "fp": 0, "fn": 1, "tn": 1,
        "false_acceptance": 1, "false_rejection": 0, "false_acceptance_rate": 1.0,
        "false_rejection_rate": 0.0, "binary_denominator": 2, "indeterminate": 1}
    b3 = metrics["overall"]["b3"]
    assert (b3["tp"], b3["fp"], b3["fn"], b3["tn"]) == (1, 1, 0, 0)
    assert metrics["b3_recorded_verdict_counts"]["ABSTAIN"] == 1
    assert metrics["shared_error_occurrence_ids"] == []


def test_ledger_revalidation_detects_metadata_edits_even_with_recomputed_digest(research_case):
    root, cws, cohort, protocol, scope, proposals, _, ledger, *_ = research_case
    bad = {**ledger, "protocol_fingerprint": "0" * 64}
    bad["fingerprint"] = digest({k: v for k, v in bad.items() if k != "fingerprint"})
    with pytest.raises(ValueError, match="bindings"):
        validate_research_ledger(root, cohort, cws, protocol, scope, proposals, bad)


def test_research_cli_round_trip_requires_separate_confirmation(research_case, monkeypatch):
    from rcqasyn.phase2 import research_cli

    root, cws, cohort, protocol, scope, _proposals, _, ledger, confirmed, answers, _ = research_case
    monkeypatch.setattr(research_cli, "discover_project_root", lambda: root)
    monkeypatch.setattr(research_cli, "_context", lambda *_: (cohort, cws, protocol, {}))
    monkeypatch.setattr(research_cli.subprocess, "check_output",
                        lambda args, **_: "e" * 40 if "rev-parse" in args else "")
    inputs = root / "test-inputs"
    inputs.mkdir()
    for name, value in (("scope", scope), ("answers", answers),
                        ("reviewed", ledger["rows"]), ("confirmation", confirmed)):
        (inputs / f"{name}.json").write_text(json.dumps(value), encoding="utf-8")
    base = root / "artifacts/reports/phase2"
    checkpoint = base / "proposals"
    runner = CliRunner()

    def invoke(command):
        result = runner.invoke(research_cli.app, [str(c) for c in command])
        assert result.exit_code == 0, (result.output, result.exception)
        return result

    invoke(["submit", inputs / "scope.json", inputs / "answers.json", "SYNTHETIC_TEST_AGENT",
            "SYNTHETIC_TEST_ONLY", checkpoint])
    invoke(["review-export", inputs / "scope.json", checkpoint, base / "pending"])
    invoke(["review-import", inputs / "scope.json", checkpoint, inputs / "reviewed.json",
            "SYNTHETIC_TEST_ONLY", base / "reviewed-v1"])
    saved = read_bundle(base / "reviewed-v1")
    assert saved == ledger
    (inputs / "confirmation.json").write_text("{}", encoding="utf-8")
    command = ["analyze", inputs / "scope.json", checkpoint, base / "reviewed-v1",
               inputs / "confirmation.json", base / "results"]
    refused = runner.invoke(research_cli.app, [str(c) for c in command])
    assert refused.exit_code != 0 and not (base / "results").exists()
    (inputs / "confirmation.json").write_text(json.dumps(confirmed), encoding="utf-8")
    invoke(command)
    result = read_bundle(base / "results")
    assert result["population_kind"] == "synthetic_fixture"
    assert result["reviewed_ledger_fingerprint"] == saved["fingerprint"]
    assert (base / "results/report.md").exists()


def test_real_checkpoint_contains_exact_preserved_inputs_and_no_labels():
    from pathlib import Path

    from rcqasyn.phase2.research import checkpoint_text, scope_checkpoint
    from rcqasyn.phase2.workflow import load_preparation

    bundle = Path(__file__).resolve().parents[2] / "artifacts/reports/phase2/gate-a-v3"
    cohort, crosswalks, protocol, specs = load_preparation(bundle)
    checkpoint = scope_checkpoint(cohort, crosswalks, protocol, specs)
    assert checkpoint["cohort_fingerprint"] == (
        "b754ccee1f58ccfc0d89dfde176cb84d58993b93bc5e87a7059ce5e8885877a5")
    assert sum(c["occurrences"] for c in checkpoint["crosswalk_summaries"]) == 601
    assert (checkpoint["cohort_records"], checkpoint["overlap_records"]) == (120, 40)
    assert checkpoint["cohort_or_rubric_approved"] is checkpoint["real_labels_generated"] is False
    assert checkpoint["rubric"]["definitions"] == protocol["definitions"]
    text = checkpoint_text(checkpoint)
    assert all(c["fingerprint"] in text for c in crosswalks)
    assert all(r in text for r in protocol["rules"])
    assert "INDETERMINATE" in text and "No real labels generated" in text
