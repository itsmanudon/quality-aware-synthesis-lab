import json
from pathlib import Path
from typing import Annotated

import typer

from rcqasyn.config import discover_project_root

from .study import run_core
from .utility import run_utility

app = typer.Typer(help="Bounded repair, frozen reevaluation and predeclared descriptive utility.")


def destination(root: Path, output: Path) -> Path:
    namespace = (root / "artifacts/reports/phase6").resolve()
    target = (root / output).resolve()
    if target == namespace or not target.is_relative_to(namespace):
        raise ValueError("Phase-6 output must be a fresh version under artifacts/reports/phase6")
    return target


@app.command("core")
def core_command(
    output: Path,
    source_root: Annotated[Path, typer.Option()],
    plan: Path = Path("configs/phase6/m6-m9-study-v1.json"),
) -> None:
    root = discover_project_root()
    result = run_core(
        root, source_root, destination(root, output), json.loads((root / plan).read_text())
    )
    typer.echo(
        f"{result['construction_count']} original/repair M7 constructions; bounded repair audit complete"
    )


@app.command("utility")
def utility_command(
    core: Path,
    output: Path,
    source_root: Annotated[Path, typer.Option()],
    plan: Path = Path("configs/phase6/m6-m9-study-v1.json"),
) -> None:
    root = discover_project_root()
    result = run_utility(
        root,
        source_root,
        root / core,
        destination(root, output),
        json.loads((root / plan).read_text()),
    )
    typer.echo(
        f"{len(result['results'])} predeclared task-utility results: {result['status_counts']}"
    )


@app.command("audit")
def audit_command(core: Path, source_root: Annotated[Path, typer.Option()]) -> None:
    from .audit import audit_core

    root = discover_project_root()
    typer.echo(json.dumps(audit_core(root, source_root, root / core), sort_keys=True))
