"""V1-V3 regressions for staging aliases, alias hops, and hard-link append isolation."""

from __future__ import annotations

import json
import multiprocessing
import os
import subprocess
import threading
from pathlib import Path

import pytest
from pydantic import BaseModel

from rcqasyn.storage.artifacts import write_json, write_text
from rcqasyn.storage.jsonl import append_jsonl, read_jsonl
from rcqasyn.storage.ownership import execution_scope, own_run, seal_bundle, verify_seal

HELPERS = ["json", "yaml", "csv", "text", "jsonl"]
NAMESPACES = ["artifacts/reports", "data/manifests", "test-results"]


def _alias(alias: Path, target: Path, kind: str, *, directory: bool = True) -> None:
    if kind == "junction":
        if os.name != "nt":
            pytest.skip("junctions require Windows")
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(alias), str(target)],
            capture_output=True, text=True, check=False,
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


@pytest.mark.parametrize("alias_kind,directory,dangling", [
    ("symlink", False, False), ("symlink", False, True),
    ("symlink", True, False), ("symlink", True, True),
    ("junction", True, False), ("junction", True, True),
])
@pytest.mark.parametrize("nested", [False, True])
def test_stage_named_alias_is_rejected_before_staging_exclusion(
    tmp_path, alias_kind, directory, dangling, nested
):
    # Excluding the stage prefix before inspecting entry metadata admits these aliases.
    bundle = tmp_path / "bundle"
    container = bundle / "nested" if nested else bundle
    container.mkdir(parents=True)
    outside = tmp_path / "outside"
    if not dangling:
        if directory:
            outside.mkdir()
            (outside / "original.json").write_bytes(b"original")
        else:
            outside.write_bytes(b"original")
    _alias(container / ".rcqasyn-stage-abandoned", outside, alias_kind, directory=directory)
    with pytest.raises(ValueError, match="alias|symlink"):
        seal_bundle(bundle)
    assert not (bundle / "FINALIZED.json").exists()
    if not dangling:
        assert (outside / "original.json" if directory else outside).read_bytes() == b"original"


def test_normal_stage_file_is_excluded_but_stage_directory_alias_is_rejected(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "record.json").write_bytes(b"record")
    (bundle / ".rcqasyn-stage-record-abandoned").write_bytes(b"partial")
    seal_bundle(bundle)
    verify_seal(bundle)
    assert json.loads((bundle / "FINALIZED.json").read_text())["files"].keys() == {"record.json"}
    outside = tmp_path / "outside"
    outside.mkdir()
    _alias(bundle / ".rcqasyn-stage-after-seal", outside, "junction")
    with pytest.raises(ValueError, match="alias"):
        verify_seal(bundle)


@pytest.mark.parametrize("alias_kind", ["symlink", "junction"])
@pytest.mark.parametrize("namespace", NAMESPACES)
@pytest.mark.parametrize("kind", HELPERS)
def test_alias_target_that_is_itself_an_alias_preserves_historical_ancestry(
    tmp_path, alias_kind, namespace, kind
):
    # Resolving entrance/redirect in one step erases artifacts/reports/redirect.
    historical = tmp_path / namespace
    historical.mkdir(parents=True)
    outside = tmp_path / "ordinary"
    outside.mkdir()
    entrance = tmp_path / "entrance"
    entrance.mkdir()
    original = outside / f"old.{kind}"
    original.write_bytes(b"historical\n")
    _alias(historical / "redirect", outside, alias_kind)
    _alias(entrance / "redirect", historical / "redirect", alias_kind)
    with pytest.raises(FileExistsError):
        _write(kind, entrance / "redirect" / original.name)
    assert original.read_bytes() == b"historical\n"


@pytest.mark.parametrize("first,second", [("symlink", "junction"), ("junction", "symlink")])
@pytest.mark.parametrize("claim", ["none", "all", "alias"])
@pytest.mark.parametrize("kind", HELPERS)
def test_mixed_nested_alias_hops_reject_history_even_when_claimed(
    tmp_path, first, second, claim, kind
):
    historical = tmp_path / "artifacts" / "reports" / "nested"
    historical.mkdir(parents=True)
    outside = tmp_path / "ordinary"
    outside.mkdir()
    entrance = tmp_path / "entrance"
    entrance.mkdir()
    _alias(historical / "redirect", outside, second)
    _alias(entrance / "redirect", historical / "redirect", first)
    with execution_scope():
        if claim == "all":
            own_run(historical)
            own_run(outside)
            own_run(entrance)
        elif claim == "alias":
            own_run(entrance / "redirect")
        with pytest.raises(FileExistsError):
            _write(kind, entrance / "redirect" / "missing" / f"new.{kind}")
    assert not (outside / "missing").exists()


