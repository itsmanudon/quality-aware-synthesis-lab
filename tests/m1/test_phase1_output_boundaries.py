"""Derived destinations retain aliases; refused writes leave the entire tree intact."""

from __future__ import annotations

import hashlib
import itertools
import os
import runpy
import subprocess
import threading
from pathlib import Path

import pytest

from rcqasyn.config import load_experiment_config
from rcqasyn.experiments import run_experiment, runner
from rcqasyn.experiments.analysis import export_disagreements, export_human_review
from rcqasyn.experiments.diagnostics import (
    copying_diagnostics,
    p1_human_review_sample,
    support_diagnostics,
)
from rcqasyn.experiments.human_audit import write_human_audit_reports
from rcqasyn.experiments.readers import derived_directory, read_bundle
from rcqasyn.storage.artifacts import immutable_text_stream, write_text
from rcqasyn.storage.jsonl import append_jsonl
from rcqasyn.storage.ownership import execution_scope, own_run, seal_bundle, verify_seal


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    return run_experiment(
        config.model_copy(update={"artifact_root": tmp_path_factory.mktemp("source")}),
        replay=True,
    ).artifact_dir


def tree_snapshot(root: Path) -> dict:
    """Include directories, file bytes and mtimes, not merely the seal inventory."""
    result = {}
    for path in root.rglob("*"):
        stat = path.lstat()
        result[path.relative_to(root).as_posix()] = (
            "directory" if path.is_dir() else "file",
            stat.st_mtime_ns,
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
        )
    result["."] = ("directory", root.stat().st_mtime_ns, None)
    return result


def assert_refusal_unchanged(root: Path, operation) -> None:
    before = tree_snapshot(root)
    with pytest.raises((FileExistsError, ValueError)):
        operation()
    assert tree_snapshot(root) == before
    verify_seal(root)


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
        try:
            path.symlink_to(target, target_is_directory=True)
        except OSError as error:
            if os.name == "nt" and error.winerror in {5, 1314}:
                pytest.skip("Windows symlink permission")
            raise


def derive(api: str, source: Path, destination: Path):
    if api == "directory":
        return derived_directory(source, "probe", destination)
    if api == "review":
        return export_human_review(source, output_dir=destination)
    if api == "disagreements":
        return export_disagreements(source, output_dir=destination)
    if api == "copying":
        return copying_diagnostics(source, Path.cwd(), output_dir=destination)
    return support_diagnostics(source, Path.cwd(), output_dir=destination)


APIS = ["directory", "review", "disagreements", "copying", "support"]
CHAINS = list(itertools.product(["symlink", "junction"], repeat=2))


@pytest.mark.parametrize("api", APIS)
@pytest.mark.parametrize("chain", CHAINS)
def test_derived_output_preserves_every_intermediate_alias(tmp_path, source, api, chain):
    protected = tmp_path / "artifacts" / "reports"
    protected.mkdir(parents=True)
    ordinary = tmp_path / "ordinary"
    ordinary.mkdir()
    alias(protected / "exit", ordinary, chain[1])
    alias(tmp_path / "gateway", protected / "exit", chain[0])
    destination = tmp_path / "gateway" / "missing" / "output"
    before = tree_snapshot(ordinary)
    source_before = tree_snapshot(source)
    with pytest.raises(FileExistsError):
        write_text(destination / "generic.txt", "forbidden")
    with pytest.raises(FileExistsError):
        derive(api, source, destination)
    assert tree_snapshot(ordinary) == before
    assert tree_snapshot(source) == source_before
    read_bundle(source)


@pytest.mark.parametrize("api", APIS)
@pytest.mark.parametrize("protection", ["artifacts/reports", "data/manifests", "test-results", "sealed", "legacy"])
def test_derived_output_cannot_precreate_in_protected_destination(tmp_path, source, api, protection):
    root = tmp_path / protection
    root.mkdir(parents=True)
    if protection != "legacy":
        write_text(root / "original.txt", "original")
        seal_bundle(root)
    if protection == "legacy":
        (root / "manifest.json").write_text('{"status":"completed"}', encoding="utf-8")
    before = tree_snapshot(root)
    with pytest.raises(FileExistsError):
        derive(api, source, root / "missing" / "output")
    assert tree_snapshot(root) == before
    if protection != "legacy":
        verify_seal(root)


