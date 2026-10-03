from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

import typer
from pydantic import BaseModel

from rcqasyn.config import discover_project_root, load_config
from rcqasyn.config.experiment import load_experiment_config
from rcqasyn.datasets import (
    DatasetRegistry,
    assert_no_test_leakage,
    build_dataset_report,
    build_profile,
    inspect_dataset_schema,
    load_dataset,
    make_split,
    reconcile_schema,
    record_acquisition,
    write_acquisition,
)
from rcqasyn.experiments import (
    HumanAuditError,
    analyze_review,
    cross_dataset_comparison,
    export_blinded_reviews,
    import_blinded_review,
    review_status,
    run_experiment,
)
from rcqasyn.literature import build_inventory
from rcqasyn.metrics import utility_metrics
from rcqasyn.storage.artifacts import read_json, write_json

app = typer.Typer(help="RC-QASyn research foundation CLI.")
papers_app = typer.Typer(help="Inspect the local literature corpus.")
app.add_typer(papers_app, name="papers")
datasets_app = typer.Typer(help="Inspect and prepare registered local datasets.")
baselines_app = typer.Typer(help="Run paired baseline experiments.")
human_review_app = typer.Typer(help="Validate and analyze external human annotations.")
app.add_typer(datasets_app, name="datasets")
app.add_typer(baselines_app, name="baselines")
app.add_typer(human_review_app, name="human-review")


def _display_counts(values: dict[str, int]) -> str:
    return ", ".join(f"{name}={count}" for name, count in values.items()) or "none"


@human_review_app.command("status")
def human_review_status(review_csv: Path) -> None:
    """Report external annotation completeness without inferring labels."""

    try:
        status = review_status(review_csv.expanduser().resolve())
    except HumanAuditError as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(code=1) from error
    for key in ("rows", "labelled", "unlabelled", "valid", "invalid"):
        typer.echo(f"{key}: {status[key]}")
    typer.echo(f"taxonomy: {_display_counts(status['taxonomy_counts'])}")
    typer.echo(f"datasets: {_display_counts(status['dataset_counts'])}")
    typer.echo(f"classes: {_display_counts(status['class_counts'])}")
    typer.echo(f"roles: {_display_counts(status['role_counts'])}")
    typer.echo(f"b2: {_display_counts(status['b2_counts'])}")
    typer.echo(f"b3: {_display_counts(status['b3_counts'])}")
    typer.echo(f"human_fields_blank: {str(status['human_fields_blank']).lower()}")
    for field, counts in status["copying_flag_counts"].items():
        typer.echo(f"{field}: {_display_counts(counts)}")
    for field, count in status["support_distance_coverage"].items():
        typer.echo(f"{field}: {count}/{status['rows']}")
    for field, count in status["provider_lineage_coverage"].items():
        typer.echo(f"{field}: {count}/{status['rows']}")
    typer.echo(f"analysis_ready: {str(status['analysis_ready']).lower()}")
    if status["unknown_taxonomy_labels"]:
        typer.echo(f"unknown_taxonomy: {_display_counts(status['unknown_taxonomy_labels'])}")


def _annotator_paths(values: list[str], project_root: Path) -> dict[str, Path]:
    parsed: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise HumanAuditError("--annotator must use ID=PATH syntax")
        annotator_id, raw_path = value.split("=", 1)
        annotator_id = annotator_id.strip()
        raw_path = raw_path.strip()
        if not annotator_id or not raw_path:
            raise HumanAuditError("--annotator must use non-blank ID=PATH syntax")
        if annotator_id in parsed or annotator_id == "primary":
            raise HumanAuditError(f"duplicate or reserved annotator ID: {annotator_id}")
        path = Path(raw_path).expanduser()
        parsed[annotator_id] = (
            path.resolve() if path.is_absolute() else (project_root / path).resolve()
        )
    return parsed


@human_review_app.command("analyze")
def human_review_analyze(
    review_csv: Path,
    root: Path | None = typer.Option(None, "--root", help="Project root."),  # noqa: B008
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Report directory."),  # noqa: B008
    annotator: list[str] | None = typer.Option(  # noqa: B008
        None, "--annotator", help="Optional ID=PATH annotation file."
    ),
    adjudicated: Path | None = typer.Option(  # noqa: B008
        None, "--adjudicated", help="Explicit adjudicated annotation file."
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Retained for compatibility; historical outputs cannot be replaced."
    ),
) -> None:
    """Generate M1.6 reports from complete external human annotations."""

    project_root = _root_option(root)
    source = review_csv.expanduser()
    source = source.resolve() if source.is_absolute() else (project_root / source).resolve()
    destination = output_dir or project_root / "artifacts" / "reports" / "human_audit"
    destination = (
        destination.resolve()
        if destination.is_absolute()
        else (project_root / destination).resolve()
    )
    adjudicated_path = None
    if adjudicated is not None:
        adjudicated_path = adjudicated.expanduser()
        adjudicated_path = (
            adjudicated_path.resolve()
            if adjudicated_path.is_absolute()
            else (project_root / adjudicated_path).resolve()
        )
    try:
        annotator_files = _annotator_paths(annotator or [], project_root)
        result = analyze_review(
            source,
            project_root=project_root,
            output_dir=destination,
            annotators=annotator_files,
            adjudicated=adjudicated_path,
            overwrite=overwrite,
        )
    except HumanAuditError as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(code=1) from error
    typer.echo(f"human audit complete: {result['human_summary']['labelled']} labelled rows")
    typer.echo(f"reports: {destination}")


