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
    load_proposals,
    pending_batches,
    record_review,
    submit_batch,
)
from .common import csv_rows, csv_text, digest, envelope, write_bundle
from .workflow import DEFAULT_OUTPUT, load_preparation, prepare, validate_preparation

app = typer.Typer(help="Occurrence-bound Phase-2 preparation and approval-gated review.")


def context(root: Path, bundle: Path) -> tuple[Any, ...]:
    validate_preparation(root, bundle)
    return load_preparation(bundle)


@app.command("prepare")
def prepare_command(output: Path = DEFAULT_OUTPUT, dry_run: bool = False) -> None:
    """Reconstruct new derivatives; never generate annotation labels."""
    root = discover_project_root()
    result = prepare(root, root / output, dry_run=dry_run)
    typer.echo(json.dumps(result, indent=2))


@app.command("validate")
def validate_command(bundle: Path = DEFAULT_OUTPUT) -> None:
    """Independently rebuild bindings, order, schemas and historical integrity."""
    root = discover_project_root()
    typer.echo(json.dumps(validate_preparation(root, root / bundle), indent=2))


@app.command("batches")
def batches_command(approval: Path, checkpoint: Path, output: Path,
                    bundle: Path = DEFAULT_OUTPUT, batch_size: int = 10) -> None:
    """After Gate A, export stable pending blinded requests. No model is called."""
    root = discover_project_root()
    cohort, crosswalks, protocol, _ = context(root, root / bundle)
    gate_a(root, cohort, crosswalks, protocol, read_json(approval))
    batches = pending_batches(cohort, protocol, checkpoint, batch_size)
    value = envelope("annotation-batch-requests-v1", {
        "cohort_fingerprint": cohort["fingerprint"],
        "protocol_fingerprint": protocol["fingerprint"], "batches": batches,
        "validation_status": "REQUESTS_ONLY_NO_LABELS"})
    write_bundle(output, value)
    typer.echo(str(output))


@app.command("submit")
def submit_command(approval: Path, answers: Path, model: str, execution: str,
                   checkpoint: Path, bundle: Path = DEFAULT_OUTPUT) -> None:
    """Validate agent answers after Gate A; keep immutable proposal batches."""
    root = discover_project_root()
    cohort, crosswalks, protocol, _ = context(root, root / bundle)
    path = submit_batch(root, cohort, crosswalks, protocol, read_json(approval),
                        read_json(answers), model, execution, checkpoint)
    typer.echo(str(path))


@app.command("review-export")
def review_export_command(checkpoint: Path, output: Path,
                          bundle: Path = DEFAULT_OUTPUT) -> None:
    """Export proposals for supervision; an export conveys no approval."""
    root = discover_project_root()
    cohort, _, protocol, _ = context(root, root / bundle)
    proposals = load_proposals(checkpoint, cohort, protocol)
    byrow = {r["review_row_id"]: r for r in cohort["records"]}
    rows = [{**p, "proposal_fingerprint": digest(p), "payload": byrow[p["review_row_id"]]["payload"]}
            for p in proposals]
    value = envelope("supervisor-review-export-v1", {
        "cohort_fingerprint": cohort["fingerprint"], "protocol_fingerprint": protocol["fingerprint"],
        "proposals": rows, "validation_status": "PENDING_HUMAN_APPROVAL"})
    extras = {"review.csv": csv_text(rows)} if rows else {}
    write_bundle(output, value, extras)
    typer.echo(str(output))


@app.command("review")
def review_command(approval: Path, decisions: Path, checkpoint: Path, history: Path,
                   bundle: Path = DEFAULT_OUTPUT) -> None:
    """Append explicitly supplied human decisions; never infer reviewer identity."""
    root = discover_project_root()
    cohort, crosswalks, protocol, _ = context(root, root / bundle)
    proposals = load_proposals(checkpoint, cohort, protocol)
    if decisions.suffix.lower() == ".csv":
        fields = ("review_row_id", "occurrence_id", "payload_sha256", "proposal_fingerprint",
                  "review_status", "human_final_label", "human_correction_note",
                  "human_reviewer_reference", "human_approval_provenance")
        value = [{key: (row[key] or None) if key == "human_final_label" else row[key]
                  for key in fields} for row in csv_rows(decisions)]
    else:
        value = read_json(decisions)
    path = record_review(root, cohort, crosswalks, protocol, read_json(approval),
                         proposals, value, history)
    typer.echo(str(path))


@app.command("analyze")
def analyze_command(approval: Path, checkpoint: Path, history: Path, output: Path,
                    bundle: Path = DEFAULT_OUTPUT) -> None:
    """Refuse official evaluation until all human final labels are approved."""
    root = discover_project_root()
    cohort, crosswalks, protocol, _ = context(root, root / bundle)
    result = analyze(root, cohort, crosswalks, protocol, read_json(approval),
                     load_proposals(checkpoint, cohort, protocol), history)
    write_bundle(output, result, {"approved-comparisons.csv": csv_text(result["rows"])})
    typer.echo(str(output))