def adapter(kind: str, source: Path, path: Path):
    if kind == "p1":
        return p1_human_review_sample([source], Path.cwd(), path)
    if kind == "jsonl":
        return runner._write_jsonl(path, [{"new": True}])
    if kind == "empty-jsonl":
        return runner._write_jsonl(path, [])
    if kind == "yaml":
        return runner._write_yaml(path, {"new": True})
    if kind == "json":
        return runner._write_json(path, {"new": True})
    if kind == "csv":
        with immutable_text_stream(path) as stream:
            stream.write("column\nvalue\n")
    elif kind == "text":
        return write_text(path, "value")
    elif kind == "audit":
        return write_human_audit_reports(
            {"human_summary": {"source_files": {"primary": {"sha256": "fixture"}}}},
            path.parent,
        )
    else:
        return append_jsonl(path, [{"new": True}])


@pytest.mark.parametrize("kind", ["p1", "jsonl", "empty-jsonl", "yaml", "json", "csv", "text", "audit", "append"])
@pytest.mark.parametrize("alias_kind", [None, "symlink", "junction"])
def test_public_refusal_preserves_sealed_namespace(tmp_path, source, kind, alias_kind):
    root = tmp_path / "sealed"
    root.mkdir()
    write_text(root / "original.txt", "original")
    seal_bundle(root)
    destination = root
    if alias_kind:
        destination = tmp_path / "gateway"
        alias(destination, root, alias_kind)
    assert_refusal_unchanged(
        root, lambda: adapter(kind, source, destination / "missing" / "nested" / "output"),
    )
    assert not (root / "missing").exists()


@pytest.mark.parametrize("kind", ["jsonl", "empty-jsonl", "yaml"])
def test_runner_refusal_after_preflight_seal_creates_no_directories(tmp_path, source, monkeypatch, kind):
    root = tmp_path / "bundle"
    root.mkdir()
    write_text(root / "original.txt", "original")
    paused, release = threading.Event(), threading.Event()
    real_check = runner.assert_writable

    def pause_after_check(path):
        real_check(path)
        paused.set()
        assert release.wait(10)

    monkeypatch.setattr(runner, "assert_writable", pause_after_check)
    errors = []

    def writer():
        try:
            adapter(kind, source, root / "missing" / "nested" / "output")
        except Exception as error:  # noqa: BLE001 - surface every thread error in assertions
            errors.append(error)

    thread = threading.Thread(target=writer)
    thread.start()
    try:
        assert paused.wait(10)
        seal_bundle(root)
        before = tree_snapshot(root)
        release.set()
        thread.join(10)
        assert not thread.is_alive()
        assert len(errors) == 1 and isinstance(errors[0], FileExistsError)
        assert tree_snapshot(root) == before
        verify_seal(root)
    finally:
        release.set()
        thread.join(10)


@pytest.mark.parametrize("api", APIS)
def test_ordinary_explicit_derived_directory_succeeds(tmp_path, source, api):
    destination = tmp_path / "missing" / "ordinary-output"
    derive(api, source, destination)
    assert (destination / "source.json").is_file()
    if api != "directory":
        verify_seal(destination)


def test_default_derived_namespace_succeeds(source):
    destination = derived_directory(source, "positive")
    assert (destination / "source.json").is_file()
    assert source not in destination.parents


@pytest.mark.parametrize("kind", ["p1", "jsonl", "empty-jsonl", "yaml", "json", "csv", "text", "append"])
@pytest.mark.parametrize("owned", [False, True])
def test_authorized_adapters_create_parents_normally(tmp_path, source, kind, owned):
    root = tmp_path / "ordinary"
    root.mkdir()
    with execution_scope():
        if owned:
            own_run(root)
        destination = root / "new" / "nested" / "output"
        adapter(kind, source, destination)
        assert destination.is_file()


@pytest.mark.parametrize("api", APIS)
@pytest.mark.parametrize("alias_kind", ["symlink", "junction"])
def test_single_alias_into_sealed_output_is_side_effect_free(tmp_path, source, api, alias_kind):
    root = tmp_path / "sealed"
    root.mkdir()
    write_text(root / "original.txt", "original")
    seal_bundle(root)
    gateway = tmp_path / "gateway"
    alias(gateway, root, alias_kind)
    assert_refusal_unchanged(root, lambda: derive(api, source, gateway / "new" / "output"))


