import json
from pathlib import Path
from typing import Annotated

import typer

from rcqasyn.config import discover_project_root
from rcqasyn.phase2.workflow import DEFAULT_OUTPUT

from .workflow import read_shadow, run_shadow

app = typer.Typer(help="Uncalibrated descriptive evidence fusion and offline shadow policies.")


@app.command("shadow")
def shadow_command(output: Path, source_root: Annotated[Path, typer.Option()],
                   plan: Path = Path("configs/phase4/m4-m5-shadow-v1.json")) -> None:
    root = discover_project_root()
    namespace = (root/"artifacts/reports/phase4").resolve()
    target = (root/output).resolve()
    if target == namespace or not target.is_relative_to(namespace):
        raise ValueError("shadow output must be a version under artifacts/reports/phase4")
    design = json.loads((root/plan).read_text())
    result = run_shadow(source_root, root/DEFAULT_OUTPUT, root/design["m2_input"],
                        root/"artifacts/reports/phase3/review-v2", target, design, root)
    typer.echo(f"{target}: {len(result['decisions'])} exploratory decisions; calibration inactive")


@app.command("inspect")
def inspect_command(bundle: Path) -> None:
    root = discover_project_root()
    # Read the sealed contract first, then replay against its recorded M2 source.
    result = read_shadow(bundle)
    read_shadow(bundle, root/result["m2_input"])
    typer.echo(f"{result['scientific_status']}: {len(result['decisions'])} shadow decisions")