@pytest.mark.parametrize("protection", ["finalized", "legacy"])
@pytest.mark.parametrize("direction", ["into", "out"])
@pytest.mark.parametrize("alias_kind", ["symlink", "junction"])
@pytest.mark.parametrize("kind", HELPERS)
def test_intermediate_bundle_markers_reject_alias_writes_in_both_directions(
    tmp_path, protection, direction, alias_kind, kind
):
    historical = tmp_path / "recorded"
    historical.mkdir()
    marker = "FINALIZED.json" if protection == "finalized" else "manifest.json"
    payload = b"{}" if protection == "finalized" else b'{"status":"completed"}'
    (historical / marker).write_bytes(payload)
    outside = tmp_path / "ordinary"
    outside.mkdir()
    entrance = tmp_path / "entrance"
    entrance.mkdir()
    _alias(historical / "redirect", outside, alias_kind)
    _alias(entrance / "redirect", historical / "redirect", alias_kind)
    destination = (
        entrance / "redirect" / f"new.{kind}"
        if direction == "into" else historical / "redirect" / f"new.{kind}"
    )
    with execution_scope():
        own_run(outside)
        with pytest.raises(FileExistsError):
            _write(kind, destination)
    assert not (outside / f"new.{kind}").exists()
    assert (historical / marker).read_bytes() == payload


@pytest.mark.parametrize("alias_kind", ["symlink", "junction"])
def test_alias_cycle_fails_with_destination_context(tmp_path, alias_kind):
    one, two = tmp_path / "one", tmp_path / "two"
    _alias(one, two, alias_kind)
    _alias(two, one, alias_kind)
    destination = one / "record.json"
    with pytest.raises((OSError, RuntimeError, ValueError), match="one|record.json"):
        write_json(destination, {})
    assert not (tmp_path / "record.json").exists()


@pytest.mark.parametrize("alias_kind", ["symlink", "junction"])
@pytest.mark.parametrize("kind", HELPERS)
def test_ordinary_alias_chain_and_real_active_owned_writes_remain_allowed(
    tmp_path, alias_kind, kind
):
    outside = tmp_path / "ordinary"
    outside.mkdir()
    _alias(tmp_path / "second", outside, alias_kind)
    _alias(tmp_path / "first", tmp_path / "second", alias_kind)
    _write(kind, tmp_path / "first" / f"new.{kind}")
    assert (outside / f"new.{kind}").exists()
    active = tmp_path / "test-results" / "active"
    active.mkdir(parents=True)
    with execution_scope():
        own_run(active)
        _write(kind, active / f"new.{kind}")
        _write(kind, active / f"new.{kind}")
    assert (active / f"new.{kind}").exists()


@pytest.mark.parametrize("protection", ["sealed", "standalone", "legacy", "namespace"])
@pytest.mark.parametrize("additional_links", [0, 2])
def test_append_to_outside_hard_link_leaves_original_history_and_seal_unchanged(
    tmp_path, protection, additional_links
):
    # An in-place append modifies every directory entry sharing the old inode.
    bundle = tmp_path / ("artifacts/reports/recorded" if protection == "namespace" else "bundle")
    bundle.mkdir(parents=True)
    original = bundle / "events.jsonl"
    original.write_bytes(b'{"n":1}\n')
    if protection == "legacy":
        (bundle / "manifest.json").write_bytes(b'{"status":"completed"}')
    elif protection == "sealed":
        with execution_scope():
            own_run(bundle)
            write_json(bundle / "manifest.json", {"schema_version": "m1-run-v2"})
            seal_bundle(bundle)
    elif protection == "standalone":
        seal_bundle(bundle)
    outside = tmp_path / "outside.jsonl"
    os.link(original, outside)
    other_links = [tmp_path / f"other-{index}.jsonl" for index in range(additional_links)]
    for link in other_links:
        os.link(original, link)
    seal_before = (bundle / "FINALIZED.json").read_bytes() if protection in {
        "sealed", "standalone"
    } else None
    append_jsonl(outside, [{"n": 2}])
    assert original.read_bytes() == b'{"n":1}\n'
    assert all(link.read_bytes() == b'{"n":1}\n' for link in other_links)
    assert outside.read_bytes() == b'{"n":1}\n{"n":2}\n'
    assert not os.path.samefile(original, outside)
    if seal_before is not None:
        assert (bundle / "FINALIZED.json").read_bytes() == seal_before
        verify_seal(bundle)


