from pathlib import Path

import typer

from rcqasyn.config import discover_project_root
from rcqasyn.phase2.workflow import DEFAULT_OUTPUT

from .contracts import M2Config
from .workflow import read_results, run_offline

app = typer.Typer(help="TRAIN-only heterogeneous evidence diagnostics; no admission policy.")


@app.command("score")
def score_command(output: Path, source_root: Path, k: int = 5, shrinkage: float = 0.1,
                  seed: int = 42, preparation: Path = DEFAULT_OUTPUT) -> None:
    root = discover_project_root()
    namespace = (root / "artifacts/reports/phase3").resolve()
    target = (root / output).resolve()
    if target == namespace or not target.is_relative_to(namespace):
        raise ValueError("M2 output must be a new version under artifacts/reports/phase3")
    result = run_offline(source_root, root / preparation, target,
                         M2Config(k=k, shrinkage=shrinkage, seed=seed), root)
    typer.echo(f"{target}: {len(result['evidence'])} evidence records")


@app.command("inspect")
def inspect_command(bundle: Path) -> None:
    result = read_results(bundle)
    typer.echo(f"{result['scientific_status']}: {len(result['candidate_bindings'])} occurrences")
