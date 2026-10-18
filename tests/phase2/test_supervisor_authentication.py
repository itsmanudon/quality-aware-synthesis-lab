from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from test_annotation_analysis import decision, propose
from typer.testing import CliRunner

from rcqasyn.cli.app import app
from rcqasyn.phase2.analysis import analyze, diagnose_fixture_analysis
from rcqasyn.phase2.annotations import (
    import_supervisor_approval,
    record_review,
    review_history,
)
from rcqasyn.phase2.approval import (
    authenticate_review,
    build_approval_ledger,
    read_approval_json,
)
from rcqasyn.phase2.common import digest, envelope, read_bundle, write_bundle
from rcqasyn.phase2.fixture_approval import (
    FixtureTrustAnchor,
    diagnose_fixture_review,
    import_fixture_diagnostic,
)


@pytest.fixture
def reviewed(fixture_workflow, tmp_path, supervisor_signer):
    root, cws, cohort, protocol, gate = fixture_workflow
    checkpoint, proposals = propose(fixture_workflow, tmp_path)
    history = tmp_path / "history"
    record_review(root, cohort, cws, protocol, gate, proposals,
                  [decision(p) for p in proposals], history)
    wire = supervisor_signer.attest(fixture_workflow, proposals, history)
    return SimpleNamespace(root=root, cws=cws, cohort=cohort, protocol=protocol, gate=gate,
                           proposals=proposals, history=history, signer=supervisor_signer,
                           wire=wire, tmp=tmp_path, checkpoint=checkpoint)


def fixture_anchor(z, policy=...):
    if policy is None:
        return None
    pin = z.signer.anchor(z.history)
    return FixtureTrustAnchor(z.signer.trust if policy is ... else policy,
                              pin.expected_key_id, pin.expected_history_tip)


def auth(z, wire=..., trust=...):
    return diagnose_fixture_review(z.root, z.cohort, z.cws, z.protocol, z.gate,
                                    z.proposals, z.history, z.wire if wire is ... else wire,
                                    fixture_anchor(z, trust))


def refused(z, wire=..., trust=...):
    value = z.wire if wire is ... else wire
    key = z.signer.trust if trust is ... else trust
    output = z.tmp / "must-not-exist"
    with pytest.raises((ValueError, FileNotFoundError)):
        authenticate_review(z.root, z.cohort, z.cws, z.protocol, z.gate,
                             z.proposals, z.history, value, key)
    with pytest.raises((ValueError, FileNotFoundError)):
        import_supervisor_approval(z.root, z.cohort, z.cws, z.protocol, z.gate,
                                   z.proposals, z.history, value, key, output)
    with pytest.raises((ValueError, FileNotFoundError)):
        analyze(z.root, z.cohort, z.cws, z.protocol, z.gate, z.proposals, z.history,
                supervisor_attestation=value, trust_config=key)
    # Retain all existing cryptographic and binding tests on the separate diagnostic path.
    anchor = fixture_anchor(z, trust)
    with pytest.raises((ValueError, FileNotFoundError)):
        diagnose_fixture_review(z.root, z.cohort, z.cws, z.protocol, z.gate,
                                  z.proposals, z.history, value, anchor)
    with pytest.raises((ValueError, FileNotFoundError)):
        import_fixture_diagnostic(z.root, z.cohort, z.cws, z.protocol, z.gate,
                                    z.proposals, z.history, value, anchor, output)
    with pytest.raises((ValueError, FileNotFoundError)):
        diagnose_fixture_analysis(z.root, z.cohort, z.cws, z.protocol, z.gate,
                                    z.proposals, z.history, supervisor_attestation=value,
                                    fixture_anchor=anchor)
    assert not output.exists()