@pytest.mark.parametrize("protection", ["artifacts/derived", "artifacts/reports", "data/manifests"])
def test_fresh_unsealed_namespace_remains_usable(tmp_path, source, protection):
    destination = tmp_path / protection / "fresh-output"
    derived_directory(source, "positive", destination)
    assert (destination / "source.json").is_file()


def test_p1_report_adapter_does_not_precreate_sealed_child(tmp_path):
    namespace = runpy.run_path("experiments/m1_5_p1_reports.py")
    root = tmp_path / "sealed"
    root.mkdir()
    write_text(root / "original.txt", "original")
    seal_bundle(root)
    write = namespace["write_disagreement_summary"]
    write.__globals__["OUT"] = root / "missing" / "nested"
    assert_refusal_unchanged(root, lambda: write({"probe": True}))


@pytest.mark.parametrize("command", ["analyze", "export-blind", "import-blind"])
@pytest.mark.parametrize("chain", CHAINS)
def test_human_review_cli_preserves_output_alias_chain(tmp_path, monkeypatch, command, chain):
    from importlib import import_module

    from typer.testing import CliRunner

    cli = import_module("rcqasyn.cli.app")
    protected = tmp_path / "artifacts" / "reports"
    protected.mkdir(parents=True)
    ordinary = tmp_path / "ordinary"
    ordinary.mkdir()
    alias(protected / "exit", ordinary, chain[1])
    alias(tmp_path / "gateway", protected / "exit", chain[0])
    destination = tmp_path / "gateway" / "missing" / "output"
    before = tree_snapshot(ordinary)

    def guarded_analysis(*args, output_dir, **kwargs):
        write_text(output_dir / "result.json", "forbidden")

    def guarded_export(master, output_dir, **kwargs):
        write_text(output_dir / "review.csv", "forbidden")

    def guarded_import(master, reviewer, manifest, output, **kwargs):
        write_text(output, "forbidden")

    monkeypatch.setattr(cli, "analyze_review", guarded_analysis)
    monkeypatch.setattr(cli, "export_blinded_reviews", guarded_export)
    monkeypatch.setattr(cli, "import_blinded_review", guarded_import)
    monkeypatch.setattr(cli, "review_status", lambda *args: {"rows": 1})
    args = ["human-review", command, "master.csv", "--root", str(tmp_path)]
    if command == "import-blind":
        args.insert(3, "reviewer.csv")
        args.extend(["--manifest", "manifest.json", "--annotator-id", "A", "--output", str(destination)])
    else:
        args.extend(["--output-dir", str(destination)])
    result = CliRunner().invoke(cli.app, args)
    assert result.exit_code != 0
    assert isinstance(result.exception, FileExistsError), result.output
    assert tree_snapshot(ordinary) == before


@pytest.mark.parametrize("api", APIS)
@pytest.mark.parametrize("alias_kind", ["symlink", "junction"])
def test_nonhistorical_alias_output_succeeds_after_guarded_reservation(tmp_path, source, api, alias_kind):
    ordinary = tmp_path / "ordinary"
    ordinary.mkdir()
    gateway = tmp_path / "gateway"
    alias(gateway, ordinary, alias_kind)
    derive(api, source, gateway / "fresh-output")
    destination = ordinary / "fresh-output"
    assert (destination / "source.json").is_file()
    if api != "directory":
        verify_seal(destination)


@pytest.mark.parametrize("alias_kind", ["symlink", "junction"])
def test_human_audit_cli_ordinary_alias_seals_after_guarded_writes(tmp_path, alias_kind):
    from typer.testing import CliRunner

    from rcqasyn.cli.app import app

    fixture = runpy.run_path("tests/m1/test_human_audit.py")
    review = fixture["_write_review"](
        tmp_path / "review.csv", [fixture["_row"](1, human_valid="true")],
    )
    ordinary = tmp_path / "ordinary"
    ordinary.mkdir()
    gateway = tmp_path / "gateway"
    alias(gateway, ordinary, alias_kind)
    result = CliRunner().invoke(app, [
        "human-review", "analyze", str(review), "--root", str(tmp_path),
        "--output-dir", str(gateway / "fresh-report"),
    ])
    assert result.exit_code == 0, result.output + str(result.exception)
    verify_seal(ordinary / "fresh-report")
