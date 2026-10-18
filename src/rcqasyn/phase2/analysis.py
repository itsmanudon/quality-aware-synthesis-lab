from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from rcqasyn.storage.ownership import bundle_lock

from .annotations import gate_a, review_history
from .approval import authenticate_review
from .common import digest, envelope
from .contracts import HumanDecision
from .fixture_approval import FixtureTrustAnchor


def _confusion(rows: list[dict[str, Any]], baseline: str) -> dict[str, Any]:
    determinate = [r for r in rows if r["label"] != "INDETERMINATE"]
    tp = sum(r["label"] == "INVALID" and not r[baseline] for r in determinate)
    fp = sum(r["label"] == "VALID" and not r[baseline] for r in determinate)
    fn = sum(r["label"] == "INVALID" and r[baseline] for r in determinate)
    tn = sum(r["label"] == "VALID" and r[baseline] for r in determinate)
    def ratio(n: int, d: int) -> float | None:
        return n / d if d else None
    return {"positive_class": "INVALID", "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "false_acceptance": fn, "false_rejection": fp,
            "false_acceptance_rate": ratio(fn, fn + tp),
            "false_rejection_rate": ratio(fp, fp + tn),
            "binary_denominator": len(determinate),
            "indeterminate": len(rows) - len(determinate)}


def analyze(root: Path, cohort: dict[str, Any], crosswalks: list[dict[str, Any]],
            protocol: dict[str, Any], approval: dict[str, Any],
            proposals: list[dict[str, Any]], history: Path,
            *, fixture_only: bool = False,
            supervisor_attestation: dict[str, Any] | None = None,
            trust_config: Path | None = None) -> dict[str, Any]:
    # No per-call policy or fixture flag can establish production authority.
    if fixture_only:
        raise ValueError("use the separate untrusted fixture analysis API")
    authenticate_review(root, cohort, crosswalks, protocol, approval, proposals,
                        history, supervisor_attestation, trust_config)
    raise ValueError("protected supervisor approval unavailable")


def diagnose_fixture_analysis(root: Path, cohort: dict[str, Any],
                               crosswalks: list[dict[str, Any]], protocol: dict[str, Any],
                               approval: dict[str, Any], proposals: list[dict[str, Any]],
                               history: Path, *, supervisor_attestation: dict[str, Any] | None,
                               fixture_anchor: FixtureTrustAnchor | None = None) -> dict[str, Any]:
    from .fixture_approval import diagnose_fixture_review

    if cohort.get("population_kind") != "synthetic_fixture":
        raise ValueError("fixture diagnostics refuse research populations")
    attestation = gate_a(root, cohort, crosswalks, protocol, approval)
    with bundle_lock(history):
        authenticated = diagnose_fixture_review(root, cohort, crosswalks, protocol, approval,
                                                 proposals, history, supervisor_attestation,
                                                 fixture_anchor)
        events = review_history(history)
    byrow = {r["review_row_id"]: r for r in cohort["records"]}
    proposed = {r["review_row_id"]: r for r in proposals}
    final = {d["review_row_id"]: HumanDecision.model_validate_json(json.dumps(d))
             for d in authenticated["approved_decisions"]}
    rows = []
    for key, source in byrow.items():
        proposal, decision = proposed[key], final[key]
        if any(proposal[k] != source[k] for k in ("occurrence_id", "payload_sha256", "dataset_id")):
            raise ValueError("proposal has foreign occurrence metadata")
        if (decision.occurrence_id != source["occurrence_id"]
                or decision.payload_sha256 != source["payload_sha256"]):
            raise ValueError("approved label has foreign occurrence binding")
        rows.append({"review_row_id": key, "occurrence_id": source["occurrence_id"],
                     "payload_sha256": source["payload_sha256"],
                     "dataset_id": source["dataset_id"], "requested_class": source["requested_class"],
                     "label": decision.human_final_label,
                     "b2": source["controls"]["b2"]["decision"]["accepted"],
                     "b3": source["controls"]["b3"]["decision"]["accepted"],
                     "b3_recorded_verdict": source["controls"]["b3"]["result"]["verdict"]})
    determinate = [r for r in rows if r["label"] != "INDETERMINATE"]
    errors = {b: {r["occurrence_id"] for r in determinate
                  if r[b] != (r["label"] == "VALID")} for b in ("b2", "b3")}
    return envelope("untrusted-fixture-analysis-v1", {
        "official": False, "production_approval": False,
        "population_kind": "synthetic_fixture",
        "cohort_fingerprint": cohort["fingerprint"], "protocol_fingerprint": protocol["fingerprint"],
        "crosswalk_fingerprints": cohort["crosswalk_fingerprints"],
        "gate_a_approval_fingerprint": digest(attestation.model_dump(mode="json")),
        "proposal_set_fingerprint": digest([proposed[k] for k in sorted(proposed)]),
        "review_event_fingerprints": [e["fingerprint"] for e in events],
        "approved_ledger_fingerprint": digest([final[k].model_dump(mode="json") for k in sorted(final)]),
        "approved_decisions": [final[k].model_dump(mode="json") for k in sorted(final)],
        "validation_status": "UNTRUSTED_FIXTURE_LABELS_DIAGNOSTIC",
        "supervisor_attestation_fingerprint": digest(authenticated["attestation"]),
        "trusted_supervisor_key_id": authenticated["trusted_key_id"],
        "trust_configuration_fingerprint": authenticated["trust_configuration_fingerprint"],
        "label_counts": dict(Counter(r["label"] for r in rows)),
        "b3_recorded_verdict_counts": dict(Counter(r["b3_recorded_verdict"] for r in rows)),
        "controls_unchanged": True, "control_view": "original recorded admission decisions",
        "overall": {b: _confusion(rows, b) for b in ("b2", "b3")},
        "by_dataset": {d: {b: _confusion([r for r in rows if r["dataset_id"] == d], b)
                          for b in ("b2", "b3")} for d in sorted({r["dataset_id"] for r in rows})},
        "by_requested_class": {c: {b: _confusion([r for r in rows if r["requested_class"] == c], b)
                                  for b in ("b2", "b3")}
                               for c in sorted({r["requested_class"] for r in rows})},
        "machine_disagreements": [r for r in rows if r["b2"] != r["b3"]],
        "shared_error_occurrence_ids": sorted(errors["b2"] & errors["b3"]),
        "individual_failure_cases": [r for r in determinate if
                                     r["occurrence_id"] in errors["b2"] | errors["b3"]],
        "rows": rows, "sampling_limitation": cohort["selection_limitations"],
        "interpretation": "Exploratory selected-cohort audit; no population-wide accuracy claim.",
    })
