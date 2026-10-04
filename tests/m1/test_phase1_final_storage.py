"""Alias regressions: seals never follow links; history survives path resolution."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from rcqasyn.storage.artifacts import write_json, write_text
from rcqasyn.storage.jsonl import append_jsonl
from rcqasyn.storage.ownership import execution_scope, own_run, seal_bundle, verify_seal

KINDS = ["json", "jsonl", "csv", "yaml"]
PROTECTIONS = ["artifacts/reports", "data/manifests", "test-results", "legacy", "finalized"]


def _alias(alias: Path, target: Path, kind: str, *, directory: bool = True) -> None:
    if kind == "junction":
        if os.name != "nt":
            pytest.skip("junctions require Windows")
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(alias), str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        try:
            alias.symlink_to(target, target_is_directory=directory)
        except OSError as error:
            if os.name == "nt" and error.winerror in {5, 1314}:
                pytest.skip("Windows denied disposable symlink creation")
            raise


def _write(kind: str, path: Path) -> None:
    if kind == "json":
        write_json(path, {"changed": True}, overwrite=True)
    elif kind == "jsonl":
        append_jsonl(path, [{"changed": True}])
    else:
        write_text(path, "changed\n", overwrite=True)


def _protected(root: Path, protection: str) -> Path:
    directory = root / protection / "recorded"
    directory.mkdir(parents=True)
    if protection == "legacy":
        (directory / "manifest.json").write_text('{"status":"completed"}', encoding="utf-8")
    elif protection == "finalized":
        (directory / "manifest.json").write_text(
            '{"schema_version":"m1-run-v2","status":"finalized"}', encoding="utf-8"
        )
        (directory / "FINALIZED.json").write_text("{}", encoding="utf-8")
    return directory


@pytest.mark.parametrize("alias_kind", ["symlink", "junction"])
@pytest.mark.parametrize("target_kind", ["external", "internal", "dangling"])
@pytest.mark.parametrize("nested", [False, True])
def test_seal_rejects_directory_alias_without_inventorying_target(
    tmp_path, alias_kind, target_kind, nested
):
    # Missing junction/reparse detection would seal these aliases and hash outside files.
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    container = bundle / "nested" if nested else bundle
    container.mkdir(exist_ok=True)
    target = bundle / "real" if target_kind == "internal" else tmp_path / "outside"
    if target_kind != "dangling":
        target.mkdir()
        (target / "outside.json").write_text("original", encoding="utf-8")
    _alias(container / "alias", target, alias_kind)
    with pytest.raises(ValueError):
        seal_bundle(bundle)
    assert not (bundle / "FINALIZED.json").exists()
    if target_kind != "dangling":
        assert (target / "outside.json").read_text() == "original"


@pytest.mark.parametrize("dangling", [False, True])
def test_seal_rejects_file_symlink(tmp_path, dangling):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    target = tmp_path / "outside.json"
    if not dangling:
        target.write_text("original", encoding="utf-8")
    _alias(bundle / "alias.json", target, "symlink", directory=False)
    with pytest.raises(ValueError):
        seal_bundle(bundle)
    assert not (bundle / "FINALIZED.json").exists()


@pytest.mark.parametrize("alias_kind", ["symlink", "junction"])
def test_inventory_prunes_staging_alias_directory(tmp_path, alias_kind):
    # Walking a staging junction would expose target files despite staging exclusion.
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "record.json").write_text("record", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    _alias(outside / "recursive", outside, alias_kind)
    _alias(bundle / ".rcqasyn-stage-abandoned", outside, alias_kind)
    seal_bundle(bundle)
    verify_seal(bundle)
    assert set(json.loads((bundle / "FINALIZED.json").read_text())["files"]) == {"record.json"}


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("protection", PROTECTIONS)
@pytest.mark.parametrize("alias_kind", ["symlink", "junction"])
@pytest.mark.parametrize("direction", ["into", "out"])
@pytest.mark.parametrize("claim", [False, True, "alias"])
def test_alias_ancestry_cannot_bypass_history(
    tmp_path, kind, protection, alias_kind, direction, claim
):
    # Resolving the parent alone loses logical history on aliases pointing outside.
    protected = _protected(tmp_path, protection)
    outside = tmp_path / "ordinary"
    outside.mkdir()
    if direction == "out":
        alias = protected / "alias"
        target = outside
    else:
        alias = outside / "alias"
        target = protected
    (target / "nested").mkdir()
    original = target / "nested" / f"old.{kind}"
    original.write_text("historical\n", encoding="utf-8")
    _alias(alias, target, alias_kind)
    destination = alias / "nested" / original.name
    with execution_scope():
        if claim == "alias":
            own_run(alias)
        elif claim:
            own_run(protected)
            own_run(outside)
        with pytest.raises(FileExistsError):
            _write(kind, destination)
    assert original.read_text() == "historical\n"
    assert destination.read_text() == "historical\n"


@pytest.mark.parametrize("kind", KINDS)
def test_real_test_results_namespace_is_immutable(tmp_path, kind):
    destination = tmp_path / "test-results" / "nested" / f"old.{kind}"
    destination.parent.mkdir(parents=True)
    destination.write_text("historical\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        _write(kind, destination)
    assert destination.read_text() == "historical\n"


@pytest.mark.parametrize("alias_kind", ["symlink", "junction"])
@pytest.mark.parametrize("kind", KINDS)
def test_postseal_alias_cannot_write_into_or_out_of_bundle(tmp_path, alias_kind, kind):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "record.json").write_text("record", encoding="utf-8")
    seal_bundle(bundle)
    before = (bundle / "FINALIZED.json").read_bytes()
    outside = tmp_path / "outside"
    outside.mkdir()
    _alias(outside / "into", bundle, alias_kind)
    _alias(bundle / "out", outside, alias_kind)
    for destination in [outside / "into" / f"new.{kind}", bundle / "out" / f"new.{kind}"]:
        with pytest.raises(FileExistsError):
            _write(kind, destination)
        assert not destination.exists()
    assert (bundle / "FINALIZED.json").read_bytes() == before
    with pytest.raises(ValueError):
        verify_seal(bundle)


@pytest.mark.parametrize("alias_kind", ["symlink", "junction"])
def test_ordinary_alias_and_active_real_owned_paths_still_allow_writes(tmp_path, alias_kind):
    ordinary = tmp_path / "ordinary"
    ordinary.mkdir()
    alias = tmp_path / "alias"
    _alias(alias, ordinary, alias_kind)
    write_json(alias / "record.json", {"n": 1})
    write_json(alias / "record.json", {"n": 2}, overwrite=True)
    assert json.loads((ordinary / "record.json").read_text()) == {"n": 2}
    active = tmp_path / "test-results" / "active"
    active.mkdir(parents=True)
    with execution_scope():
        own_run(active)
        write_json(active / "record.json", {"n": 1})
        write_json(active / "record.json", {"n": 2}, overwrite=True)
        append_jsonl(active / "events.jsonl", [{"n": 1}])
        append_jsonl(active / "events.jsonl", [{"n": 2}])
    assert json.loads((active / "record.json").read_text()) == {"n": 2}
    assert (active / "events.jsonl").read_text() == '{"n":1}\n{"n":2}\n'


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("protection", PROTECTIONS)
@pytest.mark.parametrize("alias_kind", ["symlink", "junction"])
def test_intermediate_history_ancestor_survives_two_aliases(tmp_path, kind, protection, alias_kind):
    # Checking only lexical and fully resolved endpoints misses the protected middle.
    protected = _protected(tmp_path, protection)
    outside = tmp_path / "outside"
    outside.mkdir()
    target = tmp_path / "target"
    target.mkdir()
    original = target / f"old.{kind}"
    original.write_text("historical\n", encoding="utf-8")
    _alias(protected / "out", target, alias_kind)
    _alias(outside / "into", protected, alias_kind)
    destination = outside / "into" / "out" / original.name
    with execution_scope():
        own_run(outside)
        own_run(target)
        with pytest.raises(FileExistsError):
            _write(kind, destination)
    assert original.read_text() == "historical\n"


@pytest.mark.parametrize("alias_kind", ["symlink", "junction"])
def test_bundle_root_alias_is_rejected_by_seal_and_verification(tmp_path, alias_kind):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "record.json").write_text("record", encoding="utf-8")
    alias = tmp_path / "alias"
    _alias(alias, bundle, alias_kind)
    with pytest.raises(ValueError):
        seal_bundle(alias)
    seal_bundle(bundle)
    with pytest.raises(ValueError):
        verify_seal(alias)
    verify_seal(bundle)


def test_verification_rejects_alias_of_seal_marker(tmp_path):
    # Skipping the seal entry before checking its type trusts an external seal.
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    external = tmp_path / "external-seal.json"
    external.write_text('{"schema_version":"m1-seal-v1","files":{}}', encoding="utf-8")
    _alias(bundle / "FINALIZED.json", external, "symlink", directory=False)
    with pytest.raises(ValueError):
        verify_seal(bundle)
    assert external.read_text() == '{"schema_version":"m1-seal-v1","files":{}}'


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("protection", PROTECTIONS)
@pytest.mark.parametrize("alias_kind", ["symlink", "junction"])
@pytest.mark.parametrize("direction", ["into", "out"])
def test_historical_alias_rejects_creation_before_mkdir(
    tmp_path, kind, protection, alias_kind, direction
):
    protected = _protected(tmp_path, protection)
    outside = tmp_path / "outside"
    outside.mkdir()
    alias, target = (
        (outside / "alias", protected) if direction == "into" else (protected / "alias", outside)
    )
    _alias(alias, target, alias_kind)
    with pytest.raises(FileExistsError):
        _write(kind, alias / "missing" / f"new.{kind}")
    assert not (target / "missing").exists()


@pytest.mark.parametrize(
    "namespace", ["test-results-more", "artifacts/reports-more", "data/manifests-more"]
)
def test_protection_uses_whole_path_components(tmp_path, namespace):
    destination = tmp_path / namespace / "ordinary.json"
    write_json(destination, {"n": 1})
    write_json(destination, {"n": 2}, overwrite=True)
    assert json.loads(destination.read_text()) == {"n": 2}