@pytest.mark.parametrize("agent", ["SYNTHETIC_TEST_AGENT", "different-agent-v17", "Agent Delta"])
def test_exact_f1_and_other_proposer_identities_refused(fixture_workflow, tmp_path, agent):
    root, cws, c, p, gate = fixture_workflow
    _, proposals = propose(fixture_workflow, tmp_path)
    proposals = [{**r, "annotator_model_or_agent_version": agent} for r in proposals]
    decisions = [{**decision(r, status="APPROVED"), "human_reviewer_reference": agent,
                  "human_approval_provenance": "AGENT_SELF_APPROVAL_NO_HUMAN"} for r in proposals]
    with pytest.raises(ValueError, match="known agent self-approval"):
        record_review(root, c, cws, p, gate, proposals, decisions, tmp_path / "history")
    assert not (tmp_path / "history").exists()


@pytest.mark.parametrize("reference", ["arbitrary-human-string", "SYNTHETIC_TEST_SUPERVISOR",
                                       "  synthetic_test_agent  ", ""])
def test_claimed_approved_strings_cannot_authorize(fixture_workflow, tmp_path, reference):
    root, cws, c, p, gate = fixture_workflow
    _, proposals = propose(fixture_workflow, tmp_path)
    row = {**decision(proposals[0], status="APPROVED"),
           "human_reviewer_reference": reference,
           "human_approval_provenance": "I say this is human approved"}
    with pytest.raises(ValueError):
        record_review(root, c, cws, p, gate, proposals, [row], tmp_path / "history")
    assert not (tmp_path / "history").exists()


def test_unverified_claims_can_be_saved_but_never_consumed_as_approval(reviewed):
    z = reviewed
    event = review_history(z.history)[0]
    assert event["validation_status"] == "SUBMITTED_UNVERIFIED"
    assert all(d["review_status"] == "SUBMITTED" for d in event["decisions"])
    refused(z, wire=None)
    refused(z, trust=None)


def test_no_attestation_missing_trust_and_untrusted_key_fail_closed(reviewed):
    z = reviewed
    refused(z, wire=None)
    refused(z, trust=None)
    refused(z, trust=z.tmp / "missing-trust.json")
    bad = copy.deepcopy(z.wire)
    bad["signature"]["signature_hex"] = "00" * 64
    refused(z, wire=bad)
    bad = copy.deepcopy(z.wire)
    other = Ed25519PrivateKey.generate()  # Disposable untrusted fixture credential only.
    from rcqasyn.phase2.approval import signing_bytes
    bad["signature"]["signature_hex"] = other.sign(signing_bytes(bad["ledger"])).hex()
    refused(z, wire=bad)
    bad["signature"]["key_id"] = "f" * 64
    refused(z, wire=bad)


@pytest.mark.parametrize("field", [
    "label", "occurrence", "payload", "cohort", "crosswalk", "protocol_version",
    "protocol_fingerprint", "proposal", "history_tip", "history_list", "reviewer",
    "approval_state", "population", "gate_a", "rationale", "freeze",
])
def test_any_changed_signed_content_refused(reviewed, field):
    z = reviewed
    bad = copy.deepcopy(z.wire)
    ledger, row = bad["ledger"], bad["ledger"]["decisions"][0]
    if field == "label":
        row["human_final_label"] = "INVALID"
    elif field == "occurrence":
        row["occurrence_id"] = "foreign"
    elif field == "payload":
        row["payload_sha256"] = "0" * 64
    elif field == "cohort":
        ledger["cohort_fingerprint"] = "0" * 64
    elif field == "crosswalk":
        ledger["crosswalk_fingerprints"][0] = "0" * 64
    elif field == "protocol_version":
        ledger["protocol_version"] = "annotation-protocol-v999"
    elif field == "protocol_fingerprint":
        ledger["protocol_fingerprint"] = "0" * 64
    elif field == "proposal":
        ledger["proposal_ledger_fingerprint"] = "0" * 64
    elif field == "history_tip":
        ledger["correction_history_tip"] = "0" * 64
    elif field == "history_list":
        ledger["correction_history_fingerprints"] = []
    elif field == "reviewer":
        row["human_reviewer_reference"] = "Someone Else"
    elif field == "approval_state":
        row["review_status"] = "UNRESOLVED"
        row["human_final_label"] = None
    elif field == "population":
        ledger["population_kind"] = "research"
    elif field == "gate_a":
        ledger["gate_a_approval_fingerprint"] = "0" * 64
    elif field == "rationale":
        row["human_correction_note"] = "changed after signing"
    else:
        ledger["phase1_freeze_sha"] = "foreign"
    refused(z, wire=bad)


