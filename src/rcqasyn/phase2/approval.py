"""Offline supervisor authentication. Imported review claims are never credentials."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .common import digest
from .contracts import (
    ApprovalLedger,
    HumanDecision,
    SupervisorAttestation,
    SupervisorTrust,
)

DOMAIN = b"RC-QASyn/supervisor-approval-ledger/v1\x00"


def read_approval_json(path: Path) -> dict[str, Any]:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate approval JSON key")
            value[key] = item
        return value

    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise TypeError("approval JSON must be an object")
    return value


def signing_bytes(ledger: dict[str, Any]) -> bytes:
    parsed = ApprovalLedger.model_validate_json(json.dumps(ledger))
    normalized = parsed.model_dump(mode="json")
    if normalized != ledger:
        raise ValueError("approval ledger must use canonical contract values")
    return DOMAIN + json.dumps(normalized, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True, allow_nan=False).encode("utf-8")


def check_decisions(decisions: list[dict[str, Any]], proposals: list[dict[str, Any]],
                    cohort: dict[str, Any], protocol: dict[str, Any],
                    *, submitted: bool) -> list[dict[str, Any]]:
    """Shared import/consumption binding and role checks; no authentication here."""
    from .annotations import validate_proposals

    validate_proposals(proposals, cohort, protocol)
    proposed = {p["review_row_id"]: p for p in proposals}
    if len(proposed) != len(proposals):
        raise ValueError("duplicate proposal")
    agents = {p["annotator_model_or_agent_version"].strip().casefold() for p in proposals}
    checked = []
    for raw in decisions:
        d = HumanDecision.model_validate_json(json.dumps(raw))
        if d.human_reviewer_reference.casefold() in agents:
            raise ValueError("known agent self-approval is forbidden")
        if submitted and d.review_status == "APPROVED":
            raise ValueError("APPROVED is an untrusted claim; submit a decision then authenticate it")
        p = proposed.get(d.review_row_id)
        if (p is None or d.proposal_fingerprint != digest(p)
                or d.occurrence_id != p["occurrence_id"]
                or d.payload_sha256 != p["payload_sha256"]):
            raise ValueError("review decision has stale proposal/occurrence binding")
        if (d.human_final_label is not None and d.human_final_label != p["proposed_label"]
                and not d.human_correction_note.strip()):
            raise ValueError("a changed label requires a correction note")
        checked.append(d.model_dump(mode="json"))
    if len({d["review_row_id"] for d in checked}) != len(checked):
        raise ValueError("duplicate review decision")
    return checked


def build_approval_ledger(root: Path, cohort: dict[str, Any], crosswalks: list[dict[str, Any]],
                          protocol: dict[str, Any], approval: dict[str, Any],
                          proposals: list[dict[str, Any]], history: Path,
                          reviewer_reference: str) -> dict[str, Any]:
    """Prepare unsigned content for supervisor inspection/signing; grant no approval."""
    from .annotations import gate_a, review_history

    gate = gate_a(root, cohort, crosswalks, protocol, approval)
    byrow = {r["review_row_id"]: r for r in cohort["records"]}
    proposed = {p["review_row_id"]: p for p in proposals}
    if len(proposed) != len(proposals) or set(proposed) != set(byrow):
        raise ValueError("proposal set differs from complete cohort")
    events = review_history(history)
    final: dict[str, dict[str, Any]] = {}
    for event in events:
        if (event["schema_version"] != "supervisor-review-event-v2"
                or event.get("validation_status") != "SUBMITTED_UNVERIFIED"):
            raise ValueError("legacy/unverified approval schema cannot authenticate; resubmit separately")
        if (event["cohort_fingerprint"] != cohort["fingerprint"]
                or event["protocol_fingerprint"] != protocol["fingerprint"]
                or event["population_kind"] != cohort["population_kind"]):
            raise ValueError("stale review event")
        decisions = check_decisions(event["decisions"], proposals, cohort, protocol, submitted=True)
        if (not decisions or event["proposal_fingerprints"] != {
                d["review_row_id"]: digest(proposed[d["review_row_id"]]) for d in decisions}):
            raise ValueError("review event proposal bindings differ")
        final.update({d["review_row_id"]: d for d in decisions})
    if set(final) != set(byrow) or any(
            d["review_status"] != "SUBMITTED" or d["human_final_label"] is None
            for d in final.values()):
        raise ValueError("explicit final review of every record is required")
    if any(d["human_reviewer_reference"] != reviewer_reference for d in final.values()):
        raise ValueError("every final decision must name the authenticating supervisor")
    # APPROVED in this unsigned document expresses the requested action, not authority.
    decisions = [{**final[key], "review_status": "APPROVED"} for key in sorted(final)]
    ledger = ApprovalLedger(
        cohort_fingerprint=cohort["fingerprint"],
        crosswalk_fingerprints=tuple(cohort["crosswalk_fingerprints"]),
        protocol_version=protocol["protocol_version"], protocol_fingerprint=protocol["fingerprint"],
        gate_a_approval_fingerprint=digest(gate.model_dump(mode="json")),
        population_kind=cohort["population_kind"],
        proposal_ledger_fingerprint=digest([proposed[k] for k in sorted(proposed)]),
        reviewer_reference=reviewer_reference,
        correction_history_tip=events[-1]["fingerprint"],
        correction_history_fingerprints=tuple(e["fingerprint"] for e in events),
        decisions=tuple(HumanDecision.model_validate_json(json.dumps(d)) for d in decisions),
    )
    return ledger.model_dump(mode="json")


def load_supervisor_trust(path: Path | None, forbidden_roots: tuple[Path, ...]) -> SupervisorTrust:
    """Reject the obsolete caller-selected authority interface, including test policies."""
    raise ValueError("caller-selected supervisor trust is forbidden; protected enrollment unavailable")


def authenticate_review(root: Path, cohort: dict[str, Any], crosswalks: list[dict[str, Any]],
                        protocol: dict[str, Any], approval: dict[str, Any],
                        proposals: list[dict[str, Any]], history: Path,
                        attestation: dict[str, Any] | None,
                        trust_config: Path | None = None) -> dict[str, Any]:
    """Production gate: this build has no independently protected authority provider.

    Neither an external path, environment variable, fixture object nor signed package
    can enroll authority. A reviewed supervisor deployment is required before this
    gate can be enabled. Keep legacy arguments only to reject old callers explicitly.
    """
    if trust_config is not None:
        raise ValueError("caller-selected supervisor trust is forbidden")
    raise ValueError("protected supervisor enrollment unavailable; official approval disabled")


def _verify_review_signature(root: Path, cohort: dict[str, Any],
                             crosswalks: list[dict[str, Any]], protocol: dict[str, Any],
                             approval: dict[str, Any], proposals: list[dict[str, Any]],
                             history: Path, attestation: dict[str, Any] | None,
                             trust: SupervisorTrust, expected_history_tip: str) -> dict[str, Any]:
    """Cryptographic/source checks only; this helper never establishes production authority."""
    if attestation is None:
        raise ValueError("signed supervisor attestation required")
    wire = SupervisorAttestation.model_validate_json(json.dumps(attestation))
    if wire.model_dump(mode="json") != attestation:
        raise ValueError("attestation must use canonical contract values")
    if wire.signature.key_id != trust.key_id:
        raise ValueError("untrusted supervisor signing key")
    supplied = wire.ledger.model_dump(mode="json")
    if wire.ledger.correction_history_tip != expected_history_tip:
        raise ValueError("signed history tip differs from the independently retained expected tip")
    if wire.ledger.reviewer_reference != trust.reviewer_reference:
        raise ValueError("signer is not the configured supervisor")
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(trust.public_key_hex)).verify(
            bytes.fromhex(wire.signature.signature_hex), signing_bytes(supplied))
    except InvalidSignature as error:
        raise ValueError("invalid supervisor signature") from error
    expected = build_approval_ledger(root, cohort, crosswalks, protocol, approval,
                                     proposals, history, trust.reviewer_reference)
    if supplied != expected:
        raise ValueError("signed ledger is stale or differs from source/proposals/review history")
    # Recheck signed records too; all fields are signed and independently source-bound.
    decisions = check_decisions(supplied["decisions"], proposals, cohort, protocol, submitted=False)
    if any(d["review_status"] != "APPROVED" for d in decisions):
        raise ValueError("authenticated approval of every record is required")
    return {"validation_status": "UNTRUSTED_SIGNATURE_DIAGNOSTIC",
            "official": False, "production_approval": False,
            "population_kind": cohort["population_kind"],
            "attestation": wire.model_dump(mode="json"), "trusted_key_id": trust.key_id,
            "trust_configuration_fingerprint": digest(trust.model_dump(mode="json")),
            "approved_decisions": decisions}