@pytest.mark.parametrize("failure", ["iteration", "serialization"])
@pytest.mark.parametrize("existing", [False, True])
def test_failed_append_does_not_install_partial_records(tmp_path, failure, existing):
    path = tmp_path / "events.jsonl"
    if existing:
        path.write_bytes(b'{"n":1}\n')

    def records():
        yield {"n": 2}
        if failure == "iteration":
            raise RuntimeError("iterator failed")
        yield {"bad": float("nan")}

    with pytest.raises((RuntimeError, ValueError)):
        append_jsonl(path, records())
    if existing:
        assert path.read_bytes() == b'{"n":1}\n'
    else:
        assert not path.exists()
    assert not list(tmp_path.glob(".rcqasyn-stage-*"))


def test_active_owned_append_preserves_jsonl_serialization_and_record_order(tmp_path):
    class Record(BaseModel):
        name: str
        n: int

    bundle = tmp_path / "test-results" / "active"
    bundle.mkdir(parents=True)
    with execution_scope():
        own_run(bundle)
        path = bundle / "events.jsonl"
        append_jsonl(path, [Record(name="é", n=1)])
        append_jsonl(path, [{"n": 2, "name": "next"}])
        assert path.read_bytes() == '{"n":1,"name":"é"}\n{"n":2,"name":"next"}\n'.encode()
        assert list(read_jsonl(path)) == [{"n": 1, "name": "é"}, {"n": 2, "name": "next"}]
        seal_bundle(bundle)
    verify_seal(bundle)


def test_staging_directory_does_not_hide_nested_junction(tmp_path):
    bundle = tmp_path / "bundle"
    stage = bundle / ".rcqasyn-stage-directory" / "nested"
    stage.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    _alias(stage / "alias", outside, "junction")
    with pytest.raises(ValueError, match="alias"):
        seal_bundle(bundle)
    assert not (bundle / "FINALIZED.json").exists()


@pytest.mark.parametrize("kind", HELPERS)
def test_relative_alias_chain_preserves_each_historical_hop(tmp_path, kind):
    historical = tmp_path / "artifacts" / "reports"
    historical.mkdir(parents=True)
    outside = tmp_path / "ordinary"
    outside.mkdir()
    entrance = tmp_path / "entrance"
    entrance.mkdir()
    _alias(historical / "redirect", Path("../../ordinary"), "symlink")
    _alias(entrance / "middle", Path("../artifacts/reports/redirect"), "symlink")
    _alias(entrance / "first", Path("middle"), "symlink")
    with pytest.raises(FileExistsError):
        _write(kind, entrance / "first" / f"new.{kind}")
    assert not (outside / f"new.{kind}").exists()


@pytest.mark.parametrize("boundary", ["fsync", "replace"])
def test_append_io_failure_preserves_existing_bytes_and_removes_staging(
    tmp_path, monkeypatch, boundary
):
    from rcqasyn.storage import jsonl

    path = tmp_path / "events.jsonl"
    path.write_bytes(b'{"n":1}\n')

    def fail_io(*args, **kwargs):
        raise OSError(f"{boundary} failed")

    monkeypatch.setattr(jsonl.os, boundary, fail_io)
    with pytest.raises(OSError, match=f"{boundary} failed"):
        append_jsonl(path, [{"n": 2}])
    assert path.read_bytes() == b'{"n":1}\n'
    assert not list(tmp_path.glob(".rcqasyn-stage-*"))


def _namespace_race_worker(action, path, pause, paused, release, started, done, results):
    """Pause after a real helper/seal acquires its directory exclusion."""
    from rcqasyn.storage import artifacts, ownership

    original_replace = artifacts.os.replace
    original_hash = ownership.file_hash

    def wait_for_release():
        paused.set()
        if not release.wait(20):
            raise TimeoutError("namespace race release")

    try:
        started.set()
        if action == "append":
            def records():
                if pause:
                    wait_for_release()
                yield {"n": 2}
            append_jsonl(path / "events.jsonl", records())
        elif action == "overwrite":
            if pause:
                def delayed_replace(*args, **kwargs):
                    wait_for_release()
                    return original_replace(*args, **kwargs)
                artifacts.os.replace = delayed_replace
            write_text(path / "record.txt", "installed\n", overwrite=True)
        else:
            if pause:
                def delayed_hash(file):
                    wait_for_release()
                    return original_hash(file)
                ownership.file_hash = delayed_hash
            seal_bundle(path)
        results.put((action, "ok"))
    except (OSError, ValueError, RuntimeError) as error:
        results.put((action, type(error).__name__))
    finally:
        artifacts.os.replace = original_replace
        ownership.file_hash = original_hash
        done.set()


