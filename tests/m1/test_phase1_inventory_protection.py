"""The public paper inventory API and CLI must not bypass historical storage guards."""

from __future__ import annotations

import json
import os
import subprocess
import threading

import pytest
from typer.testing import CliRunner

from rcqasyn.cli.app import app
from rcqasyn.literature.inventory import PaperInventoryEntry, write_inventory
from rcqasyn.storage.ownership import execution_scope, own_run, seal_bundle, verify_seal

PROTECTIONS = ["sealed", "legacy", "legacy-v1", "artifacts/reports", "data/manifests", "test-results"]
CHAINS = [("symlink", "symlink"), ("junction", "junction"), ("symlink", "junction"), ("junction", "symlink")]
ORIGINAL = b"preserved,record\n1,2\n"
HEADER = b"filename,relative_path,sha256,size_bytes\n"


@pytest.fixture
def project(tmp_path):
    (tmp_path / "configs").mkdir()
    (tmp_path / "literature/papers").mkdir(parents=True)
    (tmp_path / "configs/base.yaml").write_text(
        "project:\n  name: inventory-test\n  seed: 42\n"
        "artifacts:\n  root: artifacts\nliterature:\n"
        "  papers_dir: literature/papers\n  notes_dir: literature/notes\n",
        encoding="utf-8",
    )
    return tmp_path


