from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from rcqasyn.phase2.common import digest, envelope, verify_envelope
from rcqasyn.phase3.contracts import M2Config, M2Evidence

from .contracts import FAMILIES, STATISTICAL, EvidenceVector, Policy


def mid_percentile(score: float | None, reference: list[float], minimum: int = 10
                   ) -> tuple[float | None, str]:
    """Empirical mid-distribution, not a probability of invalidity."""
    if minimum < 2 or any(not np.isfinite(x) for x in reference):
        raise ValueError("invalid descriptive reference")
    if score is None:
        return None, "MISSING_SCORE"
    if not np.isfinite(score):
        raise ValueError("nonfinite candidate score")
    if len(reference) < minimum:
        return None, "SPARSE_REFERENCE"
    a = np.asarray(reference)
    return float((np.sum(a < score) + 0.5 * np.sum(a == score)) / len(a)), "AVAILABLE"


def harmonize(m2: dict[str, Any], minimum: int = 10) -> dict[str, Any]:
    verify_envelope(m2, "m2-offline-evidence-v1")
    if digest(m2["evidence"]) != m2["evidence_content_fingerprint"]:
        raise ValueError("M2 content mismatch")
    config = M2Config.model_validate_json(json.dumps(m2["configuration"]))
    config_fp = digest(config.model_dump(mode="json"))
    bindings = m2["candidate_bindings"]
    if len({r["occurrence_id"] for r in bindings}) != len(bindings):
        raise ValueError("duplicate occurrence binding")
    expected = {(b["occurrence_id"], f) for b in bindings for f in FAMILIES}
    indexed = {}
    byid = {b["occurrence_id"]: b for b in bindings}
    for raw in m2["evidence"]:
        r = M2Evidence.model_validate_json(json.dumps(raw)).model_dump(mode="json")
        key = (r["occurrence_id"], r["validator_family"])
        if key in indexed or key not in expected:
            raise ValueError("foreign or duplicate evidence")
        b = byid[r["occurrence_id"]]; ref = m2["reference_populations"][b["dataset_id"]]
        if (r["payload_sha256"] != b["payload_sha256"] or r["dataset_id"] != b["dataset_id"]
                or r["reference_fingerprint"] != ref["train_reference_fingerprint"]
                or r["specification_fingerprint"] != ref["specification_fingerprint"]
                or r["configuration_fingerprint"] != config_fp
                or ref["statistical_fit_uses_test"] is not False):
            raise ValueError("source/reference/configuration mismatch or TEST leakage")
        indexed[key] = r
    if set(indexed) != expected:
        raise ValueError("incomplete M2 evidence")
    references = {}
    for dataset in sorted({b["dataset_id"] for b in bindings}):
        references[dataset] = {}
        for family in STATISTICAL:
            rows = sorted([{"occurrence_id": r["occurrence_id"], "raw_score": r["raw_score"],
                                "evidence_fingerprint": digest(r)} for r in indexed.values()
                           if r["dataset_id"] == dataset and r["validator_family"] == family
                           and r["status"] == "AVAILABLE" and r["raw_score"] is not None],
                          key=lambda r: r["occurrence_id"])
            references[dataset][family] = envelope("candidate-mid-ecdf-reference-v1", {
                "dataset_id": dataset, "family": family, "members": rows,
                "population": "Frozen historical candidates; within dataset/family; self included",
                "formula": "(count(reference < score) + 0.5 * count(reference == score)) / n",
                "direction": "LARGER_MEANS_WEAKER_STATISTICAL_SUPPORT", "minimum_n": minimum,
                "calibrated_probability": False, "real_test_used": False})
    vectors = []
    for b in bindings:
        rows = {f: indexed[b["occurrence_id"], f] for f in FAMILIES}
        normalized = {}
        for f in STATISTICAL:
            r = rows[f]; ref = references[b["dataset_id"]][f]
            score = r["raw_score"] if r["status"] == "AVAILABLE" else None
            percentile, state = mid_percentile(score, [v["raw_score"] for v in ref["members"]], minimum)
            normalized[f] = {"raw_score": r["raw_score"], "percentile": percentile, "state": state,
                "input_status": r["status"], "reference_fingerprint": ref["fingerprint"],
                "reference_n": len(ref["members"]), "direction": ref["direction"]}
        available = [normalized[f]["percentile"] for f in STATISTICAL]
        complete = all(v is not None for v in available)
        structural = {k: rows["authoritative_structure"][k] for k in (
            "status", "authoritative_validity", "reason_codes", "quantities", "uncertainty",
            "unsupported_fields", "rule_or_model_evidence")}
        vector = EvidenceVector(**b, m2_bundle_fingerprint=m2["fingerprint"],
            specification_fingerprint=rows["authoritative_structure"]["specification_fingerprint"],
            train_reference_fingerprint=rows["authoritative_structure"]["reference_fingerprint"],
            m2_configuration_fingerprint=config_fp,
            input_evidence_fingerprints={f: digest(r) for f, r in rows.items()},
            structural=structural, normalized=normalized,
            family_reasons={f: {k: rows[f][k] for k in ("reason_codes", "uncertainty", "unsupported_fields")} for f in FAMILIES},
            fusion={"version": "dependent-max-min-descriptive-v1", "complete": complete,
                    "uncalibrated_max": max(available) if complete else None,
                    "uncalibrated_min": min(available) if complete else None,
                    "independence_assumed": False, "probability_of_invalidity": None})
        value = vector.model_dump(mode="json")
        vectors.append({**value, "fingerprint": digest(value)})
    return envelope("m4-harmonized-evidence-v1", {"m2_bundle_fingerprint": m2["fingerprint"],
        "minimum_reference_size": minimum, "references": references, "vectors": vectors,
        "vector_content_fingerprint": digest(vectors), "real_test_used": False})


