from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

import typer
from pydantic import BaseModel

from rcqasyn.config import discover_project_root, load_config
from rcqasyn.config.experiment import load_experiment_config
from rcqasyn.datasets import DatasetRegistry, build_profile, load_dataset, make_split
from rcqasyn.experiments import run_experiment
from rcqasyn.literature import build_inventory
from rcqasyn.storage.artifacts import read_json, write_json

app = typer.Typer(help="RC-QASyn research foundation CLI.")
papers_app = typer.Typer(help="Inspect the local literature corpus.")
app.add_typer(papers_app, name="papers")
datasets_app = typer.Typer(help="Inspect and prepare registered local datasets.")
baselines_app = typer.Typer(help="Run paired baseline experiments.")
app.add_typer(datasets_app, name="datasets")
app.add_typer(baselines_app, name="baselines")


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


@datasets_app.command("list")
def datasets_list(root: Path | None = typer.Option(None, "--root", help="Project root.")) -> None:  # noqa: B008
    """List registered datasets without reading or printing records."""
    registry = DatasetRegistry(project_root=_root_option(root))
    for spec in registry.list():
        path = registry.resolve_path(spec)
        print(f"{spec.dataset_id}\t{spec.display_name}\t{'present' if path.is_file() else 'missing'}\t{path}")


@datasets_app.command("inspect")
def datasets_inspect(dataset_id: str, root: Path | None = typer.Option(None, "--root", help="Project root.")) -> None:  # noqa: B008
    """Show registry, presence, fingerprint, schema, and split metadata without records."""
    project_root = _root_option(root)
    registry = DatasetRegistry(project_root=project_root)
    try:
        spec = registry.get(dataset_id)
    except KeyError as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(code=1) from error
    path = registry.resolve_path(spec)
    print(f"Dataset: {spec.dataset_id} ({spec.display_name})")
    print(f"Path: {path}")
    print(f"Presence: {'present' if path.is_file() else 'missing'}")
    print(f"Target: {spec.target_column}")
    print(f"Features: {len(spec.feature_columns)} ({', '.join(spec.feature_columns)})")
    print(f"Categorical: {', '.join(spec.categorical_columns) or 'none'}")
    print(f"Numerical: {', '.join(spec.numerical_columns) or 'none'}")
    print(f"Missing policy: {spec.missing_policy}")
    print(f"Split: test_size={spec.split.test_size}, stratify={spec.split.stratify}")
    if not path.is_file():
        print(f"Placement: copy the verified local source to {path} (accepted: {', '.join(spec.accepted_filenames)})")
        return
    dataset = load_dataset(spec, registry)
    split = make_split(dataset, 42)
    print(f"Fingerprint: {dataset.fingerprint}")
    print(f"Rows: {len(dataset.frame)}; missing cells: {dataset.missing_count}")
    print(f"Classes: {dataset.frame[spec.target_column].astype(str).value_counts().sort_index().to_dict()}")
    print(f"Split indices: train={len(split.train_indices)}, test={len(split.test_indices)}")


@datasets_app.command("prepare")
def datasets_prepare(dataset_id: str, root: Path | None = typer.Option(None, "--root", help="Project root."), seed: int = typer.Option(42, "--seed")) -> None:  # noqa: B008
    """Prepare deterministic dataset, split, and TRAIN-only profile manifests."""
    project_root = _root_option(root)
    registry = DatasetRegistry(project_root=project_root)
    try:
        spec = registry.get(dataset_id)
        dataset = load_dataset(spec, registry)
        split = make_split(dataset, seed)
        profile = build_profile(dataset, split, seed=seed)
        destination = project_root / "data" / "manifests" / dataset_id
        destination.mkdir(parents=True, exist_ok=True)
        _write_reusable_manifest(destination / "dataset_manifest.json", {
            "dataset_id": dataset_id,
            "display_name": spec.display_name,
            "path": str(dataset.path),
            "fingerprint": dataset.fingerprint,
            "rows": len(dataset.frame),
            "features": list(spec.feature_columns),
            "target": spec.target_column,
            "categorical_features": list(spec.categorical_columns),
            "numerical_features": list(spec.numerical_columns),
            "missing_policy": spec.missing_policy,
            "class_counts": dataset.frame[spec.target_column].astype(str).value_counts().sort_index().to_dict(),
            "source_url": spec.source_url,
            "source_page": spec.source_page,
            "preprocessing": list(spec.preprocessing),
            "spec_metadata": spec.metadata,
        })
        _write_reusable_manifest(destination / "split_manifest.json", split.to_dict())
        _write_reusable_manifest(destination / "profile.json", profile.model_dump(mode="json"))
    except (OSError, ValueError, KeyError) as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(code=1) from error
    print(f"Prepared {dataset_id} manifests under {destination}")


def _write_reusable_manifest(path: Path, value: object | BaseModel) -> None:
    if path.exists():
        expected = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
        if read_json(path) == expected:
            return
        raise FileExistsError(f"existing manifest is incompatible; refusing overwrite: {path}")
    write_json(path, value)


@baselines_app.command("run")
def baselines_run(config: Path = typer.Option(..., "--config", help="Experiment YAML config."), root: Path | None = typer.Option(None, "--root", help="Project root.")) -> None:  # noqa: B008
    """Run a configured generation and paired B1/B2/B3 experiment."""
    _run_baseline(config, root, replay=False)


@baselines_app.command("replay")
def baselines_replay(config: Path = typer.Option(..., "--config", help="Offline replay YAML config."), root: Path | None = typer.Option(None, "--root", help="Project root.")) -> None:  # noqa: B008
    """Run the same baseline architecture using deterministic stored responses."""
    _run_baseline(config, root, replay=True)


def _run_baseline(config: Path, root: Path | None, replay: bool) -> None:
    project_root = _root_option(root)
    try:
        experiment, _ = load_experiment_config(config, project_root)
        result = run_experiment(experiment, project_root=project_root, replay=replay)
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(code=1) from error
    print(f"Completed {result.run_id}")
    print(f"Artifacts: {result.artifact_dir}")
    for name, summary in result.comparison.get("baselines", {}).items():
        print(f"{name}: accepted={summary.get('accepted')}/{summary.get('requested')} rate={summary.get('acceptance_rate')}")


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
