"""CLI input lookup must not erase the logical anchor of protected outputs."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from importlib import import_module
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from rcqasyn.config import load_experiment_config
from rcqasyn.experiments import run_experiment, runner
from rcqasyn.experiments.readers import read_bundle
from rcqasyn.generation.provider import ReplayGenerator
from rcqasyn.storage.artifacts import write_text

cli = import_module("rcqasyn.cli.app")


def tree(root):
    result = {}
    for p in [root, *root.rglob("*")]:
        metadata = p.lstat()
        result[str(p.relative_to(root))] = (
            metadata.st_mtime_ns,
            os.readlink(p) if p.is_symlink() or p.is_junction() else None,
            hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None,
        )
    return result


def link(path, target, kind):
    if kind == "j":
        if os.name != "nt":
            pytest.skip("Windows junction fixture")
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(path), str(target)],
                                capture_output=True, text=True, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        path.symlink_to(target, target_is_directory=True)


@pytest.fixture
def project(tmp_path):
    physical = tmp_path / "ordinary-project"
    for part in ("configs", "prompts", "tests/fixtures"):
        shutil.copytree(Path.cwd() / part, physical / part)
    raw = yaml.safe_load((physical / "configs/experiments/replay.yaml").read_text())
    raw["generation"].update({"prompt_version": "v2", "transport_version": "v2"})
    raw["artifact_root"] = "artifacts"
    raw["run_id"] = "cli-root-test"
    (physical / "experiment.yaml").write_text(yaml.safe_dump(raw), encoding="utf-8")
    return physical


def protected_chain(tmp_path, project, chain):
    protected = tmp_path / "artifacts/reports"
    protected.mkdir(parents=True)
    (protected / "recorded.txt").write_text("preserved")
    link(protected / "exit", project, chain[-1])
    if chain.startswith("logical"):
        return protected / "exit"
    if chain.startswith("physical"):
        shutil.copytree(project, protected / "project")
        link(tmp_path / "gateway", protected / "project", chain[-1])
    elif chain.startswith("long"):
        link(tmp_path / "middle", protected / "exit", chain[-1])
        link(tmp_path / "gateway", tmp_path / "middle", chain[-1])
    else:
        link(tmp_path / "gateway", protected / "exit", chain[0])
    return tmp_path / "gateway"


def assert_blocked(tmp_path, logical, entry, monkeypatch):
    providers = []
    reservations = []

    def provider(*args, **kwargs):
        providers.append("constructed")
        raise AssertionError("provider constructed before output authorization")

    def reserve(*args, **kwargs):
        reservations.append("reserved")
        raise AssertionError("reservation reached for protected root")

    monkeypatch.setattr(runner, "_provider", provider)
    monkeypatch.setattr(runner, "create_run_dir", reserve)
    monkeypatch.setattr(runner, "_require_real_provider", lambda config: None)
    before = tree(tmp_path)
    if entry == "api":
        config, _ = load_experiment_config(Path("experiment.yaml"), logical)
        with pytest.raises(FileExistsError):
            run_experiment(config, project_root=logical, replay=True)
    else:
        command = "run" if entry == "run" else "replay"
        result = CliRunner().invoke(cli.app, ["baselines", command, "--root", str(logical),
                                             "--config", "experiment.yaml"])
        assert result.exit_code == 1 and "immutable" in result.output, result.output
    assert providers == []
    assert reservations == []
    assert tree(tmp_path) == before
    assert not (logical / "artifacts").exists()


@pytest.mark.parametrize("chain", ["ss", "sj", "js", "jj"])
@pytest.mark.parametrize("entry", ["api", "run", "replay"])
@pytest.mark.parametrize("spelling", ["relative", "absolute"])
def test_cli_project_root_retains_protected_intermediate_aliases(
    tmp_path, project, monkeypatch, chain, entry, spelling,
):
    logical = protected_chain(tmp_path, project, chain)
    monkeypatch.chdir(tmp_path)
    if spelling == "relative":
        logical = logical.relative_to(tmp_path)
    assert_blocked(tmp_path, logical, entry, monkeypatch)


@pytest.mark.parametrize("chain", ["long-s", "long-j", "logical-s", "logical-j", "physical-s", "physical-j"])
@pytest.mark.parametrize("entry", ["api", "run", "replay"])
def test_additional_cli_root_ancestry_is_side_effect_free(tmp_path, project, monkeypatch, chain, entry):
    logical = protected_chain(tmp_path, project, chain)
    monkeypatch.chdir(tmp_path)
    assert_blocked(tmp_path, logical.relative_to(tmp_path), entry, monkeypatch)


@pytest.mark.parametrize("spelling", ["relative", "absolute", "dotdot", "alias"])
@pytest.mark.parametrize("entry", ["api", "run", "replay"])
def test_ordinary_cli_roots_keep_physical_input_lookup(tmp_path, project, monkeypatch, spelling, entry):
    if spelling == "alias":
        link(tmp_path / "gateway", project, "s")
        logical = Path("gateway")
    elif spelling == "relative":
        logical = Path("ordinary-project")
    elif spelling == "dotdot":
        (tmp_path / "child").mkdir()
        logical = Path("child/../ordinary-project")
    else:
        logical = project
    if entry == "run":
        fixture = project / "tests/fixtures/replay_fixture.json"
        raw = yaml.safe_load(fixture.read_text())
        raw["generation"].insert(0, {"response": {"ok": True}})
        fixture.write_text(json.dumps(raw), encoding="utf-8")
        monkeypatch.setattr(runner, "_require_real_provider", lambda config: None)
        monkeypatch.setattr(runner, "_provider", lambda config, root, replay: ReplayGenerator(config.fixture, model=config.model))
    monkeypatch.chdir(tmp_path)
    if entry == "api":
        config, _ = load_experiment_config(Path("experiment.yaml"), logical)
        result = run_experiment(config, project_root=logical, replay=True)
        directory = result.artifact_dir
    else:
        result = CliRunner().invoke(cli.app, ["baselines", entry, "--root", str(logical),
                                             "--config", "experiment.yaml"])
        assert result.exit_code == 0, result.output
        directory = project / "artifacts/runs/cli-root-test"
    read_bundle(directory)


@pytest.mark.parametrize("chain", ["ss", "jj"])
@pytest.mark.parametrize("command", ["papers", "prepare", "acquisition", "trtr", "compare", "diagnose", "analyze", "blind", "import"])
def test_mixed_cli_consumers_preserve_output_root(tmp_path, project, monkeypatch, chain, command):
    logical = protected_chain(tmp_path, project, chain)
    monkeypatch.chdir(tmp_path)
    options = ["--root", str(logical.relative_to(tmp_path))]
    if command == "papers":
        args = ["papers", "index", *options]
    elif command == "prepare":
        args = ["datasets", "prepare", "dev-small", *options]
    elif command == "acquisition":
        args = ["datasets", "record-acquisition", "dev-small", "--source-url", "https://example.test/source", *options]
    elif command == "trtr":
        args = ["baselines", "trtr", "dev-small", *options]
    elif command == "compare":
        monkeypatch.setattr("rcqasyn.experiments.readers.read_bundle", lambda path: {})
        monkeypatch.setattr(cli, "cross_dataset_comparison", lambda inputs: {})
        args = ["baselines", "compare", "artifacts/runs/source", *options]
    elif command == "diagnose":
        def diagnostic(run_dir, project_root, *, output_dir=None):
            path = output_dir or run_dir.parent.parent / "derived/attempt"
            write_text(path / "attempt.json", "guarded")
            return {}
        monkeypatch.setattr("rcqasyn.experiments.copying_diagnostics", diagnostic)
        monkeypatch.setattr("rcqasyn.experiments.support_diagnostics", diagnostic)
        args = ["baselines", "diagnose", "artifacts/runs/source", *options]
    elif command == "analyze":
        def analyze(source, *, project_root, output_dir, **kwargs):
            write_text(output_dir / "attempt.json", "guarded")
            return {}
        monkeypatch.setattr(cli, "analyze_review", analyze)
        args = ["human-review", "analyze", "review.csv", *options]
    elif command == "blind":
        monkeypatch.setattr(cli, "review_status", lambda source: {"rows": 1})
        def blind(source, output_dir, **kwargs):
            write_text(output_dir / "attempt.json", "guarded")
            return {}
        monkeypatch.setattr(cli, "export_blinded_reviews", blind)
        args = ["human-review", "export-blind", "review.csv", *options]
    else:
        def imported(master, reviewer, manifest, output, **kwargs):
            write_text(output, "guarded")
            return output
        monkeypatch.setattr(cli, "import_blinded_review", imported)
        args = ["human-review", "import-blind", "review.csv", "reviewer.csv", "--manifest", "map.json",
                "--annotator-id", "fixture", "--output", "annotations/new.csv", *options]
    before = tree(tmp_path)
    result = CliRunner().invoke(cli.app, args)
    assert result.exit_code == 1, result.output
    assert "immutable" in result.output or isinstance(result.exception, FileExistsError), result.output
    assert tree(tmp_path) == before


@pytest.mark.parametrize("protected", [False, True])
def test_real_diagnostic_cli_keeps_source_readonly_and_guards_logical_output(
    tmp_path, project, monkeypatch, protected,
):
    config, _ = load_experiment_config(project / "experiment.yaml", project)
    source = run_experiment(config, project_root=project, replay=True).artifact_dir
    if protected:
        logical = protected_chain(tmp_path, project, "ss")
    else:
        logical = project
    monkeypatch.chdir(tmp_path)
    before = tree(tmp_path)
    source_before = tree(source)
    result = CliRunner().invoke(cli.app, ["baselines", "diagnose", "artifacts/runs/cli-root-test",
                                         "--root", str(logical.relative_to(tmp_path))])
    assert tree(source) == source_before
    read_bundle(source)
    if protected:
        assert result.exit_code == 1 and "immutable" in result.output, result.output
        assert tree(tmp_path) == before
    else:
        assert result.exit_code == 0, result.output
        directories = list((project / "artifacts/derived").iterdir())
        assert len(directories) == 2
        assert all((directory / "FINALIZED.json").is_file() for directory in directories)


@pytest.mark.parametrize("command", ["run", "replay"])
def test_default_discovery_keeps_linked_cwd_ancestry(tmp_path, project, monkeypatch, command):
    (project / "nested").mkdir()
    history = tmp_path / "artifacts/reports"
    history.mkdir(parents=True)
    link(history / "exit", project / "nested", "s")
    link(tmp_path / "gateway", history / "exit", "s")
    monkeypatch.chdir(tmp_path / "gateway")
    calls = []
    reservations = []

    def provider(*args, **kwargs):
        calls.append("constructed")
        raise AssertionError("provider reached through lost working-directory ancestry")

    def reserve(*args, **kwargs):
        reservations.append("reserved")
        raise AssertionError("protected working-directory reservation reached")

    monkeypatch.setattr(runner, "_provider", provider)
    monkeypatch.setattr(runner, "create_run_dir", reserve)
    monkeypatch.setattr(runner, "_require_real_provider", lambda config: None)
    before = tree(tmp_path)
    result = CliRunner().invoke(cli.app, ["baselines", command, "--config", "experiment.yaml"])
    assert result.exit_code == 1 and "immutable" in result.output, result.output
    assert calls == [] and reservations == []
    assert tree(tmp_path) == before


@pytest.mark.parametrize("command", [["list"], ["inspect", "dev-small"]])
def test_readonly_discovery_still_uses_physical_project(tmp_path, project, monkeypatch, command):
    (project / "nested").mkdir()
    history = tmp_path / "artifacts/reports"
    history.mkdir(parents=True)
    link(history / "exit", project / "nested", "s")
    link(tmp_path / "gateway", history / "exit", "s")
    monkeypatch.chdir(tmp_path / "gateway")
    before = tree(tmp_path)
    result = CliRunner().invoke(cli.app, ["datasets", *command])
    assert result.exit_code == 0 and "dev-small" in result.output, result.output
    assert tree(tmp_path) == before
