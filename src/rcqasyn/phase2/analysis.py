from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .annotations import gate_a, review_history, validate_proposals
from .common import digest, envelope
from .contracts import HumanDecision, Proposal


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
            *, fixture_only: bool = False) -> dict[str, Any]:
    attestation = gate_a(root, cohort, crosswalks, protocol, approval)
    fixture = cohort["population_kind"] == "synthetic_fixture"
    if fixture != fixture_only:
        raise ValueError("fixture provenance cannot be used for official research analysis")
    byrow = {r["review_row_id"]: r for r in cohort["records"]}
    validate_proposals(proposals, cohort, protocol)
    proposed = {}
    for raw in proposals:
        row = Proposal.model_validate_json(json.dumps(raw)).model_dump(mode="json")
        if row["review_row_id"] in proposed:
            raise ValueError("duplicate proposal")
        proposed[row["review_row_id"]] = row
    if set(proposed) != set(byrow):
        raise ValueError("proposal set differs from complete cohort")
    final = {}
    events = review_history(history)
    for event in events:
        if (event["cohort_fingerprint"] != cohort["fingerprint"]
                or event["protocol_fingerprint"] != protocol["fingerprint"]
                or event["population_kind"] != cohort["population_kind"]):
            raise ValueError("stale review event")
        for raw in event["decisions"]:
            decision = HumanDecision.model_validate_json(json.dumps(raw))
            if decision.review_row_id not in proposed:
                raise ValueError("foreign review identity")
            if decision.proposal_fingerprint != digest(proposed[decision.review_row_id]):
                raise ValueError("stale proposal approval")
            final[decision.review_row_id] = decision
    if set(final) != set(byrow) or any(r.review_status != "APPROVED" for r in final.values()):
        raise ValueError("official analysis requires explicit approval of every record")
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
    return envelope("b2-b3-approved-label-analysis-v1", {
        "official": not fixture, "population_kind": cohort["population_kind"],
        "cohort_fingerprint": cohort["fingerprint"], "protocol_fingerprint": protocol["fingerprint"],
        "crosswalk_fingerprints": cohort["crosswalk_fingerprints"],
        "gate_a_approval_fingerprint": digest(attestation.model_dump(mode="json")),
        "proposal_set_fingerprint": digest([proposed[k] for k in sorted(proposed)]),
        "review_event_fingerprints": [e["fingerprint"] for e in events],
        "approved_ledger_fingerprint": digest([final[k].model_dump(mode="json") for k in sorted(final)]),
        "approved_decisions": [final[k].model_dump(mode="json") for k in sorted(final)],
        "validation_status": "APPROVED_LABELS_VALIDATED",
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
