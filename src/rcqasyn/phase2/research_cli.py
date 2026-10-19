"""Explicit academic research commands; production authorization stays disabled."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import typer

from rcqasyn.config import discover_project_root
from rcqasyn.storage.artifacts import read_json

from .analysis import analyze_research, research_report
from .annotations import pending_batches
from .common import csv_text, envelope, read_bundle, write_bundle
from .research import (
    RESEARCH,
    bindings,
    checkpoint_text,
    export_research_review,
    import_research_review,
    load_research_proposals,
    read_review_rows,
    scope_checkpoint,
    submit_research_batch,
    validate_scope,
)
from .workflow import DEFAULT_OUTPUT, derivative_destination, load_preparation, validate_preparation

app = typer.Typer(help="Supervisor-reviewed research ledger; no cryptographic authentication.")


def _context(root: Path, source: Path | None, bundle: Path) -> tuple[Any, ...]:
    validate_preparation(source or root, root / bundle)
    return load_preparation(root / bundle)


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"


@app.command("checkpoint")
def checkpoint_command(output: Path, bundle: Path = DEFAULT_OUTPUT,
                       source_root: Path | None = None) -> None:
    """Present frozen cohort and exact rubric; generate no labels or approvals."""
    root = discover_project_root()
    output = derivative_destination(root, output)
    cohort, crosswalks, protocol, specs = _context(root, source_root, bundle)
    value = scope_checkpoint(cohort, crosswalks, protocol, specs)
    template = {"schema_version": "research-scope-approval-v1", "purpose": "COHORT_AND_RUBRIC_ONLY",
                "decision": "PENDING_SUPERVISOR_APPROVAL", **bindings(cohort, protocol),
                "supervisor_reference": "", "implementation_owner_reference": "",
                "approval_provenance": "", "scientific_decisions": ""}
    write_bundle(output, value, {"checkpoint.md": checkpoint_text(value),
                                 "rubric.json": _json(value["rubric"]),
                                 "scope-approval.template.json": _json(template)})
    typer.echo(str(output))


@app.command("batches")
def batches_command(scope_approval: Path, checkpoint: Path, output: Path,
                    bundle: Path = DEFAULT_OUTPUT, batch_size: int = 10,
                    source_root: Path | None = None) -> None:
    """After explicit cohort/rubric approval, export pending blinded requests."""
    root = discover_project_root()
    checkpoint = derivative_destination(root, checkpoint)
    output = derivative_destination(root, output)
    cohort, crosswalks, protocol, _ = _context(root, source_root, bundle)
    scope = validate_scope(source_root or root, cohort, crosswalks, protocol, read_json(scope_approval))
    load_research_proposals(checkpoint, cohort, protocol, scope)
    requests = pending_batches(cohort, protocol, checkpoint, batch_size)
    value = envelope("research-annotation-requests-v1", {
        **RESEARCH, **bindings(cohort, protocol), "scope_approval": scope,
        "batches": requests, "validation_status": "REQUESTS_ONLY_NO_LABELS"})
    write_bundle(output, value)
    typer.echo(str(output))


@app.command("submit")
def submit_command(scope_approval: Path, answers: Path, model: str, execution: str,
                   checkpoint: Path, bundle: Path = DEFAULT_OUTPUT,
                   source_root: Path | None = None) -> None:
    """Save evidence-backed agent proposals; never populate supervisor decisions."""
    root = discover_project_root()
    checkpoint = derivative_destination(root, checkpoint)
    cohort, crosswalks, protocol, _ = _context(root, source_root, bundle)
    path = submit_research_batch(source_root or root, cohort, crosswalks, protocol,
                                 read_json(scope_approval), read_json(answers), model, execution,
                                 checkpoint)
    typer.echo(str(path))


@app.command("review-export")
def export_command(scope_approval: Path, checkpoint: Path, output: Path,
                   bundle: Path = DEFAULT_OUTPUT, source_root: Path | None = None) -> None:
    """Export complete CSV/JSON sheets with blank human decision fields."""
    root = discover_project_root()
    checkpoint = derivative_destination(root, checkpoint)
    output = derivative_destination(root, output)
    cohort, crosswalks, protocol, _ = _context(root, source_root, bundle)
    scope = validate_scope(source_root or root, cohort, crosswalks, protocol, read_json(scope_approval))
    proposals = load_research_proposals(checkpoint, cohort, protocol, scope)
    value = export_research_review(source_root or root, cohort, crosswalks, protocol, scope, proposals)
    write_bundle(output, value, {"review.csv": csv_text(value["rows"]),
                                 "review.json": _json(value["rows"])})
    typer.echo(str(output))


@app.command("review-import")
def import_command(scope_approval: Path, checkpoint: Path, reviewed_rows: Path,
                   provenance: str, output: Path, previous_ledger: Path | None = None,
                   bundle: Path = DEFAULT_OUTPUT, source_root: Path | None = None) -> None:
    """Record complete personally reviewed rows; analysis still requires confirmation."""
    root = discover_project_root()
    checkpoint = derivative_destination(root, checkpoint)
    output = derivative_destination(root, output)
    cohort, crosswalks, protocol, _ = _context(root, source_root, bundle)
    scope = validate_scope(source_root or root, cohort, crosswalks, protocol, read_json(scope_approval))
    proposals = load_research_proposals(checkpoint, cohort, protocol, scope)
    value = import_research_review(source_root or root, cohort, crosswalks, protocol, scope,
                                   proposals, read_review_rows(reviewed_rows), provenance,
                                   read_bundle(previous_ledger) if previous_ledger else None)
    template = {"schema_version": "research-ledger-confirmation-v1",
                "decision": "PENDING_SUPERVISOR_CONFIRMATION",
                "reviewed_ledger_fingerprint": value["fingerprint"],
                "scope_approval_fingerprint": value["scope_approval_fingerprint"],
                "supervisor_reference": scope["supervisor_reference"],
                "confirmation_provenance": ""}
    write_bundle(output, value, {"reviewed.csv": csv_text(value["rows"]),
                                 "confirmation.template.json": _json(template)})
    typer.echo(f"{output}\nReviewed ledger fingerprint: {value['fingerprint']}")


@app.command("analyze")
def analyze_command(scope_approval: Path, checkpoint: Path, reviewed_ledger: Path,
                    confirmation: Path, output: Path, bundle: Path = DEFAULT_OUTPUT,
                    source_root: Path | None = None) -> None:
    """Only after exact supervisor confirmation, compute research B2/B3 results."""
    root = discover_project_root()
    checkpoint = derivative_destination(root, checkpoint)
    output = derivative_destination(root, output)
    cohort, crosswalks, protocol, _ = _context(root, source_root, bundle)
    scope = validate_scope(source_root or root, cohort, crosswalks, protocol, read_json(scope_approval))
    proposals = load_research_proposals(checkpoint, cohort, protocol, scope)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"],
                               cwd=root, text=True).strip():
        raise ValueError("commit implementation changes before reproducible research analysis")
    ledger, confirmed = read_bundle(reviewed_ledger), read_json(confirmation)
    result = analyze_research(source_root or root, cohort, crosswalks, protocol, scope,
                              proposals, ledger, confirmed, implementation_revision=revision)
    write_bundle(output, result, {"comparisons.csv": csv_text(result["rows"]),
                                  "report.md": research_report(result),
                                  "scope-approval.json": _json(scope),
                                  "proposals.json": _json(proposals),
                                  "reviewed-ledger.json": _json(ledger),
                                  "confirmation.json": _json(confirmed)})
    typer.echo(str(output))
