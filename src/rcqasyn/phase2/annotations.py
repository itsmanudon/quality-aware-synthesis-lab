from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rcqasyn.storage.ownership import bundle_lock

from .cohort import validate_cohort
from .common import digest, envelope, read_bundle, verify_envelope, verify_sources, write_bundle
from .contracts import COHORT, PROTOCOL, GateAApproval, HumanDecision, Proposal, Rule


def annotation_protocol(specs: dict[str, Any]) -> dict[str, Any]:
    verify_envelope(specs, "dataset-specifications-v1")
    rules, fields, ambiguity = {}, {}, {}
    for artifact in specs["specifications"]:
        verify_envelope(artifact, "dataset-specification-v1")
        spec = artifact["specification"]
        fields[spec["dataset_id"]] = [*spec["features"],
            {"name": spec["target_semantics"]["target_column"], "type": "categorical",
             "documented_categories": spec["target_semantics"]["literal_labels"],
             "meaning": "Source binary token; original task mapping UNVERIFIED"}]
        ambiguity[spec["dataset_id"]] = spec["ambiguity"]
        for raw in spec["rules"]:
            rule = Rule.model_validate_json(json.dumps(raw))
            rules[rule.rule_id] = rule.model_dump(mode="json")
    return envelope(PROTOCOL, {
        "protocol_version": PROTOCOL, "validation_status": "DRAFT_REQUIRES_GATE_A_APPROVAL",
        "source_files": {k: v for a in specs["specifications"]
                         for k, v in a.get("source_files", {}).items()},
        "specifications_fingerprint": specs["fingerprint"], "rules": rules, "fields": fields,
        "ambiguity": ambiguity,
        "definitions": {
            "VALID": "No substantiated authoritative violation, with sufficient evidence "
            "for a positive record-level judgment.",
            "INVALID": "A specific supported applicable authoritative violation exists.",
            "INDETERMINATE": "Evidence does not support a defensible conclusion."},
        "separate_concepts": ["record_validity", "uncertainty", "redundancy", "contribution"],
        "prohibitions": ["rare/unseen/outlier/duplicate/low probability is not invalidity",
                         "machine controls are not annotation evidence"],
    })


def packets(cohort: dict[str, Any], protocol: dict[str, Any]
            ) -> tuple[dict[str, Any], dict[str, Any]]:
    verify_envelope(cohort, COHORT)
    verify_envelope(protocol, PROTOCOL)
    primary, mapping = [], []
    for row in cohort["records"]:
        blind = "blind-" + digest({"cohort": cohort["fingerprint"],
                                   "review_row_id": row["review_row_id"]})
        primary.append({"blinded_review_id": blind, "dataset_id": row["dataset_id"],
                        "payload": row["payload"], "payload_sha256": row["payload_sha256"],
                        "field_definitions": protocol["fields"][row["dataset_id"]],
                        "allowed_evidence": [rule for _, rule in sorted(protocol["rules"].items())
                                             if rule["rule_id"].startswith(row["dataset_id"] + ":")
                                             and rule["authority"] == "AUTHORITATIVE"],
                        "known_ambiguity": protocol["ambiguity"][row["dataset_id"]]})
        mapping.append({"blinded_review_id": blind, "review_row_id": row["review_row_id"],
                        "occurrence_id": row["occurrence_id"], "dataset_id": row["dataset_id"],
                        "payload_sha256": row["payload_sha256"]})
    byrow = {m["review_row_id"]: p for m, p in zip(mapping, primary, strict=True)}
    public = envelope("blind-packets-v1", {
        "validation_status": "PENDING_INDEPENDENT_VERIFICATION",
        "cohort_fingerprint": cohort["fingerprint"], "protocol_fingerprint": protocol["fingerprint"],
        "primary": primary, "overlap": [byrow[r] for r in cohort["overlap_review_row_ids"]],
    })
    private = envelope("private-review-map-v1", {
        "cohort_fingerprint": cohort["fingerprint"], "protocol_fingerprint": protocol["fingerprint"],
        "public_packet_fingerprint": public["fingerprint"], "mapping": mapping,
        "distribution": "INTERNAL_ONLY; do not send with blind packets",
    })
    return public, private