def _protect(root, protection):
    directory = root / protection
    directory.mkdir(parents=True)
    if protection == "sealed":
        (directory / "historic.csv").write_bytes(ORIGINAL)
        seal_bundle(directory)
    elif protection in {"legacy", "legacy-v1"}:
        manifest = {"status": "completed"}
        if protection == "legacy-v1":
            manifest["schema_version"] = "m1-run-v1"
        (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return directory


def _alias(link, target, kind):
    if kind == "junction":
        if os.name != "nt":
            pytest.skip("Windows junction fixture")
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        link.symlink_to(target, target_is_directory=True)


def _denied(entrypoint, destination, project):
    if entrypoint == "api":
        with pytest.raises(FileExistsError, match="immutable|historical"):
            write_inventory([], destination)
    else:
        result = CliRunner().invoke(
            app, ["papers", "index", "--root", str(project), "--output", str(destination)]
        )
        assert result.exit_code != 0
        assert isinstance(result.exception, FileExistsError)
        assert "Indexed" not in result.stdout


@pytest.mark.parametrize("entrypoint", ["api", "cli"])
@pytest.mark.parametrize("protection", PROTECTIONS)
def test_inventory_cannot_replace_direct_protected_history(project, protection, entrypoint):
    directory = _protect(project, protection)
    destination = directory / "historic.csv"
    if not destination.exists():
        destination.write_bytes(ORIGINAL)
    before = {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}
    _denied(entrypoint, destination, project)
    assert {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()} == before
    if protection == "sealed":
        verify_seal(directory)


@pytest.mark.parametrize("entrypoint", ["api", "cli"])
@pytest.mark.parametrize("protection", PROTECTIONS)
@pytest.mark.parametrize("first,second", CHAINS)
def test_inventory_cannot_escape_intermediate_history_via_two_aliases(
    project, protection, entrypoint, first, second
):
    directory = _protect(project, protection)
    outside = project / "ordinary"
    outside.mkdir()
    target = outside / "historic.csv"
    target.write_bytes(ORIGINAL)
    _alias(directory / "redirect", outside, second)
    _alias(project / "entrance", directory / "redirect", first)
    markers = {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}
    _denied(entrypoint, project / "entrance/historic.csv", project)
    assert target.read_bytes() == ORIGINAL
    assert {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()} == markers


@pytest.mark.parametrize("first,second", CHAINS)
@pytest.mark.parametrize("claim", ["root", "history", "alias"])
def test_inventory_ownership_claim_cannot_authorize_intermediate_history(project, first, second, claim):
    history = _protect(project, "artifacts/reports")
    outside = project / "ordinary"
    outside.mkdir()
    target = outside / "historic.csv"
    target.write_bytes(ORIGINAL)
    _alias(history / "redirect", outside, second)
    _alias(project / "entrance", history / "redirect", first)
    with execution_scope():
        own_run({"root": project, "history": history, "alias": project / "entrance"}[claim])
        _denied("api", project / "entrance/historic.csv", project)
    assert target.read_bytes() == ORIGINAL


@pytest.mark.parametrize("entrypoint", ["api", "cli"])
@pytest.mark.parametrize("protection", PROTECTIONS)
def test_inventory_outside_hardlink_replacement_preserves_protected_source(project, protection, entrypoint):
    directory = _protect(project, protection)
    original = directory / "historic.csv"
    if not original.exists():
        original.write_bytes(ORIGINAL)
    outside = project / "outside.csv"
    os.link(original, outside)
    if entrypoint == "api":
        write_inventory([], outside)
    else:
        result = CliRunner().invoke(app, ["papers", "index", "--root", str(project), "--output", str(outside)])
        assert result.exit_code == 0, result.output
    assert original.read_bytes() == ORIGINAL
    assert outside.read_bytes() == HEADER
    assert not os.path.samefile(original, outside)
    if protection == "sealed":
        verify_seal(directory)


def test_inventory_nonhistorical_replacement_preserves_csv_serialization(project):
    destination = project / "ordinary/new/inventory.csv"
    write_inventory([], destination)
    assert destination.read_bytes() == HEADER
    write_inventory([PaperInventoryEntry('a,"é.pdf', "literature/papers/a.pdf", "abc", 7)], destination)
    assert destination.read_bytes() == HEADER + '"a,""é.pdf",literature/papers/a.pdf,abc,7\n'.encode()


def test_inventory_active_owned_updates_stop_after_sealing(project):
    directory = project / "artifacts/derived/active"
    directory.mkdir(parents=True)
    with execution_scope():
        own_run(directory)
        destination = directory / "inventory.csv"
        write_inventory([], destination)
        write_inventory([PaperInventoryEntry("a.pdf", "papers/a.pdf", "abc", 1)], destination)
        seal_bundle(directory)
        _denied("api", destination, project)
    verify_seal(directory)


@pytest.mark.parametrize("first", ["writer", "seal"])
def test_inventory_replacement_and_sealing_are_mutually_exclusive(project, monkeypatch, first):
    from rcqasyn.storage import artifacts, ownership

    bundle = project / "bundle"
    bundle.mkdir()
    destination = bundle / "inventory.csv"
    destination.write_bytes(ORIGINAL)
    paused, release, started, finished = (threading.Event() for _ in range(4))
    original_operation = artifacts.os.replace if first == "writer" else ownership._bundle_inventory

    def delay(*args, **kwargs):
        paused.set()
        assert release.wait(15)
        return original_operation(*args, **kwargs)

    if first == "writer":
        monkeypatch.setattr(artifacts.os, "replace", delay)
    else:
        monkeypatch.setattr(ownership, "_bundle_inventory", delay)
    results = {}

    def operation(name):
        try:
            if name != first:
                started.set()
            if name == "writer":
                write_inventory([], destination)
            else:
                seal_bundle(bundle)
            results[name] = "ok"
        except (OSError, ValueError, RuntimeError, AssertionError) as error:
            results[name] = error
        finally:
            if name != first:
                finished.set()

    second = "seal" if first == "writer" else "writer"
    threads = [threading.Thread(target=operation, args=(name,)) for name in (first, second)]
    threads[0].start()
    try:
        assert paused.wait(15)
        threads[1].start()
        assert started.wait(15)
        assert not finished.wait(0.2)
    finally:
        release.set()
        for thread in threads:
            if thread.ident is not None:
                thread.join(15)
                assert not thread.is_alive()
    assert results["seal"] == "ok"
    if first == "writer":
        assert results["writer"] == "ok"
        assert destination.read_bytes() == HEADER
    else:
        assert isinstance(results["writer"], FileExistsError)
        assert destination.read_bytes() == ORIGINAL
    verify_seal(bundle)