@pytest.mark.skipif(os.name != "nt", reason="Windows namespace prefixes require Windows")
@pytest.mark.parametrize("concurrency", ["thread", "process"])
@pytest.mark.parametrize("writer_extended", [False, True])
@pytest.mark.parametrize("operation", ["append", "overwrite"])
@pytest.mark.parametrize("first", ["writer", "seal"])
def test_normal_and_extended_namespace_share_helper_seal_exclusion(
    tmp_path, concurrency, writer_extended, operation, first
):
    # Separate namespace lock roots permit installation after the other spelling seals.
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "events.jsonl").write_bytes(b'{"n":1}\n')
    (bundle / "record.txt").write_bytes(b"initial\n")
    extended = Path("\\\\?\\" + str(bundle))
    writer_path, seal_path = (extended, bundle) if writer_extended else (bundle, extended)
    if concurrency == "process":
        context = multiprocessing.get_context("spawn")
        worker, event, queue = context.Process, context.Event, context.Queue
    else:
        import queue as queues
        worker, event, queue = threading.Thread, threading.Event, queues.Queue
    paused, release, started1, started2, done1, done2 = [event() for _ in range(6)]
    results = queue()
    actions = [(operation, writer_path), ("seal", seal_path)]
    if first == "seal":
        actions.reverse()
    one = worker(target=_namespace_race_worker, args=(
        *actions[0], True, paused, release, started1, done1, results,
    ))
    two = worker(target=_namespace_race_worker, args=(
        *actions[1], False, paused, release, started2, done2, results,
    ))
    one.start()
    try:
        assert paused.wait(15), "first operation did not reach its protected filesystem boundary"
        two.start()
        assert started2.wait(15), "second operation did not start"
        completed_while_paused = done2.wait(0.3)
    finally:
        release.set()
        one.join(25)
        if two.ident is not None:
            two.join(25)
    assert not one.is_alive() and not two.is_alive()
    assert not completed_while_paused, "normal and extended namespace operations overlapped"
    outcomes = dict(results.get(timeout=5) for _ in range(2))
    assert outcomes[actions[0][0]] == "ok"
    assert outcomes[actions[1][0]] == ("FileExistsError" if first == "seal" else "ok")
    verify_seal(bundle)
    verify_seal(extended)
    if first == "seal":
        assert (bundle / "events.jsonl").read_bytes() == b'{"n":1}\n'
        assert (bundle / "record.txt").read_bytes() == b"initial\n"
    elif operation == "append":
        assert (bundle / "events.jsonl").read_bytes() == b'{"n":1}\n{"n":2}\n'
    else:
        assert (bundle / "record.txt").read_bytes() == b"installed\n"
    assert not list(bundle.glob(".rcqasyn-stage-*"))


@pytest.mark.skipif(os.name != "nt", reason="Windows namespace prefixes require Windows")
@pytest.mark.parametrize("writer_extended", [False, True])
def test_cross_namespace_reentrant_seal_rejects_active_append(tmp_path, writer_extended):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    extended = Path("\\\\?\\" + str(bundle))
    writer_path, seal_path = (extended, bundle) if writer_extended else (bundle, extended)

    def records():
        seal_bundle(seal_path)
        yield {"n": 1}

    with pytest.raises(RuntimeError, match="active helper write"):
        append_jsonl(writer_path / "events.jsonl", records())
    assert not (bundle / "FINALIZED.json").exists()
    assert not (bundle / "events.jsonl").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows namespace prefixes require Windows")
@pytest.mark.parametrize("prefix", ["\\\\?\\", "\\??\\"])
@pytest.mark.parametrize("unc", [False, True])
def test_namespace_identity_normalizes_drive_and_unc_roots_without_io(prefix, unc):
    from rcqasyn.storage.ownership import _normalize_namespace

    ordinary = Path("\\\\server\\share\\bundle" if unc else "C:\\bundle")
    extended = Path(prefix + ("UNC\\server\\share\\bundle" if unc else "C:\\bundle"))
    normalized = _normalize_namespace(extended)
    assert normalized == ordinary
    assert normalized.anchor == ordinary.anchor
    assert list(normalized.parents) == list(ordinary.parents)


@pytest.mark.skipif(os.name != "nt", reason="Windows namespace prefixes require Windows")
@pytest.mark.parametrize("owned_extended", [False, True])
def test_active_ownership_accepts_both_namespace_spellings(tmp_path, owned_extended):
    bundle = tmp_path / "test-results" / "active"
    bundle.mkdir(parents=True)
    extended = Path("\\\\?\\" + str(bundle))
    owned_path, writer_path = (extended, bundle) if owned_extended else (bundle, extended)
    with execution_scope():
        own_run(owned_path)
        write_json(writer_path / "manifest.json", {
            "schema_version": "m1-run-v2", "status": "running",
        })
        append_jsonl(writer_path / "events.jsonl", [{"n": 1}])
        append_jsonl(writer_path / "events.jsonl", [{"n": 2}])
        seal_bundle(owned_path)
    assert (bundle / "events.jsonl").read_bytes() == b'{"n":1}\n{"n":2}\n'
    verify_seal(writer_path)