def gate_a(root: Path, cohort: dict[str, Any], crosswalks: list[dict[str, Any]],
           protocol: dict[str, Any], approval: dict[str, Any]) -> GateAApproval:
    validate_cohort(root, cohort, crosswalks)
    verify_envelope(protocol, PROTOCOL)
    verify_sources(root, protocol["source_files"])
    value = GateAApproval.model_validate_json(json.dumps(approval))
    if (value.cohort_fingerprint != cohort["fingerprint"]
            or value.protocol_fingerprint != protocol["fingerprint"]
            or list(value.crosswalk_fingerprints) != cohort["crosswalk_fingerprints"]):
        raise ValueError("Gate A approval is stale or bound to different inputs")
    return value


def load_proposals(checkpoint: Path, cohort: dict[str, Any],
                   protocol: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(checkpoint.glob("batch-*")):
        batch = read_bundle(path)
        verify_envelope(batch, "agent-proposal-batch-v1")
        if (batch["cohort_fingerprint"] != cohort["fingerprint"]
                or batch["protocol_fingerprint"] != protocol["fingerprint"]
                or batch["population_kind"] != cohort["population_kind"]):
            raise ValueError("stale checkpoint")
        for raw in batch["proposals"]:
            rows.append(Proposal.model_validate_json(json.dumps(raw)).model_dump(mode="json"))
    if len({r["review_row_id"] for r in rows}) != len(rows):
        raise ValueError("duplicate proposal identity across checkpoint batches")
    validate_proposals(rows, cohort, protocol)
    return rows


def validate_proposals(rows: list[dict[str, Any]], cohort: dict[str, Any],
                       protocol: dict[str, Any]) -> None:
    sources = {r["review_row_id"]: r for r in cohort["records"]}
    for raw in rows:
        row = Proposal.model_validate_json(json.dumps(raw)).model_dump(mode="json")
        source = sources.get(row["review_row_id"])
        if source is None or any(row[k] != source[k] for k in
                                 ("occurrence_id", "payload_sha256", "dataset_id")):
            raise ValueError("proposal has foreign occurrence metadata")
        for evidence in row["supporting_evidence_ids"]:
            rule = protocol["rules"].get(evidence)
            if (rule is None or not evidence.startswith(row["dataset_id"] + ":")
                    or rule["authority"] != "AUTHORITATIVE"):
                raise ValueError("proposal evidence must be applicable authoritative evidence")


def pending_batches(cohort: dict[str, Any], protocol: dict[str, Any], checkpoint: Path,
                    batch_size: int = 10) -> list[list[dict[str, Any]]]:
    if batch_size < 1:
        raise ValueError("batch size must be positive")
    public, private = packets(cohort, protocol)
    done = {r["review_row_id"] for r in load_proposals(checkpoint, cohort, protocol)}
    remaining = [p for p, m in zip(public["primary"], private["mapping"], strict=True)
                 if m["review_row_id"] not in done]
    return [remaining[i:i + batch_size] for i in range(0, len(remaining), batch_size)]


def submit_batch(root: Path, cohort: dict[str, Any], crosswalks: list[dict[str, Any]],
                 protocol: dict[str, Any], approval: dict[str, Any],
                 answers: list[dict[str, Any]], model: str, execution: str,
                 checkpoint: Path) -> Path:
    """Ingest external agent answers to annotation-only packets; never call a provider."""
    attestation = gate_a(root, cohort, crosswalks, protocol, approval)
    _, private = packets(cohort, protocol)
    mapping = {r["blinded_review_id"]: r for r in private["mapping"]}
    if not answers:
        raise ValueError("empty proposal batch")
    proposals = []
    for answer in answers:
        expected = {"blinded_review_id", "proposed_label", "proposed_rationale",
                    "supporting_evidence_ids", "uncertainty_or_ambiguity"}
        if set(answer) != expected or answer["blinded_review_id"] not in mapping:
            raise ValueError("answer must use the blinded annotation-only schema")
        identity = mapping[answer["blinded_review_id"]]
        evidence = answer["supporting_evidence_ids"]
        if any(e not in protocol["rules"] or not e.startswith(identity["dataset_id"] + ":")
               for e in evidence):
            raise ValueError("unsupported annotation evidence")
        if any(
                protocol["rules"][e]["authority"] != "AUTHORITATIVE" for e in evidence):
            raise ValueError("determinate annotation requires applicable authoritative evidence")
        proposal = Proposal.model_validate_json(json.dumps({
            **{k: v for k, v in identity.items() if k != "blinded_review_id"},
            **{k: v for k, v in answer.items() if k != "blinded_review_id"},
            "annotator_model_or_agent_version": model,
            "proposal_timestamp_or_execution_identity": execution,
        }))
        proposals.append(proposal.model_dump(mode="json"))
    if len({r["review_row_id"] for r in proposals}) != len(proposals):
        raise ValueError("duplicate batch answer")
    batch = envelope("agent-proposal-batch-v1", {
        "cohort_fingerprint": cohort["fingerprint"], "protocol_fingerprint": protocol["fingerprint"],
        "population_kind": cohort["population_kind"], "gate_a_approval_fingerprint": digest(
            attestation.model_dump(mode="json")),
        "proposals": proposals, "validation_status": "PENDING_HUMAN_APPROVAL"})
    path = checkpoint / ("batch-" + batch["fingerprint"])
    with bundle_lock(checkpoint):
        existing = load_proposals(checkpoint, cohort, protocol)
        seen = {r["review_row_id"] for r in existing}
        if path.exists():
            return write_bundle(path, batch)
        if seen & {r["review_row_id"] for r in proposals}:
            raise ValueError("proposal already exists; preserve its original version")
        return write_bundle(path, batch)


def record_review(root: Path, cohort: dict[str, Any], crosswalks: list[dict[str, Any]],
                  protocol: dict[str, Any], approval: dict[str, Any],
                  proposals: list[dict[str, Any]], decisions: list[dict[str, Any]],
                  history: Path) -> Path:
    gate_a(root, cohort, crosswalks, protocol, approval)
    byrow = {r["review_row_id"]: Proposal.model_validate_json(json.dumps(r)).model_dump(mode="json")
             for r in proposals}
    validate_proposals(proposals, cohort, protocol)
    if len(byrow) != len(proposals):
        raise ValueError("duplicate proposal")
    records = []
    for raw in decisions:
        decision = HumanDecision.model_validate_json(json.dumps(raw))
        original = byrow.get(decision.review_row_id)
        if (original is None or decision.proposal_fingerprint != digest(original)
                or decision.occurrence_id != original["occurrence_id"]
                or decision.payload_sha256 != original["payload_sha256"]):
            raise ValueError("review decision has stale proposal/occurrence binding")
        if (decision.human_final_label is not None
                and decision.human_final_label != original["proposed_label"]
                and not decision.human_correction_note.strip()):
            raise ValueError("a changed label requires a correction note")
        records.append(decision.model_dump(mode="json"))
    if not records or len({r["review_row_id"] for r in records}) != len(records):
        raise ValueError("empty or duplicate review events")
    with bundle_lock(history):
        chain = review_history(history)
        if any(e["cohort_fingerprint"] != cohort["fingerprint"] or
               e["protocol_fingerprint"] != protocol["fingerprint"] for e in chain):
            raise ValueError("stale review history")
        event = envelope("supervisor-review-event-v1", {
            "cohort_fingerprint": cohort["fingerprint"],
            "protocol_fingerprint": protocol["fingerprint"],
            "population_kind": cohort["population_kind"],
            "previous_event_fingerprint": chain[-1]["fingerprint"] if chain else None,
            "sequence": len(chain) + 1, "decisions": records,
            "proposal_fingerprints": {r["review_row_id"]: digest(byrow[r["review_row_id"]])
                                      for r in records}})
        return write_bundle(history / f"event-{len(chain) + 1:06d}", event)


def review_history(history: Path) -> list[dict[str, Any]]:
    events, previous = [], None
    for index, path in enumerate(sorted(history.glob("event-*")), 1):
        event = read_bundle(path)
        verify_envelope(event, "supervisor-review-event-v1")
        if event["sequence"] != index or event["previous_event_fingerprint"] != previous:
            raise ValueError("review correction history is missing, reordered or modified")
        previous = event["fingerprint"]
        events.append(event)
    return events
