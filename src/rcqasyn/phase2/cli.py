from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from rcqasyn.config import discover_project_root
from rcqasyn.storage.artifacts import read_json

from .analysis import analyze
from .annotations import (
    gate_a,
    import_supervisor_approval,
    load_proposals,
    pending_batches,
    record_review,
    submit_batch,
)
from .approval import build_approval_ledger, read_approval_json
from .common import csv_rows, csv_text, digest, envelope, read_bundle, verify_envelope, write_bundle
from .workflow import (
    DEFAULT_OUTPUT,
    derivative_destination,
    load_preparation,
    prepare,
    validate_preparation,
)

app = typer.Typer(help="Occurrence-bound Phase-2 preparation and approval-gated review.")


def context(root: Path, bundle: Path) -> tuple[Any, ...]:
    validate_preparation(root, bundle)
    return load_preparation(bundle)


@app.command("prepare")
def prepare_command(output: Path = DEFAULT_OUTPUT, dry_run: bool = False,
                    source_root: Path | None = None) -> None:
    """Reconstruct new derivatives; never generate annotation labels."""
    root = discover_project_root()
    result = prepare(source_root or root, root / output, dry_run=dry_run, artifact_root=root)
    typer.echo(json.dumps(result, indent=2))


@app.command("validate")
def validate_command(bundle: Path = DEFAULT_OUTPUT, source_root: Path | None = None) -> None:
    """Independently rebuild bindings, order, schemas and historical integrity."""
    root = discover_project_root()
    typer.echo(json.dumps(validate_preparation(source_root or root, root / bundle), indent=2))


@app.command("batches")
def batches_command(approval: Path, checkpoint: Path, output: Path,
                    bundle: Path = DEFAULT_OUTPUT, batch_size: int = 10,
                    source_root: Path | None = None) -> None:
    """After Gate A, export stable pending blinded requests. No model is called."""
    root = discover_project_root()
    checkpoint = derivative_destination(root, checkpoint)
    output = derivative_destination(root, output)
    cohort, crosswalks, protocol, _ = context(source_root or root, root / bundle)
    gate_a(source_root or root, cohort, crosswalks, protocol, read_json(approval))
    batches = pending_batches(cohort, protocol, checkpoint, batch_size)
    value = envelope("annotation-batch-requests-v1", {
        "cohort_fingerprint": cohort["fingerprint"],
        "protocol_fingerprint": protocol["fingerprint"], "batches": batches,
        "validation_status": "REQUESTS_ONLY_NO_LABELS"})
    write_bundle(output, value)
    typer.echo(str(output))


@app.command("submit")
def submit_command(approval: Path, answers: Path, model: str, execution: str,
                   checkpoint: Path, bundle: Path = DEFAULT_OUTPUT,
                   source_root: Path | None = None) -> None:
    """Validate agent answers after Gate A; keep immutable proposal batches."""
    root = discover_project_root()
    checkpoint = derivative_destination(root, checkpoint)
    cohort, crosswalks, protocol, _ = context(source_root or root, root / bundle)
    path = submit_batch(source_root or root, cohort, crosswalks, protocol, read_json(approval),
                        read_json(answers), model, execution, checkpoint)
    typer.echo(str(path))


@app.command("review-export")
def review_export_command(checkpoint: Path, output: Path,
                          bundle: Path = DEFAULT_OUTPUT, source_root: Path | None = None,
                          history: Path | None = None) -> None:
    """Export proposals for supervision; an export conveys no approval."""
    root = discover_project_root()
    checkpoint = derivative_destination(root, checkpoint)
    output = derivative_destination(root, output)
    cohort, _, protocol, _ = context(source_root or root, root / bundle)
    proposals = load_proposals(checkpoint, cohort, protocol)
    byrow = {r["review_row_id"]: r for r in cohort["records"]}
    submitted = {}
    if history is not None:
        from .annotations import review_history
        history = derivative_destination(root, history)
        for event in review_history(history):
            if (event["cohort_fingerprint"] != cohort["fingerprint"]
                    or event["protocol_fingerprint"] != protocol["fingerprint"]):
                raise ValueError("stale review history")
            for decision in event["decisions"]:
                submitted[decision["review_row_id"]] = decision
    rows = [{**p, "proposal_fingerprint": digest(p), "payload": byrow[p["review_row_id"]]["payload"]}
            for p in proposals]
    value = envelope("supervisor-review-export-v2", {
        "cohort_fingerprint": cohort["fingerprint"], "protocol_fingerprint": protocol["fingerprint"],
        "proposals": rows, "validation_status": "SUBMITTED_UNVERIFIED",
        "submitted_decisions": list(submitted.values())})
    extras = {"review.csv": csv_text(rows)} if rows else {}
    if submitted:
        extras["submitted-decisions.csv"] = csv_text(list(submitted.values()))
    write_bundle(output, value, extras)
    typer.echo(str(output))