@pytest.mark.parametrize("field", ["cohort_fingerprint", "proposal_ledger_fingerprint",
                                    "correction_history_tip", "protocol_fingerprint"])
def test_validly_signed_foreign_context_or_replay_still_refused(reviewed, field):
    z = reviewed
    bad = copy.deepcopy(z.wire["ledger"])
    bad[field] = "a" * 64
    refused(z, wire=z.signer.sign(bad))


def test_incomplete_or_exported_unsigned_review_cannot_qualify(reviewed):
    z = reviewed
    bad = copy.deepcopy(z.wire["ledger"])
    bad["decisions"] = bad["decisions"][:1]
    refused(z, wire=z.signer.sign(bad))
    # Merely exporting a complete ledger conveys no authority.
    unsigned = build_approval_ledger(z.root, z.cohort, z.cws, z.protocol, z.gate,
                                     z.proposals, z.history, "SYNTHETIC_TEST_SUPERVISOR")
    refused(z, wire={"ledger": unsigned})
    assert all(p["human_final_label"] is None for p in z.proposals)


def test_direct_forged_history_and_status_flag_cannot_bypass(reviewed):
    z = reviewed
    wire = copy.deepcopy(z.wire)
    wire["authenticated"] = True
    refused(z, wire=wire)
    # Both v1 and a caller-sealed v2 remain untrusted; even a copied authentic
    # attestation does not bind an altered event tip or submitted decision.
    path = z.tmp / "forged-history"
    fake = envelope("supervisor-review-event-v2", {
        "validation_status": "SUBMITTED_UNVERIFIED", "sequence": 1,
        "previous_event_fingerprint": None, "cohort_fingerprint": z.cohort["fingerprint"],
        "protocol_fingerprint": z.protocol["fingerprint"], "population_kind": "synthetic_fixture",
        "decisions": [decision(p, status="APPROVED") for p in z.proposals],
        "proposal_fingerprints": {p["review_row_id"]: digest(p) for p in z.proposals}})
    write_bundle(path / "event-000001", fake)
    z.history = path
    refused(z)


def test_trust_cannot_be_bundled_with_review_data_or_wire(reviewed):
    z = reviewed
    bundled = z.tmp / "trust.json"
    bundled.write_bytes(z.signer.trust.read_bytes())
    refused(z, trust=bundled)
    wire = copy.deepcopy(z.wire)
    wire["public_key_hex"] = z.signer.key.public_key().public_bytes_raw().hex()
    refused(z, wire=wire)


def test_signature_verification_is_deterministic_and_fixture_only(reviewed):
    z = reviewed
    assert auth(z) == auth(z)
    assert z.signer.sign(z.wire["ledger"]) == z.wire
    output = z.tmp / "verified-import"
    import_fixture_diagnostic(z.root, z.cohort, z.cws, z.protocol, z.gate, z.proposals,
                                z.history, z.wire, fixture_anchor(z), output)
    assert read_bundle(output)["validation_status"] == "UNTRUSTED_SIGNATURE_DIAGNOSTIC"
    report = diagnose_fixture_analysis(
        z.root, z.cohort, z.cws, z.protocol, z.gate, z.proposals, z.history,
        supervisor_attestation=z.wire, fixture_anchor=fixture_anchor(z))
    assert report["official"] is False
    assert report["validation_status"] == "UNTRUSTED_FIXTURE_LABELS_DIAGNOSTIC"
    with pytest.raises(ValueError, match="caller-selected"):
        analyze(z.root, z.cohort, z.cws, z.protocol, z.gate, z.proposals, z.history,
                supervisor_attestation=z.wire, trust_config=z.signer.trust)


