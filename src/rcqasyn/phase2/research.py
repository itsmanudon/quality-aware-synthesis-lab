"""Supervisor-reviewed research provenance, without production authentication.

Fingerprints detect changed inputs. They do not establish human identity or resist
an agent able to rewrite files and submit claims with the same permissions.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from rcqasyn.contracts._base import ContractModel, NonEmptyStr
from rcqasyn.storage.ownership import bundle_lock

from .annotations import load_proposals, packets, validate_proposals
from .cohort import validate_cohort
from .common import csv_rows, digest, envelope, verify_envelope, verify_sources, write_bundle
from .contracts import PROTOCOL, Hex32, Label, Proposal

RESEARCH = {"workflow": "SUPERVISOR_REVIEWED_RESEARCH", "production_approval": False,
            "cryptographically_authenticated": False}
HUMAN_FIELDS = {"human_review_status", "human_final_label", "human_correction_note",
                "human_reviewer_reference"}


class ResearchScopeApproval(ContractModel):
    schema_version: Literal["research-scope-approval-v1"] = "research-scope-approval-v1"
    purpose: Literal["COHORT_AND_RUBRIC_ONLY"] = "COHORT_AND_RUBRIC_ONLY"
    decision: Literal["APPROVED"]
    population_kind: Literal["research", "synthetic_fixture"]
    cohort_fingerprint: Hex32
    crosswalk_fingerprints: tuple[Hex32, ...]
    protocol_fingerprint: Hex32
    specifications_fingerprint: Hex32
    research_rubric_fingerprint: Hex32
    supervisor_reference: NonEmptyStr
    implementation_owner_reference: NonEmptyStr
    approval_provenance: NonEmptyStr
    scientific_decisions: NonEmptyStr


class ResearchConfirmation(ContractModel):
    schema_version: Literal["research-ledger-confirmation-v1"] = "research-ledger-confirmation-v1"
    decision: Literal["CONFIRM_ALL_REVIEWED_LABELS_FOR_RESEARCH_ANALYSIS"]
    reviewed_ledger_fingerprint: Hex32
    scope_approval_fingerprint: Hex32
    supervisor_reference: NonEmptyStr
    confirmation_provenance: NonEmptyStr


class ResearchDecision(ContractModel):
    human_review_status: Literal["REVIEWED"]
    human_final_label: Label
    human_correction_note: str
    human_reviewer_reference: NonEmptyStr


def _identity(value: str) -> str:
    return value.strip().casefold()


def research_rubric(protocol: dict[str, Any]) -> dict[str, Any]:
    verify_envelope(protocol, PROTOCOL)
    return envelope("research-annotation-rubric-v1", {
        **RESEARCH, "protocol_fingerprint": protocol["fingerprint"],
        "definitions": protocol["definitions"], "rules": protocol["rules"],
        "fields": protocol["fields"], "ambiguity": protocol["ambiguity"],
        "separate_concepts": protocol["separate_concepts"],
        "prohibitions": protocol["prohibitions"],
        "instructions": [
            ("Assess the original payload against applicable AUTHORITATIVE rules only. "
            "Cite rule IDs and concrete payload observations in the rationale."),
            ("INVALID requires a specific substantiated authoritative violation. "
            "Declared primitive types and nominal categories are applicable; source numerical "
            "bounds and TRAIN support are not universal physical validity limits."),
            ("VALID requires sufficient positive record-level evidence. Absence of a detected "
            "violation alone is insufficient. Explain what the evidence establishes."),
            ("Use INDETERMINATE where a defensible conclusion depends on unresolved target "
            "mapping, physical meaning, units, or cross-field constraints. Do not invent them."),
            ("Preserved source missing token '?' / null is not automatically invalid. "
            "Document missingness and use INDETERMINATE when it prevents judgment."),
            ("Treat positive/negative as literal source tokens. Do not infer the original "
            "multiclass mapping from a dataset name or infer label truth from requested_class."),
            ("Keep validity, uncertainty, redundancy and contribution separate. Rare, unseen, "
            "outlier, duplicate and low probability are not validity violations."),
            ("Annotate blinded packets without B1/B2/B3 results or machine scores as evidence. "
            "Give every proposal a rationale, applicable evidence IDs and uncertainty statement."),
            ("The supervisor personally reviews every row, explicitly records a final label "
            "including INDETERMINATE where appropriate, and explains changed labels. "
            "No proposal becomes a human decision automatically."),
        ],
        "scientific_decisions_pending": "Supervisor must explicitly accept these conservative "
        "limits or request a new source-backed rubric version before proposals are generated.",
    })


def bindings(cohort: dict[str, Any], protocol: dict[str, Any]) -> dict[str, Any]:
    return {"population_kind": cohort["population_kind"],
            "cohort_fingerprint": cohort["fingerprint"],
            "crosswalk_fingerprints": cohort["crosswalk_fingerprints"],
            "protocol_fingerprint": protocol["fingerprint"],
            "specifications_fingerprint": protocol["specifications_fingerprint"],
            "research_rubric_fingerprint": research_rubric(protocol)["fingerprint"]}


def validate_scope(root: Path, cohort: dict[str, Any], crosswalks: list[dict[str, Any]],
                   protocol: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    validate_cohort(root, cohort, crosswalks)
    verify_envelope(protocol, PROTOCOL)
    verify_sources(root, protocol["source_files"])
    scope = ResearchScopeApproval.model_validate_json(json.dumps(raw)).model_dump(mode="json")
    if any(scope[k] != v for k, v in bindings(cohort, protocol).items()):
        raise ValueError("research scope approval is stale or bound to different inputs")
    if _identity(scope["supervisor_reference"]) == _identity(scope["implementation_owner_reference"]):
        raise ValueError("implementation owner cannot self-approve research scope")
    return scope


def submit_research_batch(root: Path, cohort: dict[str, Any], crosswalks: list[dict[str, Any]],
                          protocol: dict[str, Any], approval: dict[str, Any],
                          answers: list[dict[str, Any]], model: str, execution: str,
                          checkpoint: Path) -> Path:
    scope = validate_scope(root, cohort, crosswalks, protocol, approval)
    if _identity(model) == _identity(scope["supervisor_reference"]):
        raise ValueError("known agent self-approval is forbidden")
    _, private = packets(cohort, protocol)
    mapping = {r["blinded_review_id"]: r for r in private["mapping"]}
    expected = {"blinded_review_id", "proposed_label", "proposed_rationale",
                "supporting_evidence_ids", "uncertainty_or_ambiguity"}
    proposals = []
    for answer in answers:
        if set(answer) != expected or answer["blinded_review_id"] not in mapping:
            raise ValueError("answer must use the blinded annotation-only schema")
        identity = mapping[answer["blinded_review_id"]]
        proposals.append(Proposal.model_validate_json(json.dumps({
            **{k: v for k, v in identity.items() if k != "blinded_review_id"},
            **{k: v for k, v in answer.items() if k != "blinded_review_id"},
            "annotator_model_or_agent_version": model,
            "proposal_timestamp_or_execution_identity": execution,
        })).model_dump(mode="json"))
    if not proposals or len({p["review_row_id"] for p in proposals}) != len(proposals):
        raise ValueError("empty or duplicate research proposal batch")
    validate_proposals(proposals, cohort, protocol)
    batch = envelope("agent-proposal-batch-v1", {
        **RESEARCH, **bindings(cohort, protocol),
        "research_scope_approval_fingerprint": digest(scope), "proposals": proposals,
        "validation_status": "PENDING_HUMAN_APPROVAL"})
    path = checkpoint / ("batch-" + batch["fingerprint"])
    with bundle_lock(checkpoint):
        existing = load_research_proposals(checkpoint, cohort, protocol, scope)
        if path.exists():
            return write_bundle(path, batch)
        if {p["review_row_id"] for p in existing} & {p["review_row_id"] for p in proposals}:
            raise ValueError("proposal already exists; preserve its original version")
        return write_bundle(path, batch)


def load_research_proposals(checkpoint: Path, cohort: dict[str, Any], protocol: dict[str, Any],
                            scope: dict[str, Any]) -> list[dict[str, Any]]:
    from .common import read_bundle

    rows = load_proposals(checkpoint, cohort, protocol)
    for path in checkpoint.glob("batch-*"):
        batch = read_bundle(path)
        if (batch.get("research_scope_approval_fingerprint") != digest(scope)
                or any(batch.get(k) != v for k, v in RESEARCH.items())
                or any(batch.get(k) != v for k, v in bindings(cohort, protocol).items())):
            raise ValueError("research checkpoint has different scope or workflow")
    return rows


def review_rows(proposals: list[dict[str, Any]], cohort: dict[str, Any],
                protocol: dict[str, Any]) -> list[dict[str, Any]]:
    validate_proposals(proposals, cohort, protocol)
    byrow = {p["review_row_id"]: p for p in proposals}
    expected = {r["review_row_id"] for r in cohort["records"]}
    if len(byrow) != len(proposals) or set(byrow) != expected:
        raise ValueError("research ledger requires exactly the complete cohort proposal set")
    rows = []
    for source in cohort["records"]:
        p = byrow[source["review_row_id"]]
        rows.append({**{k: p[k] for k in (
            "review_row_id", "occurrence_id", "dataset_id", "payload_sha256", "proposed_label",
            "proposed_rationale", "supporting_evidence_ids", "uncertainty_or_ambiguity")},
            "original_review_row": source["original_review_row"],
            "payload": source["payload"], "proposal_fingerprint": digest(p),
            "human_review_status": "PENDING", "human_final_label": None,
            "human_correction_note": "", "human_reviewer_reference": ""})
    return rows


def _ledger(cohort: dict[str, Any], protocol: dict[str, Any], scope: dict[str, Any],
            proposals: list[dict[str, Any]], rows: list[dict[str, Any]], *, version: int,
            previous: str | None, provenance: str, reviewed: bool) -> dict[str, Any]:
    return envelope("research-review-ledger-v1", {
        **RESEARCH, **bindings(cohort, protocol), "scope_approval_fingerprint": digest(scope),
        "proposal_set_fingerprint": digest(sorted(proposals, key=lambda p: p["review_row_id"])),
        "ledger_version": version, "previous_ledger_fingerprint": previous,
        "human_review_provenance": provenance,
        "validation_status": "REVIEWED_AWAITING_EXPLICIT_CONFIRMATION" if reviewed
        else "PENDING_PERSONAL_SUPERVISOR_REVIEW", "rows": rows})


def export_research_review(root: Path, cohort: dict[str, Any], crosswalks: list[dict[str, Any]],
                           protocol: dict[str, Any], approval: dict[str, Any],
                           proposals: list[dict[str, Any]]) -> dict[str, Any]:
    scope = validate_scope(root, cohort, crosswalks, protocol, approval)
    _supervisor_is_not_agent(scope, proposals)
    return _ledger(cohort, protocol, scope, proposals, review_rows(proposals, cohort, protocol),
                   version=1, previous=None, provenance="", reviewed=False)


def _supervisor_is_not_agent(scope: dict[str, Any], proposals: list[dict[str, Any]]) -> None:
    if _identity(scope["supervisor_reference"]) in {
            _identity(p["annotator_model_or_agent_version"]) for p in proposals}:
        raise ValueError("known agent self-approval is forbidden")


def _reviewed_rows(rows: list[dict[str, Any]], proposals: list[dict[str, Any]],
                   cohort: dict[str, Any], protocol: dict[str, Any],
                   scope: dict[str, Any]) -> list[dict[str, Any]]:
    _supervisor_is_not_agent(scope, proposals)
    expected = {r["review_row_id"]: r for r in review_rows(proposals, cohort, protocol)}
    if (len(rows) != len(expected) or len({r["review_row_id"] for r in rows}) != len(rows)
            or {r["review_row_id"] for r in rows} != set(expected)):
        raise ValueError("reviewed ledger must contain every cohort row exactly once")
    byrow = {}
    for row in rows:
        source = expected[row["review_row_id"]]
        if (set(row) != set(source) or any(row[k] != v for k, v in source.items()
                                         if k not in HUMAN_FIELDS)):
            raise ValueError("reviewed row has changed source or proposal context")
        decision = ResearchDecision.model_validate_json(json.dumps(
            {k: row[k] for k in HUMAN_FIELDS})).model_dump(mode="json")
        if _identity(decision["human_reviewer_reference"]) != _identity(scope["supervisor_reference"]):
            raise ValueError("every row must be explicitly reviewed by the named supervisor")
        if (decision["human_final_label"] != source["proposed_label"]
                and not decision["human_correction_note"].strip()):
            raise ValueError("changed labels require a supervisor correction note")
        byrow[row["review_row_id"]] = {**source, **decision}
    return [byrow[r["review_row_id"]] for r in cohort["records"]]


def import_research_review(root: Path, cohort: dict[str, Any], crosswalks: list[dict[str, Any]],
                           protocol: dict[str, Any], approval: dict[str, Any],
                           proposals: list[dict[str, Any]], rows: list[dict[str, Any]],
                           provenance: str, previous: dict[str, Any] | None = None
                           ) -> dict[str, Any]:
    scope = validate_scope(root, cohort, crosswalks, protocol, approval)
    if not provenance.strip():
        raise ValueError("explicit supervisor review provenance is required")
    if previous is not None:
        validate_research_ledger(root, cohort, crosswalks, protocol, scope, proposals, previous)
    reviewed = _reviewed_rows(rows, proposals, cohort, protocol, scope)
    return _ledger(cohort, protocol, scope, proposals, reviewed,
                   version=previous["ledger_version"] + 1 if previous else 1,
                   previous=previous["fingerprint"] if previous else None,
                   provenance=provenance, reviewed=True)


def validate_research_ledger(root: Path, cohort: dict[str, Any], crosswalks: list[dict[str, Any]],
                             protocol: dict[str, Any], approval: dict[str, Any],
                             proposals: list[dict[str, Any]], ledger: dict[str, Any]
                             ) -> dict[str, Any]:
    scope = validate_scope(root, cohort, crosswalks, protocol, approval)
    verify_envelope(ledger, "research-review-ledger-v1")
    rows = _reviewed_rows(ledger["rows"], proposals, cohort, protocol, scope)
    version, previous = ledger["ledger_version"], ledger["previous_ledger_fingerprint"]
    if (type(version) is not int or version < 1 or (version == 1 and previous is not None)
            or (version > 1 and (not isinstance(previous, str) or len(previous) != 64))
            or not ledger["human_review_provenance"].strip()):
        raise ValueError("invalid research ledger version or review provenance")
    expected = _ledger(cohort, protocol, scope, proposals, rows, version=version,
                       previous=previous, provenance=ledger["human_review_provenance"], reviewed=True)
    if ledger != expected:
        raise ValueError("research ledger bindings or review state differ")
    return scope


def confirm_research_ledger(root: Path, cohort: dict[str, Any], crosswalks: list[dict[str, Any]],
                            protocol: dict[str, Any], approval: dict[str, Any],
                            proposals: list[dict[str, Any]], ledger: dict[str, Any],
                            confirmation: dict[str, Any]) -> dict[str, Any]:
    scope = validate_research_ledger(root, cohort, crosswalks, protocol, approval, proposals, ledger)
    confirmed = ResearchConfirmation.model_validate_json(json.dumps(confirmation)).model_dump(mode="json")
    if (confirmed["reviewed_ledger_fingerprint"] != ledger["fingerprint"]
            or confirmed["scope_approval_fingerprint"] != digest(scope)
            or _identity(confirmed["supervisor_reference"]) != _identity(scope["supervisor_reference"])):
        raise ValueError("explicit supervisor confirmation does not match reviewed ledger and scope")
    return confirmed


def read_review_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() != ".csv":
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(value, list) or any(not isinstance(r, dict) for r in value):
            raise ValueError("review JSON must be the exported list of rows")
        return value
    rows: list[dict[str, Any]] = list(csv_rows(path))
    for row in rows:
        for key in ("payload", "supporting_evidence_ids", "original_review_row"):
            row[key] = json.loads(row[key])
        row["human_final_label"] = row["human_final_label"] or None
    return rows


def scope_checkpoint(cohort: dict[str, Any], crosswalks: list[dict[str, Any]],
                     protocol: dict[str, Any], specs: dict[str, Any]) -> dict[str, Any]:
    return envelope("research-scope-checkpoint-v1", {
        **RESEARCH, **bindings(cohort, protocol),
        "validation_status": "AWAITING_EXPLICIT_COHORT_AND_RUBRIC_APPROVAL",
        "crosswalk_set_fingerprint": digest(cohort["crosswalk_fingerprints"]),
        "crosswalk_summaries": [{"dataset_id": cw["records"][0]["dataset_id"],
                                 "fingerprint": cw["fingerprint"], **cw["summary"]}
                                for cw in crosswalks],
        "cohort_records": len(cohort["records"]),
        "overlap_records": len(cohort["overlap_review_row_ids"]),
        "semantics_gaps": specs["semantics_gaps"],
        "rubric": research_rubric(protocol),
        "selection_limitations": cohort["selection_limitations"],
        "real_labels_generated": False, "cohort_or_rubric_approved": False,
    })


def checkpoint_text(checkpoint: dict[str, Any]) -> str:
    rubric = checkpoint["rubric"]
    lines = ["# Phase-2 cohort and exact rubric approval checkpoint", "",
             "Status: awaiting personal supervisor approval. No real labels generated.", "",
             ("Implementation scope approval does not approve this cohort or rubric. "
             "The production-authenticated approval path remains disabled."), ""]
    for key in ("cohort_fingerprint", "crosswalk_set_fingerprint", "protocol_fingerprint",
                "specifications_fingerprint", "research_rubric_fingerprint"):
        lines.append(f"- {key}: `{checkpoint[key]}`")
    lines += ["", ("The crosswalk-set fingerprint hashes the ordered list of the three "
              "individual crosswalk fingerprints; it does not replace them."), ""]
    for cw in checkpoint["crosswalk_summaries"]:
        lines.append(f"- {cw['dataset_id']}: {cw['occurrences']} occurrences; `{cw['fingerprint']}`")
    lines += ["", (f"Preserved cohort: {checkpoint['cohort_records']} records. "
              f"Preserved review overlap: {checkpoint['overlap_records']} records."),
              ("Logical CSV row 94 (data record 93) retains its payload and binds to "
              "page-blocks0 source occurrence 1. The original and five corrected metadata "
              "fields remain in gate-a-v3/cohort/row94.md and before-after.csv."), "",
              checkpoint["selection_limitations"], "", "## Exact annotation rubric", ""]
    for label, definition in rubric["definitions"].items():
        lines.append(f"- **{label}:** {definition}")
    lines += ["", *[f"{i}. {text}" for i, text in enumerate(rubric["instructions"], 1)],
              "", "## Exact applicable rules and source declarations", ""]
    for dataset, fields in rubric["fields"].items():
        lines += [f"### {dataset}", "", "Fields (source spelling retained):", ""]
        for field in fields:
            declaration = field.get("source_declaration", field.get("documented_categories"))
            lines.append(f"- {field['name']}: {declaration}")
        lines.append("")
        for rule in rubric["rules"].values():
            if rule["rule_id"].startswith(dataset + ":"):
                lines.append(f"- `{rule['rule_id']}` [{rule['authority']}]: {rule['statement']} "
                             f"Evidence: {', '.join(rule['evidence']) or 'none'}; "
                             f"hard rejection allowed: {rule['hard_rejection_allowed']}.")
        lines += ["", *["- " + a for a in rubric["ambiguity"][dataset]], ""]
    lines += ["## Unresolved scientific decisions for explicit supervisor disposition", "",
              ("For each dataset, original multiclass-to-binary mapping, physical field "
              "meanings/units and cross-field hard constraints remain unverified. "
              "Proposed disposition: retain these unknowns, use literal source labels, "
              "add no physical rules, and use INDETERMINATE where they prevent a "
              "defensible record-level judgment. Source numerical ranges and TRAIN "
              "statistics remain descriptive; neither supplies a universal hard bound."), "",
              ("Accept the preserved nonrepresentative cohort and the documented page-blocks0 "
              "TRAIN/TEST exact-value overlap as limitations. The fixed 40-row overlap "
              "is retained, but one supervisor's review cannot establish inter-rater agreement."), "",
              ("Confirm that VALID requires positive sufficient evidence and that absence "
              "of a detected schema violation alone is insufficient. This may yield many "
              "INDETERMINATE proposals; no target class correctness is inferred."), "",
              "## Requested approval", "",
              ("Explicitly approve the cohort and exact rubric fingerprints above and state "
              "whether you accept the proposed conservative disposition of these unresolved "
              "decisions. Corrections require a new source-backed version before proposals. "
              "Only after approval will the agent prepare 120 proposals for personal review. "
              "That later review and exact reviewed-ledger confirmation are separate gates."), "",
              ("Fingerprints bind file content; this workflow does not cryptographically "
              "authenticate people or resist a malicious agent with the same permissions."), ""]
    return "\n".join(lines)
