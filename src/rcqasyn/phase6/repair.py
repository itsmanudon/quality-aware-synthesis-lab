from __future__ import annotations

import copy
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

from rcqasyn.phase2.common import digest, envelope, verify_envelope
from rcqasyn.phase3.validators import number
from rcqasyn.phase5.geometry import complete_record

POLICY = {"version": "integer-half-even-max3-v1", "maximum_fields": 3,
          "maximum_absolute_edit": "0.5", "rounding": "Decimal(str(JSON number)), ROUND_HALF_EVEN"}


def nearest_integer(value: float) -> tuple[int, Decimal]:
    if not number(value):
        raise ValueError("only finite non-boolean numeric primitives can be rounded")
    original = Decimal(str(value))
    rounded = original.to_integral_value(rounding=ROUND_HALF_EVEN)
    change = abs(rounded-original)
    if change > Decimal(POLICY["maximum_absolute_edit"]):
        raise ValueError("approved absolute edit bound exceeded")
    return int(rounded), change


def authoritative_postcondition(spec: dict[str, Any], payload: dict[str, Any]) -> str | None:
    """Repair guard only; never turn source-observed ranges into hard bounds."""
    d = spec["dataset_id"]
    for rule in spec["rules"]:
        if rule["authority"] != "AUTHORITATIVE" or not rule["hard_rejection_allowed"]:
            continue
        if rule["rule_id"] in {d+":"+s for s in ("schema", "declared-categories", "target-tokens")}:
            continue
        bounds = rule.get("numeric_bounds")
        if not isinstance(bounds, dict) or not rule.get("evidence"):
            return "UNSUPPORTED_AUTHORITATIVE_POSTCONDITION:"+rule["rule_id"]
        field = bounds["field"]
        if not number(payload.get(field)):
            return "AUTHORITATIVE_BOUND_UNCHECKABLE:"+rule["rule_id"]
        x = Decimal(str(payload[field]))
        if ("minimum" in bounds and x < Decimal(str(bounds["minimum"]))) or (
                "maximum" in bounds and x > Decimal(str(bounds["maximum"]))):
            return "AUTHORITATIVE_BOUND_WOULD_FAIL:"+rule["rule_id"]
    return None


def propose_repair(occurrence: dict[str, Any], specification: dict[str, Any],
                   structural: dict[str, Any]) -> dict[str, Any]:
    verify_envelope(specification, "dataset-specification-v1")
    original = occurrence["payload"]; spec = specification["specification"]
    if (digest(original) != occurrence["payload_sha256"]
            or structural["occurrence_id"] != occurrence["occurrence_id"]
            or structural["payload_sha256"] != occurrence["payload_sha256"]
            or structural["specification_fingerprint"] != specification["fingerprint"]
            or occurrence["dataset_id"] != spec["dataset_id"]):
        raise ValueError("critical repair source/evidence/specification mismatch")
    invalid = structural["authoritative_validity"] == "INVALID"
    issues = structural["quantities"].get("violations", [])
    integer_issues = [v for v in issues if v["reason"] == "NONINTEGRAL_DECLARED_INTEGER"]
    fields = {f["name"]: f for f in spec["features"]}
    reasons = []
    if not invalid:
        reasons.append("NO_SUBSTANTIATED_STRUCTURAL_VIOLATION")
    elif structural["status"] != "AVAILABLE":
        reasons.append("UNRESOLVED_OR_PARTIAL_STRUCTURAL_EVIDENCE")
    if invalid and (not integer_issues or len(integer_issues) != len(issues)):
        reasons.append("OTHER_OR_MISSING_STRUCTURAL_REQUIREMENTS")
    if len(integer_issues) > POLICY["maximum_fields"]:
        reasons.append("MORE_THAN_THREE_INTEGER_FIELDS")
    if len({v["field"] for v in integer_issues}) != len(integer_issues):
        reasons.append("AMBIGUOUS_REPEATED_FIELD_EVIDENCE")
    repaired = copy.deepcopy(original); edits = []
    if invalid and not reasons:
        for issue in integer_issues:
            name = issue["field"]; field = fields.get(name)
            if (field is None or not field.get("source_declaration", "").startswith("integer")
                    or not number(original.get(name)) or original[name] == int(original[name])):
                reasons.append("INTEGER_AUTHORITY_OR_VALUE_MISMATCH:"+name)
                break
            value, change = nearest_integer(original[name])
            repaired[name] = value
            edits.append({"field": name, "original_value": original[name], "repaired_value": value,
                          "absolute_change_decimal": str(change), "absolute_change": float(change),
                          "source_declaration": field["source_declaration"], "rule_id": issue["rule_id"],
                          "justification": "Approved integer compatibility correction; not semantic validation"})
        if not reasons:
            constraint = authoritative_postcondition(spec, repaired)
            if constraint:
                reasons.append(constraint)
            if not complete_record(repaired, spec):
                reasons.append("OTHER_UNRESOLVED_LABELED_RECORD_REQUIREMENT")
    eligible = invalid and bool(integer_issues) and not reasons
    derived_id = ("m6:"+digest({"parent": occurrence["occurrence_id"], "policy": POLICY,
                               "specification": specification["fingerprint"], "payload": repaired})) if eligible else None
    return envelope("m6-repair-proposal-v1", {
        "parent_occurrence_id": occurrence["occurrence_id"], "parent_payload_sha256": occurrence["payload_sha256"],
        "dataset_id": occurrence["dataset_id"], "original_payload": copy.deepcopy(original),
        "source_provenance": {k: occurrence[k] for k in ("source_artifact", "source_artifact_sha256", "source_occurrence_ordinal")},
        "specification_fingerprint": specification["fingerprint"], "policy": POLICY,
        "pre_structural_state": "STRUCTURALLY_INVALID" if invalid else "NOT_ESTABLISHED",
        "pre_structural_evidence_fingerprint": digest(structural),
        "eligibility": "REPAIR_ELIGIBLE" if eligible else "REPAIR_INELIGIBLE" if invalid else "NOT_NEEDED",
        "reasons": reasons, "derived_occurrence_id": derived_id,
        "repaired_payload": repaired if eligible else None,
        "repaired_payload_sha256": digest(repaired) if eligible else None,
        "edits": edits if eligible else [], "edited_fields": len(edits) if eligible else 0,
        "repair_attempted": eligible, "human_validity_approval": "PENDING_SUPERVISOR_REVIEW"})