def test_corrections_resume_and_reopening_invalidate_previous_signature(reviewed):
    z = reviewed
    before = copy.deepcopy(z.proposals)
    record_review(z.root, z.cohort, z.cws, z.protocol, z.gate, z.proposals,
                  [decision(z.proposals[0], "VALID")], z.history)
    refused(z)
    wire = z.signer.attest((z.root, z.cws, z.cohort, z.protocol, z.gate),
                           z.proposals, z.history)
    approved = auth(z, wire=wire)
    row = next(d for d in approved["approved_decisions"]
               if d["review_row_id"] == z.proposals[0]["review_row_id"])
    assert row["human_final_label"] == "VALID" and row["human_correction_note"]
    assert z.proposals == before and len(review_history(z.history)) == 2
    record_review(z.root, z.cohort, z.cws, z.protocol, z.gate, z.proposals,
                  [decision(z.proposals[0], None, "UNRESOLVED")], z.history)
    refused(z, wire=wire)


def test_cli_analysis_and_approval_import_share_the_guard(reviewed, monkeypatch):
    from rcqasyn.phase2 import cli

    z = reviewed
    # Context fixture preserves the same source-bound API guard; bypass no auth code.
    monkeypatch.setattr(cli, "discover_project_root", lambda: z.tmp)
    monkeypatch.setattr(cli, "context", lambda *_: (z.cohort, z.cws, z.protocol, {}))
    monkeypatch.setattr(cli, "load_proposals", lambda *_: z.proposals)
    monkeypatch.setattr(cli, "derivative_destination", lambda _, p: p)
    gate = z.tmp / "gate.json"
    gate.write_text(json.dumps(z.gate), encoding="utf-8")
    result = CliRunner().invoke(app, [
        "phase2", "analyze", str(gate), str(z.checkpoint), str(z.history),
        str(z.tmp / "official-output"), "--source-root", str(z.root)])
    assert isinstance(result.exception, ValueError)
    assert "protected supervisor enrollment" in str(result.exception)
    assert not (z.tmp / "official-output").exists()
    # Exercise the same CLI/API auth path in an explicitly test-only context;
    # the production CLI deliberately exposes no fixture_only switch.
    monkeypatch.setattr(cli, "analyze",
                        lambda *args, **kwargs: analyze(*args, **kwargs, fixture_only=True))
    result = CliRunner().invoke(app, [
        "phase2", "analyze", str(gate), str(z.checkpoint), str(z.history),
        str(z.tmp / "official-output"), "--source-root", str(z.root)])
    assert isinstance(result.exception, ValueError)
    assert "separate untrusted fixture" in str(result.exception)
    assert not (z.tmp / "official-output").exists()
    unsigned = z.tmp / "unsigned.json"
    unsigned.write_text(json.dumps(z.wire), encoding="utf-8")
    result = CliRunner().invoke(app, [
        "phase2", "approval-import", str(gate), str(z.checkpoint), str(z.history),
        str(unsigned), str(z.tmp / "missing-trust"), str(z.tmp / "import-output"),
        "--source-root", str(z.root)])
    assert result.exit_code != 0 and not (z.tmp / "import-output").exists()


