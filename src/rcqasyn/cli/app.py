from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

import typer

from rcqasyn.config import discover_project_root, load_config
from rcqasyn.literature import build_inventory

app = typer.Typer(help="RC-QASyn research foundation CLI.")
papers_app = typer.Typer(help="Inspect the local literature corpus.")
app.add_typer(papers_app, name="papers")


def _root_option(root: Path | None) -> Path:
    return root.expanduser().resolve() if root else discover_project_root()


@app.command()
def doctor(
    root: Path | None = typer.Option(None, "--root", help="Project root."),  # noqa: B008
    config: Path | None = typer.Option(None, "--config", help="YAML config path."),  # noqa: B008
) -> None:
    """Report required foundation state without exposing environment secrets."""
    project_root = _root_option(root)
    print(f"Python: {sys.version.split()[0]} ({platform.platform()})")
    print(f"Root: {project_root}")
    errors: list[str] = []
    try:
        resolved = load_config(config, project_root)
        print(f"Config: OK ({resolved.config_path})")
    except (OSError, ValueError) as error:
        print(f"Config: ERROR ({error})")
        errors.append("config")
        resolved = None
    if resolved:
        papers_dir = resolved.literature.papers_dir
        paper_count = len(list(papers_dir.glob("*"))) if papers_dir.is_dir() else 0
        if papers_dir.is_dir():
            paper_count = sum(1 for item in papers_dir.iterdir() if item.is_file() and item.suffix.lower() == ".pdf")
            print(f"Papers: OK ({papers_dir}, count={paper_count})")
        else:
            print(f"Papers: ERROR (missing {papers_dir})")
            errors.append("papers")
        artifacts_dir = resolved.artifacts.root
        print(f"Artifacts: {'OK' if artifacts_dir.is_dir() else 'MISSING'} ({artifacts_dir})")
    git = _git_status(project_root)
    print(f"Git: {'detected' if git[0] else 'not detected'}")
    if git[0]:
        print(f"Git commit: {git[1] or 'unknown'}")
        print(f"Git dirty: {'yes' if git[2] else 'no'}")
    if errors:
        raise typer.Exit(code=1)


@papers_app.command("index")
def papers_index(
    root: Path | None = typer.Option(None, "--root", help="Project root."),  # noqa: B008
    config: Path | None = typer.Option(None, "--config", help="YAML config path."),  # noqa: B008
    output: Path | None = typer.Option(None, "--output", help="Inventory CSV path."),  # noqa: B008
) -> None:
    """Create a deterministic CSV inventory of local PDFs."""
    project_root = _root_option(root)
    try:
        resolved = load_config(config, project_root)
    except (OSError, ValueError) as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(code=1) from error
    papers_dir = resolved.literature.papers_dir
    inventory_path = output or project_root / "literature" / "paper_inventory.csv"
    if not inventory_path.is_absolute():
        inventory_path = project_root / inventory_path
    entries = build_inventory(papers_dir, inventory_path, project_root)
    print(f"Indexed {len(entries)} PDF(s) to {inventory_path.resolve()}")


def _git_status(root: Path) -> tuple[bool, str | None, bool]:
    try:
        detected = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"], cwd=root, capture_output=True, text=True, check=False
        )
        if detected.returncode != 0:
            return False, None, False
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=False
        )
        return True, commit.stdout.strip() or None, bool(dirty.stdout.strip())
    except OSError:
        return False, None, False


if __name__ == "__main__":
    app()