@app.command("review")
def review_command(approval: Path, decisions: Path, checkpoint: Path, history: Path,
                   bundle: Path = DEFAULT_OUTPUT, source_root: Path | None = None) -> None:
    """Save submitted, unverified decisions; strings cannot grant approval."""
    root = discover_project_root()
    checkpoint = derivative_destination(root, checkpoint)
    history = derivative_destination(root, history)
    cohort, crosswalks, protocol, _ = context(source_root or root, root / bundle)
    proposals = load_proposals(checkpoint, cohort, protocol)
    if decisions.suffix.lower() == ".csv":
        fields = ("review_row_id", "occurrence_id", "payload_sha256", "proposal_fingerprint",
                  "review_status", "human_final_label", "human_correction_note",
                  "human_reviewer_reference", "human_approval_provenance")
        value = [{key: (row[key] or None) if key == "human_final_label" else row[key]
                  for key in fields} for row in csv_rows(decisions)]
    else:
        value = read_json(decisions)
    path = record_review(source_root or root, cohort, crosswalks, protocol, read_json(approval),
                         proposals, value, history)
    typer.echo(str(path))


@app.command("analyze")
def analyze_command(approval: Path, checkpoint: Path, history: Path, output: Path,
                    bundle: Path = DEFAULT_OUTPUT, source_root: Path | None = None,
                    supervisor_attestation: Path | None = None,
                    trust_config: Path | None = None) -> None:
    """Refuse official evaluation until all human final labels are approved."""
    root = discover_project_root()
    checkpoint = derivative_destination(root, checkpoint)
    history = derivative_destination(root, history)
    output = derivative_destination(root, output)
    cohort, crosswalks, protocol, _ = context(source_root or root, root / bundle)
    result = analyze(source_root or root, cohort, crosswalks, protocol, read_json(approval),
                     load_proposals(checkpoint, cohort, protocol), history,
                     supervisor_attestation=read_attestation(supervisor_attestation),
                     trust_config=trust_config)
    write_bundle(output, result, {"approved-comparisons.csv": csv_text(result["rows"])})
    typer.echo(str(output))


def read_attestation(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    if path.is_dir():
        value = read_bundle(path)
        verify_envelope(value, "authenticated-supervisor-review-v1")
        return value["attestation"]  # Caller must reverify against current external trust.
    return read_approval_json(path)


@app.command("approval-export")
def approval_export_command(approval: Path, checkpoint: Path, history: Path,
                            reviewer: str, output: Path, bundle: Path = DEFAULT_OUTPUT,
                            source_root: Path | None = None) -> None:
    """Export a complete unsigned ledger for the supervisor's separate signing context."""
    root = discover_project_root()
    checkpoint = derivative_destination(root, checkpoint)
    history = derivative_destination(root, history)
    output = derivative_destination(root, output)
    cohort, crosswalks, protocol, _ = context(source_root or root, root / bundle)
    ledger = build_approval_ledger(source_root or root, cohort, crosswalks, protocol,
                                    read_json(approval), load_proposals(checkpoint, cohort, protocol),
                                    history, reviewer)
    write_bundle(output, envelope("unsigned-supervisor-approval-v1", {
        "validation_status": "UNSIGNED_UNVERIFIED", "ledger": ledger}),
        {"ledger.json": json.dumps(ledger, sort_keys=True, separators=(",", ":")) + "\n"})
    typer.echo(str(output))


@app.command("approval-import")
def approval_import_command(approval: Path, checkpoint: Path, history: Path,
                            attestation: Path, trust_config: Path, output: Path,
                            bundle: Path = DEFAULT_OUTPUT,
                            source_root: Path | None = None) -> None:
    """Authenticate a signed ledger with an externally provisioned supervisor key."""
    root = discover_project_root()
    checkpoint = derivative_destination(root, checkpoint)
    history = derivative_destination(root, history)
    output = derivative_destination(root, output)
    cohort, crosswalks, protocol, _ = context(source_root or root, root / bundle)
    path = import_supervisor_approval(
        source_root or root, cohort, crosswalks, protocol, read_json(approval),
        load_proposals(checkpoint, cohort, protocol), history, read_attestation(attestation),
        trust_config, output)
    typer.echo(str(path))