@human_review_app.command("export-blind")
def human_review_export_blind(
    master_csv: Path,
    root: Path | None = typer.Option(None, "--root", help="Project root."),  # noqa: B008
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Blinded export directory."),  # noqa: B008
    overlap: int = typer.Option(40, "--overlap", help="Reviewer B overlap size."),
    seed: int = typer.Option(42, "--seed", help="Deterministic selection seed."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Retained for compatibility; existing outputs are immutable."),
) -> None:
    """Create reviewer A/all and reviewer B/overlap exports without diagnostics."""

    project_root = _root_option(root)
    master = master_csv.expanduser()
    master = master.resolve() if master.is_absolute() else (project_root / master).resolve()
    destination = output_dir or project_root / "artifacts" / "reports" / "human_audit" / "blinded"
    destination = (
        destination.resolve()
        if destination.is_absolute()
        else (project_root / destination).resolve()
    )
    try:
        master_status = review_status(master)
        outputs = export_blinded_reviews(
            master,
            destination,
            overlap=overlap,
            seed=seed,
            overwrite=overwrite,
        )
    except HumanAuditError as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(code=1) from error
    typer.echo(f"{outputs['reviewer_a'].name}: {master_status['rows']} rows")
    typer.echo(f"{outputs['reviewer_b'].name}: {overlap} rows")
    typer.echo(
        f"manifests: {outputs['reviewer_a_manifest'].name}, {outputs['reviewer_b_manifest'].name}"
    )


@human_review_app.command("import-blind")
def human_review_import_blind(
    master_csv: Path,
    reviewer_csv: Path,
    manifest: Path = typer.Option(..., "--manifest", help="Matching internal manifest."),  # noqa: B008
    annotator_id: str = typer.Option(..., "--annotator-id", help="Reviewer identifier."),
    output: Path = typer.Option(..., "--output", help="New master-format annotation CSV."),  # noqa: B008
    root: Path | None = typer.Option(None, "--root", help="Project root."),  # noqa: B008
    overwrite: bool = typer.Option(False, "--overwrite", help="Retained for compatibility; existing outputs are immutable."),
) -> None:
    """Validate and attach blinded labels to a new copy of the master review."""

    project_root = _root_option(root)

    def resolve(path: Path) -> Path:
        expanded = path.expanduser()
        return expanded.resolve() if expanded.is_absolute() else (project_root / expanded).resolve()

    try:
        imported = import_blinded_review(
            resolve(master_csv),
            resolve(reviewer_csv),
            resolve(manifest),
            resolve(output),
            annotator_id=annotator_id,
            overwrite=overwrite,
        )
        status = review_status(imported)
    except HumanAuditError as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(code=1) from error
    typer.echo(f"imported: {imported}")
    typer.echo(f"labelled: {status['labelled']}")
    typer.echo(f"unlabelled: {status['unlabelled']}")


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
            paper_count = sum(
                1
                for item in papers_dir.iterdir()
                if item.is_file() and item.suffix.lower() == ".pdf"
            )
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
        print(
            f"{spec.dataset_id}\t{spec.display_name}\t{'present' if path.is_file() else 'missing'}\t{path}"
        )


@datasets_app.command("inspect")
def datasets_inspect(
    dataset_id: str,
    root: Path | None = typer.Option(None, "--root", help="Project root."),  # noqa: B008
) -> None:
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
        print(
            f"Placement: copy the verified local source to {path} (accepted: {', '.join(spec.accepted_filenames)})"
        )
        return
    dataset = load_dataset(spec, registry)
    split = make_split(dataset, 42)
    if spec.format.lower() in {"keel_dat", "dat"}:
        try:
            raw_report = inspect_dataset_schema(path, spec)
            print(f"Relation: {raw_report['relation'] or '<undeclared>'}")
            print(
                f"Raw declarations: attributes={len(raw_report['attributes'])}, inputs={len(raw_report['inputs'])}, outputs={len(raw_report['outputs'])}"
            )
            print(
                f"Raw missing: representation={raw_report['missing_representation']}; cells={raw_report['missing_count']}"
            )
            reconcile_schema(path, spec)
            print("Schema reconciliation: OK")
        except ValueError as error:
            print(f"Schema reconciliation: ERROR ({error})")
    print(f"Fingerprint: {dataset.fingerprint}")
    print(f"Rows: {len(dataset.frame)}; missing cells: {dataset.missing_count}")
    print(
        f"Classes: {dataset.frame[spec.target_column].astype(str).value_counts().sort_index().to_dict()}"
    )
    print(f"Split indices: train={len(split.train_indices)}, test={len(split.test_indices)}")


@datasets_app.command("prepare")
def datasets_prepare(
    dataset_id: str,
    root: Path | None = typer.Option(None, "--root", help="Project root."),  # noqa: B008
    seed: int = typer.Option(42, "--seed"),
) -> None:
    """Prepare deterministic dataset, split, and TRAIN-only profile manifests."""
    project_root = _root_option(root)
    registry = DatasetRegistry(project_root=project_root)
    try:
        spec = registry.get(dataset_id)
        dataset = load_dataset(spec, registry)
        raw_schema = None
        if spec.format.lower() in {"keel_dat", "dat"}:
            raw_schema = inspect_dataset_schema(dataset.path, spec)
            reconcile_schema(dataset.path, spec)
        split = make_split(dataset, seed)
        profile = build_profile(dataset, split, seed=seed)
        assert_no_test_leakage(dataset, split, profile)
        acquisition_path = project_root / "data" / "manifests" / dataset_id / "source.json"
        legacy_acquisition_path = (
            project_root / "data" / "manifests" / dataset_id / "acquisition.json"
        )
        acquisition = None
        if acquisition_path.is_file():
            import json

            acquisition = json.loads(acquisition_path.read_text(encoding="utf-8"))
        elif legacy_acquisition_path.is_file():
            import json

            acquisition = json.loads(legacy_acquisition_path.read_text(encoding="utf-8"))
        destination = project_root / "data" / "manifests" / dataset_id
        destination.mkdir(parents=True, exist_ok=True)
        _write_reusable_manifest(
            destination / "dataset_manifest.json",
            {
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
                "class_counts": dataset.frame[spec.target_column]
                .astype(str)
                .value_counts()
                .sort_index()
                .to_dict(),
                "source_url": spec.source_url,
                "source_page": spec.source_page,
                "preprocessing": list(spec.preprocessing),
                "spec_metadata": spec.metadata,
            },
        )
        _write_reusable_manifest(destination / "split_manifest.json", split.to_dict())
        _write_reusable_manifest(destination / "profile.json", profile.model_dump(mode="json"))
        if raw_schema is not None:
            _write_reusable_manifest(destination / "raw_schema.json", raw_schema)
        report = build_dataset_report(dataset, split)
        if acquisition:
            report["acquisition"] = acquisition
            report["archive_sha256"] = acquisition.get("sha256")
            report["extracted_dataset_sha256"] = acquisition.get("extracted_sha256")
        _write_reusable_manifest(destination / "dataset_report.json", report)
        _write_reusable_manifest(
            destination / "leakage_assertions.json",
            {
                "train_test_disjoint": True,
                "train_test_cover_all_rows": True,
                "profile_train_only": True,
                "reference_train_only": True,
            },
        )
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


@datasets_app.command("record-acquisition")
def datasets_record_acquisition(
    dataset_id: str,
    root: Path | None = typer.Option(None, "--root", help="Project root."),  # noqa: B008
    source_url: str | None = typer.Option(
        None, "--source-url", help="Exact authoritative source URL."
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Retained for compatibility; acquisition history is immutable."
    ),
) -> None:
    """Record size, SHA-256, and UTC acquisition time for an already acquired raw file."""

    project_root = _root_option(root)
    registry = DatasetRegistry(project_root=project_root)
    try:
        spec = registry.get(dataset_id)
        raw_path = registry.resolve_path(spec)
        record = record_acquisition(spec, raw_path, source_url=source_url)
        destination = project_root / "data" / "manifests" / dataset_id / "source.json"
        write_acquisition(destination, record, overwrite=overwrite)
    except (OSError, ValueError, KeyError) as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(code=1) from error
    print(f"Recorded acquisition for {dataset_id}: {destination}")


@baselines_app.command("trtr")
def baselines_trtr(
    dataset_id: str,
    root: Path | None = typer.Option(None, "--root", help="Project root."),  # noqa: B008
    seed: int = typer.Option(42, "--seed"),
    output: Path | None = typer.Option(None, "--output", help="JSON report path."),  # noqa: B008
) -> None:
    """Run the real-train/real-test pilot for both configured classifiers."""

    project_root = _root_option(root)
    registry = DatasetRegistry(project_root=project_root)
    try:
        spec = registry.get(dataset_id)
        dataset = load_dataset(spec, registry)
        split = make_split(dataset, seed)
        profile = build_profile(dataset, split, seed=seed)
        assert_no_test_leakage(dataset, split, profile)
        train = dataset.frame.loc[list(split.train_indices)]
        test = dataset.frame.loc[list(split.test_indices)]
        result = utility_metrics(train, test, train.copy(), spec, seed=seed)["TRTR"]
        report = build_dataset_report(dataset, split)
        report.update({"seed": seed, "TRTR": result})
        destination = (
            output or project_root / "artifacts" / "reports" / f"trtr-{dataset_id}-{seed}.json"
        )
        if not destination.is_absolute():
            destination = project_root / destination
        _write_reusable_manifest(destination, report)
    except (OSError, ValueError, KeyError) as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(code=1) from error
    print(f"TRTR report: {destination}")
    for classifier, metrics in result.items():
        print(f"{classifier}: {metrics}")


@baselines_app.command("compare")
def baselines_compare(
    run_dirs: list[Path] = typer.Argument(..., help="Completed run directories to compare."),  # noqa: B008
    root: Path | None = typer.Option(None, "--root", help="Project root."),  # noqa: B008
    output: Path | None = typer.Option(None, "--output", help="JSON report path."),  # noqa: B008
) -> None:
    """Write a machine-only cross-dataset comparison for completed runs."""

    project_root = _root_option(root)
    try:
        comparisons = []
        for run_dir in run_dirs:
            path = run_dir if run_dir.is_absolute() else project_root / run_dir

            from rcqasyn.experiments.readers import read_bundle
            value = read_bundle(path)
            if not isinstance(value, dict):
                raise TypeError(f"comparison must be a JSON object: {path / 'comparison.json'}")
            comparisons.append(value)
        report = cross_dataset_comparison(comparisons)
        destination = (
            output or project_root / "artifacts" / "reports" / "cross-dataset-comparison.json"
        )
        if not destination.is_absolute():
            destination = project_root / destination
        _write_reusable_manifest(destination, report)
    except (OSError, TypeError, ValueError) as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(code=1) from error
    print(f"Cross-dataset report: {destination}")


@baselines_app.command("diagnose")
def baselines_diagnose(
    run_dirs: list[Path] = typer.Argument(..., help="Completed run directories to diagnose."),  # noqa: B008
    root: Path | None = typer.Option(None, "--root", help="Project root."),  # noqa: B008
) -> None:
    """Write diagnostic-only copying and TRAIN-support artifacts for completed runs.

    Does not read, change, or re-run any B1/B2/B3 acceptance decision.
    """

    from rcqasyn.experiments import copying_diagnostics, support_diagnostics

    project_root = _root_option(root)
    for run_dir in run_dirs:
        path = run_dir if run_dir.is_absolute() else project_root / run_dir
        try:
            cp = copying_diagnostics(path, project_root)
            sp = support_diagnostics(path, project_root)
        except (OSError, KeyError, ValueError) as error:
            typer.echo(f"error: {run_dir}: {error}", err=True)
            raise typer.Exit(code=1) from error
        overall = cp["overall"]
        near = sp["overall"]["nearest_train_distance"]
        print(
            f"{path.name}: unique={overall['unique_records']}/{overall['records']} "
            f"synth_dup={overall['exact_synthetic_duplicate']} "
            f"ref_match={overall['exact_reference_match']} "
            f"nonref_train_match={overall['exact_nonreference_train_match']} "
            f"nearest_train_dist(min/median/max)="
            f"{near.get('min')}/{near.get('median')}/{near.get('max')}"
        )


@baselines_app.command("run")
def baselines_run(
    config: Path = typer.Option(..., "--config", help="Experiment YAML config."),  # noqa: B008
    root: Path | None = typer.Option(None, "--root", help="Project root."),  # noqa: B008
) -> None:
    """Run a configured generation and paired B1/B2/B3 experiment."""
    _run_baseline(config, root, replay=False)


@baselines_app.command("replay")
def baselines_replay(
    config: Path = typer.Option(..., "--config", help="Offline replay YAML config."),  # noqa: B008
    root: Path | None = typer.Option(None, "--root", help="Project root."),  # noqa: B008
) -> None:
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
        print(
            f"{name}: accepted={summary.get('accepted')}/{summary.get('requested')} rate={summary.get('acceptance_rate')}"
        )


def _git_status(root: Path) -> tuple[bool, str | None, bool]:
    try:
        detected = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
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
