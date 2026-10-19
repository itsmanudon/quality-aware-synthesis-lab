import json
from pathlib import Path
from typing import Annotated

import typer

from rcqasyn.config import discover_project_root
from rcqasyn.phase2.common import read_bundle

from .workflow import audit, load_context, run_study

app = typer.Typer(help="Provisional TRAIN-only coverage-aware dataset construction and audit.")


@app.command("study")
def study_command(output: Path, source_root: Annotated[Path, typer.Option()],
                  plan: Path = Path("configs/phase5/m7-study-v1.json")) -> None:
    root = discover_project_root()
    namespace = (root/"artifacts/reports/phase5").resolve(); target = (root/output).resolve()
    if target == namespace or not target.is_relative_to(namespace):
        raise ValueError("output must be a new version under artifacts/reports/phase5")
    result = run_study(root, source_root, target, json.loads((root/plan).read_text()))
    typer.echo(f"{result['total_constructed_datasets']} exploratory datasets; all audits {result['audit_status_counts']}")


@app.command("audit")
def audit_command(bundle: Path, source_root: Annotated[Path, typer.Option()]) -> None:
    root = discover_project_root(); ctx = load_context(root,source_root)
    value = read_bundle(bundle)
    typer.echo(json.dumps(audit(ctx,value),sort_keys=True))