def test_duplicate_json_and_normalized_value_changes_refused(reviewed):
    z = reviewed
    path = z.tmp / "ambiguous.json"
    path.write_text('{"key":1,"key":2}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        read_approval_json(path)
    bad = copy.deepcopy(z.wire)
    bad["ledger"]["reviewer_reference"] += " "
    refused(z, wire=bad)


def test_supervisor_signer_uses_only_disposable_encrypted_temp_key(reviewed, monkeypatch):
    from cryptography.hazmat.primitives.serialization import (
        BestAvailableEncryption,
        Encoding,
        PrivateFormat,
    )

    z = reviewed
    script = Path(__file__).resolve().parents[2] / "scripts/sign_phase2_review.py"
    spec = importlib.util.spec_from_file_location("fixture_offline_signer", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.getpass, "getpass", lambda _: "test-only-passphrase")
    private = z.signer.directory / "DISPOSABLE_TEST_ONLY.pem"
    private.write_bytes(z.signer.key.private_bytes(
        Encoding.PEM, PrivateFormat.PKCS8, BestAvailableEncryption(b"test-only-passphrase")))
    ledger = z.tmp / "ledger.json"
    ledger.write_text(json.dumps(z.wire["ledger"]), encoding="utf-8")
    output = z.tmp / "signed.json"
    module.sign_review(ledger, private, output)
    assert read_approval_json(output) == z.wire



def test_partial_submissions_and_merged_export_resume(fixture_workflow, tmp_path, supervisor_signer,
                                                     monkeypatch):
    from rcqasyn.phase2 import cli

    root, cws, c, p, gate = fixture_workflow
    checkpoint, proposals = propose(fixture_workflow, tmp_path)
    history = tmp_path / "history"
    record_review(root, c, cws, p, gate, proposals, [decision(proposals[0])], history)
    with pytest.raises(ValueError, match="every record"):
        build_approval_ledger(root, c, cws, p, gate, proposals, history,
                               "SYNTHETIC_TEST_SUPERVISOR")
    monkeypatch.setattr(cli, "discover_project_root", lambda: tmp_path)
    monkeypatch.setattr(cli, "context", lambda *_: (c, cws, p, {}))
    monkeypatch.setattr(cli, "derivative_destination", lambda _, path: path)
    output = tmp_path / "export"
    result = CliRunner().invoke(app, [
        "phase2", "review-export", str(checkpoint), str(output), "--history", str(history)])
    assert result.exit_code == 0, result.exception
    exported = read_bundle(output)
    assert exported["validation_status"] == "SUBMITTED_UNVERIFIED"
    assert len(exported["submitted_decisions"]) == 1
    assert (output / "submitted-decisions.csv").is_file()
    assert all(row["human_final_label"] is None for row in exported["proposals"])
    record_review(root, c, cws, p, gate, proposals, [decision(proposals[1])], history)
    wire = supervisor_signer.attest(fixture_workflow, proposals, history)
    result = diagnose_fixture_review(root, c, cws, p, gate, proposals, history, wire,
                                     supervisor_signer.anchor(history))
    assert result["validation_status"] == "UNTRUSTED_SIGNATURE_DIAGNOSTIC"
    assert len(review_history(history)) == 2


def test_signed_duplicate_or_foreign_decision_refused(reviewed):
    z = reviewed
    bad = copy.deepcopy(z.wire["ledger"])
    bad["decisions"].append(bad["decisions"][0])
    refused(z, wire=z.signer.sign(bad))
    for field in ("occurrence_id", "payload_sha256", "proposal_fingerprint"):
        bad = copy.deepcopy(z.wire["ledger"])
        bad["decisions"][0][field] = "foreign"
        refused(z, wire=z.signer.sign(bad))

def test_cli_unsigned_export_and_production_import_fail_closed(reviewed, monkeypatch):
    import shutil

    from rcqasyn.phase2 import cli

    z = reviewed
    worktree = z.tmp / "implementation"
    namespace = worktree / "artifacts/reports/phase2"
    checkpoint, history = namespace / "proposals", namespace / "history"
    checkpoint.parent.mkdir(parents=True)
    shutil.copytree(z.checkpoint, checkpoint)
    shutil.copytree(z.history, history)
    monkeypatch.setattr(cli, "discover_project_root", lambda: worktree)
    monkeypatch.setattr(cli, "context", lambda *_: (z.cohort, z.cws, z.protocol, {}))
    gate, signed = z.tmp / "gate.json", z.tmp / "signed.json"
    gate.write_text(json.dumps(z.gate), encoding="utf-8")
    signed.write_text(json.dumps(z.wire), encoding="utf-8")
    unsigned, verified = namespace / "unsigned", namespace / "verified"
    runner = CliRunner()
    result = runner.invoke(app, [
        "phase2", "approval-export", str(gate), str(checkpoint), str(history),
        "SYNTHETIC_TEST_SUPERVISOR", str(unsigned), "--source-root", str(z.root)])
    assert result.exit_code == 0, result.exception
    assert read_bundle(unsigned)["validation_status"] == "UNSIGNED_UNVERIFIED"
    assert read_approval_json(unsigned / "ledger.json") == z.wire["ledger"]
    result = runner.invoke(app, [
        "phase2", "approval-import", str(gate), str(checkpoint), str(history),
        str(signed), str(verified), "--source-root", str(z.root)])
    assert result.exit_code != 0 and not verified.exists()
    assert "protected supervisor enrollment" in str(result.exception)
    diagnostic = namespace / "fixture-diagnostic"
    import_fixture_diagnostic(z.root, z.cohort, z.cws, z.protocol, z.gate, z.proposals,
                                history, z.wire, fixture_anchor(z), diagnostic)
    with pytest.raises(ValueError, match="schema"):
        cli.read_attestation(diagnostic)


@pytest.mark.parametrize("attack", [
    "direct-policy-b", "import-policy-b", "analysis-policy-b", "cli-policy-b",
    "environment-policy-b", "bundled-policy-b", "changed-selection", "missing-trust",
    "cached-test-key", "fabricated-receipt", "receipt-key-id", "foreign-cohort",
    "substituted-history-tip", "wrong-enrolled-key", "first-use-enrollment",
    "fixture-official-mode", "arbitrary-reviewer", "json-trust-field",
    "fixture-object", "legacy-authority-loader",
])
def test_r1_no_caller_input_can_enable_production_approval(reviewed, monkeypatch, attack):
    from dataclasses import replace
    from hashlib import sha256

    from rcqasyn.phase2 import cli
    from rcqasyn.phase2.approval import load_supervisor_trust

    z = reviewed
    agent = Ed25519PrivateKey.generate()
    raw = agent.public_key().public_bytes_raw()
    policy_b = z.signer.directory / "agent-owned-policy.json"
    policy_b.write_text(json.dumps({"schema_version": "supervisor-trust-v1",
        "reviewer_reference": "SYNTHETIC_TEST_SUPERVISOR",
        "key_id": sha256(raw).hexdigest(), "public_key_hex": raw.hex()}), encoding="utf-8")
    wire = copy.deepcopy(z.wire)
    from rcqasyn.phase2.approval import signing_bytes
    wire["signature"].update(key_id=sha256(raw).hexdigest(),
        signature_hex=agent.sign(signing_bytes(wire["ledger"])).hex())
    # Fixed fixture anchor A rejects B independently of the selected policy contents.
    for selected in (z.signer.trust, policy_b):
        with pytest.raises(ValueError):
            diagnose_fixture_review(z.root, z.cohort, z.cws, z.protocol, z.gate,
                z.proposals, z.history, wire,
                replace(fixture_anchor(z), policy=selected))
    supplied = policy_b
    if attack == "missing-trust":
        supplied = None
    elif attack in ("environment-policy-b", "cached-test-key"):
        assert auth(z)["production_approval"] is False
        monkeypatch.setenv("RCQASYN_SUPERVISOR_TRUST_CONFIG", str(policy_b))
        monkeypatch.setenv("SUPERVISOR_PUBLIC_KEY", raw.hex())
        supplied = None
    elif attack == "bundled-policy-b":
        wire["public_key_hex"] = raw.hex()
    elif attack == "fabricated-receipt":
        wire = {"validation_status": "AUTHENTICATED_SUPERVISOR_APPROVED",
                "official": True, "attestation": wire}
    elif attack == "receipt-key-id":
        wire["signature"]["key_id"] = z.signer.key_id
    elif attack == "foreign-cohort":
        wire["ledger"]["cohort_fingerprint"] = "f" * 64
    elif attack == "substituted-history-tip":
        wire["ledger"]["correction_history_tip"] = "f" * 64
    elif attack == "first-use-enrollment":
        supplied = z.tmp / "not-enrolled" / "trust.json"
    elif attack == "arbitrary-reviewer":
        wire["ledger"]["reviewer_reference"] = "invented-reviewer"
    elif attack == "json-trust-field":
        wire["trust_config"] = str(policy_b)
    elif attack == "fixture-object":
        supplied = fixture_anchor(z)
    elif attack == "changed-selection":
        diagnostic = auth(z)
        assert diagnostic["production_approval"] is False
    output = z.tmp / "r1-forbidden-output"
    with pytest.raises(ValueError, match="caller-selected|protected supervisor"):
        authenticate_review(z.root, z.cohort, z.cws, z.protocol, z.gate,
                            z.proposals, z.history, wire, supplied)
    with pytest.raises(ValueError):
        import_supervisor_approval(z.root, z.cohort, z.cws, z.protocol, z.gate,
            z.proposals, z.history, wire, supplied, output)
    with pytest.raises(ValueError):
        analyze(z.root, z.cohort, z.cws, z.protocol, z.gate, z.proposals, z.history,
            supervisor_attestation=wire, trust_config=supplied,
            fixture_only=attack == "fixture-official-mode")
    with pytest.raises(ValueError):
        load_supervisor_trust(supplied, ())
    assert not output.exists()
    if attack == "first-use-enrollment":
        assert not supplied.parent.exists()
    if attack == "cli-policy-b":
        monkeypatch.setattr(cli, "discover_project_root", lambda: z.tmp)
        monkeypatch.setattr(cli, "context", lambda *_: (z.cohort, z.cws, z.protocol, {}))
        monkeypatch.setattr(cli, "derivative_destination", lambda _, path: path)
        gate = z.tmp / "gate.json"
        signed = z.tmp / "signed-b.json"
        gate.write_text(json.dumps(z.gate), encoding="utf-8")
        signed.write_text(json.dumps(wire), encoding="utf-8")
        for args in (["approval-import", str(gate), str(z.checkpoint), str(z.history),
                      str(signed), str(policy_b), str(output)],
                     ["analyze", str(gate), str(z.checkpoint), str(z.history), str(output),
                      "--trust-config", str(policy_b)]):
            result = CliRunner().invoke(app, ["phase2", *args])
            assert result.exit_code != 0 and not output.exists()


def test_fixture_diagnostics_cannot_be_promoted_and_pin_is_independent(reviewed):
    from dataclasses import replace

    z = reviewed
    diagnostic = auth(z)
    assert diagnostic["official"] is False and diagnostic["production_approval"] is False
    assert diagnostic["validation_status"] == "UNTRUSTED_SIGNATURE_DIAGNOSTIC"
    for missing in ("expected_key_id", "expected_history_tip"):
        bad = replace(fixture_anchor(z), **{missing: "0" * 64})
        with pytest.raises(ValueError, match="pin|tip"):
            diagnose_fixture_review(z.root, z.cohort, z.cws, z.protocol, z.gate,
                                      z.proposals, z.history, z.wire, bad)
    research = {**z.cohort, "population_kind": "research"}
    with pytest.raises(ValueError, match="refuse research"):
        diagnose_fixture_review(z.root, research, z.cws, z.protocol, z.gate,
                                  z.proposals, z.history, z.wire, fixture_anchor(z))
    with pytest.raises(ValueError, match="refuse research"):
        diagnose_fixture_analysis(z.root, research, z.cws, z.protocol, z.gate,
            z.proposals, z.history, supervisor_attestation=z.wire,
            fixture_anchor=fixture_anchor(z))


def test_policy_file_change_cannot_change_fixed_fixture_pin(reviewed):
    z = reviewed
    pin = fixture_anchor(z)
    assert auth(z)["production_approval"] is False
    key = Ed25519PrivateKey.generate()
    from hashlib import sha256
    public = key.public_key().public_bytes_raw()
    changed = {"schema_version": "supervisor-trust-v1",
               "reviewer_reference": "SYNTHETIC_TEST_SUPERVISOR",
               "key_id": sha256(public).hexdigest(), "public_key_hex": public.hex()}
    z.signer.trust.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="pin"):
        diagnose_fixture_review(z.root, z.cohort, z.cws, z.protocol, z.gate,
                                  z.proposals, z.history, z.wire, pin)
