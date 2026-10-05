"""Configured output roots must reach authorization without losing alias hops."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from rcqasyn.cli.app import app
from rcqasyn.config import load_experiment_config
from rcqasyn.experiments import run_experiment, runner
from rcqasyn.experiments.readers import read_bundle
from rcqasyn.storage.artifacts import create_run_dir, write_text
from rcqasyn.storage.ownership import execution_scope, own_run, seal_bundle


def snapshot(root: Path) -> dict:
    result = {}
    for entry in [root, *root.rglob("*")]:
        metadata = entry.lstat()
        result[str(entry.relative_to(root))] = (
            metadata.st_mtime_ns,
            os.readlink(entry) if entry.is_symlink() or entry.is_junction() else None,
            hashlib.sha256(entry.read_bytes()).hexdigest() if entry.is_file() else None,
        )
    return result


def alias(path: Path, target: Path, kind: str) -> None:
    if kind == "junction":
        if os.name != "nt":
            pytest.skip("Windows junction fixture")
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(path), str(target)],
            capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        path.symlink_to(target, target_is_directory=True)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    source = Path.cwd()
    for part in ("configs/datasets", "prompts"):
        shutil.copytree(source / part, tmp_path / part)
    fixture_dir = tmp_path / "tests/fixtures"
    fixture_dir.mkdir(parents=True)
    for name in ("dev-small.csv", "replay_fixture.json"):
        shutil.copyfile(source / "tests/fixtures" / name, fixture_dir / name)
    return tmp_path


def config_file(project: Path, destination: str) -> Path:
    raw = yaml.safe_load(Path("configs/experiments/replay.yaml").read_text(encoding="utf-8"))
    raw["artifact_root"] = destination
    raw["generation"].update({"prompt_version": "v2", "transport_version": "v2"})
    raw["run_id"] = "configured-output-test"
    path = project / "experiment.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return path


def protected_root(project: Path, protection: str) -> Path:
    root = project / protection
    root.mkdir(parents=True)
    if protection == "legacy":
        (root / "manifest.json").write_text('{"status":"completed"}', encoding="utf-8")
    elif protection == "sealed":
        write_text(root / "original.txt", "preserved")
        seal_bundle(root)
    return root


@pytest.mark.parametrize("kind", ["symlink", "junction"])
@pytest.mark.parametrize("layout", ["exit", "entry", "logical", "long", "mixed"])
@pytest.mark.parametrize("entrypoint", ["api", "cli"])
def test_configured_alias_root_refuses_before_provider_or_namespace_mutation(
    project, monkeypatch, kind, layout, entrypoint,
):
    protected = protected_root(project, "artifacts/reports")
    outside = project / "outside"
    outside.mkdir()
    if layout == "entry":
        alias(project / "gateway", protected, kind)
        destination = "gateway/artifacts"
    else:
        alias(protected / "exit", outside, kind)
        if layout == "logical":
            destination = "artifacts/reports/exit/artifacts"
        elif layout == "long":
            alias(project / "middle", protected / "exit", kind)
            alias(project / "gateway", project / "middle", kind)
            destination = "gateway/artifacts"
        else:
            first = "junction" if kind == "symlink" else "symlink"
            alias(project / "gateway", protected / "exit", first if layout == "mixed" else kind)
            destination = "gateway/artifacts"
    path = config_file(project, destination)
    config, _ = load_experiment_config(path, project)
    calls = []

    def forbidden_provider(*args, **kwargs):
        calls.append("constructed")
        raise AssertionError("provider constructed before output authorization")

    monkeypatch.setattr(runner, "_provider", forbidden_provider)
    before = snapshot(project)
    with pytest.raises(FileExistsError):
        create_run_dir(project / destination / "runs", config.run_id)
    if entrypoint == "api":
        with pytest.raises(FileExistsError):
            run_experiment(config, project_root=project, replay=True)
    else:
        result = CliRunner().invoke(app, ["baselines", "replay", "--root", str(project), "--config", str(path)])
        assert result.exit_code == 1, result.output
        assert "immutable" in result.output
    assert calls == []
    assert snapshot(project) == before
    assert not (outside / "artifacts").exists()


@pytest.mark.parametrize("protection", ["data/manifests", "test-results", "legacy", "sealed"])
@pytest.mark.parametrize("kind", ["symlink", "junction"])
def test_configured_roots_cannot_claim_existing_history(project, monkeypatch, protection, kind):
    protected = protected_root(project, protection)
    alias(project / "gateway", protected, kind)
    config, _ = load_experiment_config(config_file(project, "gateway/artifacts"), project)
    calls = []
    monkeypatch.setattr(runner, "_provider", lambda *a, **kw: calls.append("constructed"))
    before = snapshot(project)
    with execution_scope():
        own_run(protected)
        with pytest.raises(FileExistsError):
            run_experiment(config, project_root=project, replay=True)
    assert calls == []
    assert snapshot(project) == before


@pytest.mark.parametrize("entrypoint", ["api", "run-cli", "replay-cli"])
def test_relative_direct_history_refuses_without_provider(project, monkeypatch, entrypoint):
    protected = protected_root(project, "artifacts/reports")
    write_text(protected / "original.txt", "preserved")
    seal_bundle(protected)
    path = config_file(project, "artifacts/reports/missing")
    config, _ = load_experiment_config(path, project)
    calls = []
    monkeypatch.setattr(runner, "_provider", lambda *a, **kw: calls.append("constructed"))
    monkeypatch.setattr(runner, "_require_real_provider", lambda config: None)
    before = snapshot(project)
    if entrypoint == "api":
        with pytest.raises(FileExistsError):
            run_experiment(config, project_root=project, replay=True)
    else:
        command = "run" if entrypoint == "run-cli" else "replay"
        result = CliRunner().invoke(app, ["baselines", command, "--root", str(project), "--config", str(path)])
        assert result.exit_code == 1, result.output
        assert "immutable" in result.output
    assert calls == []
    assert snapshot(project) == before


@pytest.mark.parametrize("destination", ["output", "sub/../output", "absolute", "alias"])
def test_allowed_configured_output_and_readonly_fixture_paths(project, destination):
    if destination == "absolute":
        value = str(project / "output")
    elif destination == "alias":
        (project / "ordinary").mkdir()
        alias(project / "gateway", project / "ordinary", "symlink")
        value = "gateway/output"
    else:
        value = destination
    config, _ = load_experiment_config(config_file(project, value), project)
    assert config.generator.fixture == (project / "tests/fixtures/replay_fixture.json").resolve()
    result = run_experiment(config, project_root=project, replay=True)
    assert result.artifact_dir.is_dir()
    read_bundle(result.artifact_dir)


def test_dotdot_does_not_erase_protected_logical_ancestry(project, monkeypatch):
    protected = protected_root(project, "artifacts/reports")
    alias(project / "gateway", protected, "symlink")
    (project / "sub").mkdir()
    config, _ = load_experiment_config(
        config_file(project, "sub/../gateway/artifacts"), project,
    )
    calls = []
    monkeypatch.setattr(runner, "_provider", lambda *a, **kw: calls.append("constructed"))
    before = snapshot(project)
    with pytest.raises(FileExistsError):
        run_experiment(config, project_root=project, replay=True)
    assert calls == []
    assert snapshot(project) == before
