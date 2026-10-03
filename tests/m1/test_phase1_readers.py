import json
from pathlib import Path

import pytest

from rcqasyn.cli.app import _write_reusable_manifest
from rcqasyn.config import load_experiment_config
from rcqasyn.experiments import run_experiment
from rcqasyn.experiments.analysis import cross_dataset_comparison
from rcqasyn.experiments.diagnostics import copying_diagnostics
from rcqasyn.experiments.readers import read_bundle
from rcqasyn.storage.ownership import file_hash


def fixture_run(tmp_path):
    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    return run_experiment(
        config.model_copy(update={"artifact_root": tmp_path, "run_id": None}), replay=True
    )


def test_diagnostics_write_separately_and_leave_all_source_bytes_unchanged(tmp_path):
    run = fixture_run(tmp_path)
    before = {str(p): file_hash(p) for p in run.artifact_dir.rglob("*") if p.is_file()}
    result = copying_diagnostics(run.artifact_dir, Path.cwd())
    assert Path(result["artifact_dir"]) != run.artifact_dir
    assert (Path(result["artifact_dir"]) / "copying_diagnostics.json").exists()
    assert before == {str(p): file_hash(p) for p in run.artifact_dir.rglob("*") if p.is_file()}


def test_changed_raw_dataset_fails_source_binding(tmp_path, monkeypatch):
    from dataclasses import replace

    from rcqasyn.datasets import load_dataset
    from rcqasyn.experiments import diagnostics

    run = fixture_run(tmp_path)

    def changed(*args):
        dataset = load_dataset(*args)
        return replace(dataset, fingerprint="different")

    monkeypatch.setattr(diagnostics, "load_dataset", changed)
    with pytest.raises(ValueError, match="provenance"):
        copying_diagnostics(run.artifact_dir, Path.cwd(), write=False)


def test_incomplete_and_tampered_bundles_are_rejected(tmp_path):
    run = fixture_run(tmp_path)
    assert read_bundle(run.artifact_dir)["run_id"] == run.run_id
    manifest = run.artifact_dir / "manifest.json"
    content = json.loads(manifest.read_text())
    content["status"] = "running"
    manifest.write_text(json.dumps(content))
    with pytest.raises(ValueError):
        read_bundle(run.artifact_dir)


def test_generated_report_refresh_cannot_rewrite_history(tmp_path):
    destination = tmp_path / "reports" / "trtr-example.json"
    destination.parent.mkdir()
    destination.write_text(json.dumps({"TRTR": {}, "seed": 42}))
    before = destination.read_bytes()
    with pytest.raises(FileExistsError):
        _write_reusable_manifest(destination, {"TRTR": {}, "seed": 43})
    assert destination.read_bytes() == before


def test_multiple_executions_of_one_dataset_survive_aggregation():
    comparisons = [
        {
            "dataset_id": "same",
            "run_id": identity,
            "baselines": {},
            "baseline_comparison": [{"run": identity}],
        }
        for identity in ("one", "two")
    ]
    report = cross_dataset_comparison(comparisons)
    assert len(report["datasets"]) == 2
    assert {row["run_id"] for row in report["datasets"]} == {"one", "two"}
    assert len(report["baseline_comparison_tables"]) == 2


def test_legacy_completed_artifacts_remain_readable_without_modification():
    paths = [p for p in Path("artifacts/runs").glob("*") if (p / "manifest.json").is_file()]
    assert paths
    for path in paths:
        before = {str(p): file_hash(p) for p in path.rglob("*") if p.is_file()}
        manifest = json.loads((path / "manifest.json").read_text())
        if manifest.get("status") == "completed":
            comparison = read_bundle(path)
            assert comparison["legacy_compatibility"]["success_verified"] is False
        assert before == {str(p): file_hash(p) for p in path.rglob("*") if p.is_file()}


def test_report_and_human_export_overwrite_flags_cannot_replace_existing_files(tmp_path):
    from rcqasyn.experiments.analysis import export_human_review
    from rcqasyn.storage.artifacts import immutable_text_stream

    run = fixture_run(tmp_path)
    before = file_hash(run.artifact_dir / "human_review.csv")
    with pytest.raises(FileExistsError):
        export_human_review(run.artifact_dir, overwrite=True)
    assert file_hash(run.artifact_dir / "human_review.csv") == before
    for suffix in ("jsonl", "csv", "yaml"):
        path = tmp_path / ("existing." + suffix)
        path.write_text("historical")
        with pytest.raises(FileExistsError), immutable_text_stream(path) as stream:
            stream.write("changed")
        assert path.read_text() == "historical"


def test_missing_or_unknown_source_manifest_is_not_legacy_success(tmp_path):
    from rcqasyn.experiments.readers import validate_source

    path = tmp_path / "incomplete"
    path.mkdir()
    with pytest.raises(OSError):
        validate_source(path)
    (path / "manifest.json").write_text(
        json.dumps({"schema_version": "future-unknown", "status": "completed"})
    )
    with pytest.raises(ValueError):
        validate_source(path)


def test_protected_writer_does_not_even_create_child_directories(tmp_path):
    from rcqasyn.experiments.human_audit import write_human_audit_reports
    from rcqasyn.experiments.runner import _write_jsonl, _write_yaml

    run = fixture_run(tmp_path)
    child = run.artifact_dir / "forbidden-child"
    for write in (
        lambda: _write_yaml(child / "config.yaml", {}),
        lambda: _write_jsonl(child / "events.jsonl", []),
        lambda: write_human_audit_reports(
            {"human_summary": {"source_files": {"primary": {"sha256": "fixture"}}}}, child
        ),
    ):
        with pytest.raises(FileExistsError):
            write()
        assert not child.exists()