def verify_vector(raw: dict[str, Any]) -> EvidenceVector:
    value = {k: v for k, v in raw.items() if k != "fingerprint"}
    if digest(value) != raw.get("fingerprint"):
        raise ValueError("evidence vector fingerprint mismatch")
    return EvidenceVector.model_validate_json(json.dumps(value))


def dependence(vectors: list[dict[str, Any]], cutoff: float = 0.9) -> dict[str, Any]:
    result = {}
    for d in sorted({v["dataset_id"] for v in vectors}):
        group = [v for v in vectors if v["dataset_id"] == d]
        pairs = [(v["normalized"][STATISTICAL[0]]["percentile"],
                  v["normalized"][STATISTICAL[1]]["percentile"]) for v in group]
        complete = [(a, b) for a, b in pairs if a is not None and b is not None]
        rho = None
        if len(complete) > 1:
            a, b = [pd.Series(v).rank().to_numpy() for v in zip(*complete, strict=True)]
            if np.std(a) and np.std(b):
                rho = float(np.corrcoef(a, b)[0, 1])
        both = sum(a >= cutoff and b >= cutoff for a, b in complete)
        either = sum(a >= cutoff or b >= cutoff for a, b in complete)
        same = sum((a >= cutoff) == (b >= cutoff) for a, b in complete)
        result[d] = {"n": len(group), "paired_n": len(complete), "spearman": rho,
            "correlation_status": "AVAILABLE" if rho is not None else "UNDEFINED_SPARSE_OR_CONSTANT",
            "cutoff": cutoff, "concern_intersection": both, "concern_union": either,
            "concern_disagreement": either-both, "same_concern_state": same,
            "tail_jaccard": both/either if either else None,
            "independence_assumed": False,
            "family_availability": {f: sum(v["normalized"][f]["percentile"] is not None for v in group) for f in STATISTICAL}}
    return result


def decide(raw: dict[str, Any], policy: Policy) -> dict[str, Any]:
    vector = verify_vector(raw)
    missing = [f for f in policy.families if vector.normalized[f]["percentile"] is None]
    concerns = [f for f in policy.families if vector.normalized[f]["percentile"] is not None
                and vector.normalized[f]["percentile"] >= policy.review_cutoff]
    structure = vector.structural
    if structure["authoritative_validity"] == "INVALID":
        action, reason = "REJECT_STRUCTURAL", "AUTHORITATIVE_M2_VIOLATION"
    elif structure["status"] == "UNAVAILABLE" or missing:
        action, reason = "ABSTAIN", "REQUIRED_EVIDENCE_UNAVAILABLE"
    elif structure["status"] != "AVAILABLE":
        action, reason = "REVIEW_REQUIRED", "PARTIAL_STRUCTURAL_EVIDENCE"
    elif concerns:
        action, reason = "REVIEW_REQUIRED", "EXPLORATORY_STATISTICAL_CONCERN"
    else:
        action, reason = "PROVISIONAL_PASS", "SHADOW_CONDITIONS_SATISFIED_NOT_HUMAN_VALID"
    config = policy.model_dump(mode="json")
    return {"schema_version": "m5-shadow-decision-v1",
        "occurrence_id": vector.occurrence_id, "payload_sha256": vector.payload_sha256,
        "dataset_id": vector.dataset_id, "vector_fingerprint": raw["fingerprint"],
        "input_evidence_fingerprints": vector.input_evidence_fingerprints,
        "fusion_configuration_fingerprint": digest(config), "policy": config,
        "structural_judgment": structure["authoritative_validity"],
        "structural_status": structure["status"], "missing_required_families": missing,
        "missing_any_statistical_family": [f for f in STATISTICAL if vector.normalized[f]["percentile"] is None],
        "statistical_concern_families": concerns,
        "statistical_disagreement": (len(concerns) == 1 if len(policy.families) == 2 and not missing else None),
        "action": action, "reason_codes": [reason, *structure["reason_codes"]],
        "explanation": f"{reason}; contributing concerns={concerns}; missing required={missing}. "
                       "Percentiles and max/min indices are descriptive, not calibrated risk. "
                       "PROVISIONAL_PASS is not human-validated VALID.",
        "calibration_status": vector.calibration_status, "calibrated_probability": None,
        "dataset_contribution": "DEFERRED_PHASE5", "human_validity": "NOT_ESTABLISHED"}
