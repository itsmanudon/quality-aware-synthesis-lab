"""Storage remediation: helper writes and finalization are one exclusion domain."""

from __future__ import annotations

import json
import multiprocessing
import threading
from pathlib import Path

import pytest

from rcqasyn.storage.artifacts import create_run_dir, write_json, write_text
from rcqasyn.storage.jsonl import append_jsonl
from rcqasyn.storage.ownership import execution_scope, own_run, seal_bundle, verify_seal


def _write(kind: str, path: Path) -> None:
    if kind == "json":
        write_json(path, {"changed": True}, overwrite=True)
    elif kind == "jsonl":
        append_jsonl(path, [{"changed": True}])
    else:
        write_text(path, "changed\n", overwrite=True)


@pytest.mark.parametrize("kind", ["json", "jsonl", "csv", "yaml"])
@pytest.mark.parametrize("manifest", ["legacy", "sealed", "foreign"])
def test_helpers_protect_recorded_bundles(tmp_path, kind, manifest):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    value = {"status": "completed"} if manifest == "legacy" else {
        "schema_version": "m1-run-v2", "status": "running"
    }
    (bundle / "manifest.json").write_text(json.dumps(value), encoding="utf-8")
    destination = bundle / "nested" / f"old.{kind}"
    destination.parent.mkdir()
    destination.write_text("historical\n", encoding="utf-8")
    if manifest == "sealed":
        # Record the seal as a fixture: foreign manifests cannot be modified by helpers.
        (bundle / "FINALIZED.json").write_text("{}", encoding="utf-8")
    before = {p.relative_to(bundle): p.read_bytes() for p in bundle.rglob("*") if p.is_file()}
    with pytest.raises(FileExistsError):
        _write(kind, destination)
    with pytest.raises(FileExistsError):
        _write(kind, bundle / "missing" / f"new.{kind}")
    assert not (bundle / "missing").exists()
    assert before == {p.relative_to(bundle): p.read_bytes() for p in bundle.rglob("*") if p.is_file()}


@pytest.mark.parametrize("namespace", ["artifacts/reports", "artifacts/manifests", "data/manifests", "test-history", "artifacts/derived"])
@pytest.mark.parametrize("kind", ["json", "jsonl", "csv", "yaml"])
def test_public_overwrite_and_append_cannot_replace_protected_history(tmp_path, namespace, kind):
    destination = tmp_path / namespace / "nested" / f"old.{kind}"
    destination.parent.mkdir(parents=True)
    destination.write_text("historical\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        _write(kind, destination)
    assert destination.read_text(encoding="utf-8") == "historical\n"


@pytest.mark.parametrize("schema", [None, "m1-run-v1"])
def test_owned_active_namespace_allows_updates_but_completed_legacy_does_not(tmp_path, schema):
    bundle = tmp_path / "artifacts" / "derived" / "active"
    bundle.mkdir(parents=True)
    with execution_scope():
        own_run(bundle)
        write_json(bundle / "manifest.json", {"schema_version": "m1-run-v2", "status": "running"})
        write_json(bundle / "state.json", {"old": True})
        write_json(bundle / "state.json", {"new": True}, overwrite=True)
        append_jsonl(bundle / "events.jsonl", [{"n": 1}])
        append_jsonl(bundle / "events.jsonl", [{"n": 2}])
        assert json.loads((bundle / "state.json").read_text()) == {"new": True}
        assert len((bundle / "events.jsonl").read_text().splitlines()) == 2
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "manifest.json").write_text(
        json.dumps({"schema_version": schema, "status": "completed"}), encoding="utf-8"
    )
    with execution_scope():
        own_run(legacy)
        with pytest.raises(FileExistsError):
            write_json(legacy / "new.json", {})


def test_arbitrary_nonhistorical_overwrite_and_append_remain_supported(tmp_path):
    path = tmp_path / "ordinary.json"
    write_json(path, {"old": True})
    write_json(path, {"new": True}, overwrite=True)
    assert json.loads(path.read_text()) == {"new": True}
    events = tmp_path / "ordinary.jsonl"
    append_jsonl(events, [{"n": 1}])
    append_jsonl(events, [{"n": 2}])
    assert len(events.read_text().splitlines()) == 2


def _race_worker(operation, bundle, paused, release, started, done, results):
    """Pause a real filesystem boundary, usable by both spawn processes and threads."""
    from rcqasyn.storage import artifacts, ownership

    original_link = artifacts.os.link
    original_hash = ownership.file_hash
    try:
        started.set()
        if operation == "text-paused":
            def delayed_link(*args, **kwargs):
                paused.set()
                if not release.wait(15):
                    raise TimeoutError("write release")
                return original_link(*args, **kwargs)
            artifacts.os.link = delayed_link
            write_text(bundle / "nested" / "later.json", "installed\n")
        elif operation == "append-paused":
            def records():
                paused.set()
                if not release.wait(15):
                    raise TimeoutError("append release")
                yield {"n": 1}
            append_jsonl(bundle / "events.jsonl", records())
        elif operation == "seal-paused":
            def delayed_hash(path):
                paused.set()
                if not release.wait(15):
                    raise TimeoutError("seal release")
                return original_hash(path)
            ownership.file_hash = delayed_hash
            seal_bundle(bundle)
        elif operation == "seal":
            seal_bundle(bundle)
        elif operation == "text":
            write_text(bundle / "nested" / "later.json", "installed\n")
        elif operation == "reserve":
            create_run_dir(bundle, "same-run")
        results.put((operation, "ok"))
    except (OSError, ValueError) as error:
        results.put((operation, type(error).__name__))
    finally:
        if operation == "text-paused":
            artifacts.os.link = original_link
        if operation == "seal-paused":
            ownership.file_hash = original_hash
        done.set()


def _race_context(concurrency):
    if concurrency == "process":
        context = multiprocessing.get_context("spawn")
        return context.Process, context.Event, context.Queue
    import queue
    return threading.Thread, threading.Event, queue.Queue


@pytest.mark.parametrize("concurrency", ["thread", "process"])
@pytest.mark.parametrize("first", ["text-paused", "append-paused", "seal-paused"])
def test_sealing_and_writes_are_mutually_exclusive(tmp_path, concurrency, first):
    worker, event, queue = _race_context(concurrency)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    write_json(bundle / "initial.json", {"initial": True})
    paused, release, started1, started2, done1, done2 = [event() for _ in range(6)]
    results = queue()
    second = "text" if first == "seal-paused" else "seal"
    one = worker(target=_race_worker, args=(first, bundle, paused, release, started1, done1, results))
    two = worker(target=_race_worker, args=(second, bundle, paused, release, started2, done2, results))
    one.start()
    try:
        assert paused.wait(10), "first worker did not reach filesystem boundary"
        two.start()
        assert started2.wait(10), "second worker did not start"
        completed_while_paused = done2.wait(0.3)
    finally:
        release.set()
        one.join(15)
        if two.ident is not None:
            two.join(15)
    assert not one.is_alive() and not two.is_alive()
    assert not completed_while_paused, "seal and writer overlapped their filesystem operations"
    outcomes = dict(results.get(timeout=5) for _ in range(2))
    assert outcomes[first] == "ok"
    assert outcomes[second] == ("FileExistsError" if first == "seal-paused" else "ok")
    verify_seal(bundle)
    inventory = json.loads((bundle / "FINALIZED.json").read_text())["files"]
    assert not any(part.startswith(".rcqasyn-stage-") for name in inventory for part in Path(name).parts)
    if first == "seal-paused":
        assert not (bundle / "nested").exists()
    elif first == "text-paused":
        assert (bundle / "nested" / "later.json").read_text() == "installed\n"
    else:
        assert (bundle / "events.jsonl").read_text() == '{"n":1}\n'


@pytest.mark.parametrize("concurrency", ["thread", "process"])
@pytest.mark.parametrize("operation", ["seal", "reserve"])
def test_competing_seals_and_run_reservations_have_exactly_one_winner(tmp_path, concurrency, operation):
    worker, event, queue = _race_context(concurrency)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    write_json(bundle / "initial.json", {"initial": True})
    results = queue()
    workers = [worker(target=_race_worker, args=(operation, bundle, event(), event(), event(), event(), results)) for _ in range(2)]
    for item in workers:
        item.start()
    for item in workers:
        item.join(15)
    assert not any(item.is_alive() for item in workers)
    assert sorted(results.get(timeout=5)[1] for _ in workers) == ["FileExistsError", "ok"]
    if operation == "seal":
        verify_seal(bundle)


def test_seal_excludes_abandoned_writer_staging_files(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    write_json(bundle / "record.json", {"n": 1})
    (bundle / ".rcqasyn-stage-record.json-abandoned").write_text("partial", encoding="utf-8")
    seal_bundle(bundle)
    assert set(json.loads((bundle / "FINALIZED.json").read_text())["files"]) == {"record.json"}
    verify_seal(bundle)


@pytest.mark.parametrize("schema", [None, "m1-seal-v99"])
def test_seal_verification_rejects_missing_or_unknown_schema(tmp_path, schema):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    seal = {"files": {}}
    if schema is not None:
        seal["schema_version"] = schema
    (bundle / "FINALIZED.json").write_text(json.dumps(seal), encoding="utf-8")
    with pytest.raises(ValueError, match="seal schema"):
        verify_seal(bundle)


def test_append_iterator_cannot_reentrantly_seal_its_active_bundle(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()

    def records():
        seal_bundle(bundle)
        yield {"n": 1}

    with pytest.raises(RuntimeError, match="active helper write"):
        append_jsonl(bundle / "events.jsonl", records())
    assert not (bundle / "FINALIZED.json").exists()
    # An aborted writer releases all locks, so a later normal seal still succeeds.
    seal_bundle(bundle)
    verify_seal(bundle)


@pytest.mark.parametrize("namespace", ["artifacts/reports", "artifacts/manifests", "data/manifests", "test-history", "artifacts/derived"])
@pytest.mark.parametrize("kind", ["json", "jsonl", "csv", "yaml"])
def test_claiming_existing_namespace_does_not_make_historical_files_writable(tmp_path, namespace, kind):
    directory = tmp_path / namespace / "recorded"
    directory.mkdir(parents=True)
    old = directory / f"old.{kind}"
    old.write_text("historical\n", encoding="utf-8")
    with execution_scope():
        own_run(directory)
        with pytest.raises(FileExistsError):
            _write(kind, old)
        # Newly created files in the same active ownership may still transition.
        fresh = directory / "new.json"
        write_json(fresh, {"n": 1})
        write_json(fresh, {"n": 2}, overwrite=True)
        assert json.loads(fresh.read_text()) == {"n": 2}
    assert old.read_text(encoding="utf-8") == "historical\n"


def test_claiming_foreign_active_run_does_not_make_its_manifest_writable(tmp_path):
    bundle = tmp_path / "runs" / "foreign"
    bundle.mkdir(parents=True)
    (bundle / "manifest.json").write_text(
        '{"schema_version":"m1-run-v2","status":"running"}', encoding="utf-8"
    )
    with execution_scope():
        own_run(bundle)
        with pytest.raises(FileExistsError):
            write_json(bundle / "manifest.json", {"status": "changed"}, overwrite=True)
        with pytest.raises(FileExistsError):
            write_json(bundle / "new.json", {})


def test_protected_acquisition_reuse_is_read_only_and_changed_record_is_rejected(tmp_path):
    from dataclasses import replace

    from rcqasyn.datasets.acquisition import AcquisitionRecord, write_acquisition

    path = tmp_path / "data" / "manifests" / "fixture" / "source.json"
    record = AcquisitionRecord(
        dataset_id="fixture", exact_source_url="https://example.test/source.csv",
        filename="source.csv", acquired_at_utc="2026-10-03T00:00:00Z",
        size_bytes=12, sha256="a" * 64,
    )
    write_acquisition(path, record)
    before = path.read_bytes(), path.stat().st_mtime_ns
    write_acquisition(path, record, overwrite=True)
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before
    with pytest.raises(FileExistsError):
        write_acquisition(path, replace(record, size_bytes=13), overwrite=True)
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


@pytest.mark.parametrize("kind", ["json", "jsonl", "csv", "yaml"])
@pytest.mark.parametrize("protection", ["sealed", "namespace"])
@pytest.mark.parametrize("real_symlink", [False, True])
def test_file_alias_cannot_bypass_entry_history_guard(tmp_path, monkeypatch, kind, protection, real_symlink):
    import os

    bundle = tmp_path / ("artifacts/reports/recorded" if protection == "namespace" else "sealed")
    bundle.mkdir(parents=True)
    if protection == "sealed":
        (bundle / "FINALIZED.json").write_text("{}", encoding="utf-8")
    target = tmp_path / "ordinary.json"
    target.write_text("historical\n", encoding="utf-8")
    destination = bundle / f"alias.{kind}"
    if real_symlink:
        try:
            destination.symlink_to(target)
        except OSError as error:
            if os.name == "nt" and error.winerror in {5, 1314}:
                pytest.skip("Windows denied disposable symlink creation")
            raise
    else:
        destination.write_text("historical\n", encoding="utf-8")
        original_resolve = Path.resolve

        def resolve_alias(self, *args, **kwargs):
            return target if self == destination else original_resolve(self, *args, **kwargs)

        monkeypatch.setattr(Path, "resolve", resolve_alias)
    with pytest.raises(FileExistsError):
        _write(kind, destination)
    assert destination.read_text(encoding="utf-8") == "historical\n"
    assert target.read_text(encoding="utf-8") == "historical\n"


@pytest.mark.parametrize("real_symlink", [False, True])
def test_seal_rejects_external_file_alias(tmp_path, monkeypatch, real_symlink):
    import os

    bundle = tmp_path / "bundle"
    bundle.mkdir()
    target = tmp_path / "external.json"
    target.write_text("external", encoding="utf-8")
    alias = bundle / "alias.json"
    if real_symlink:
        try:
            alias.symlink_to(target)
        except OSError as error:
            if os.name == "nt" and error.winerror in {5, 1314}:
                pytest.skip("Windows denied disposable symlink creation")
            raise
    else:
        alias.write_text("external", encoding="utf-8")
        original_resolve = Path.resolve
        original_is_symlink = Path.is_symlink
        monkeypatch.setattr(Path, "resolve", lambda self, *a, **kw: target if self == alias else original_resolve(self, *a, **kw))
        monkeypatch.setattr(Path, "is_symlink", lambda self: self == alias or original_is_symlink(self))
    with pytest.raises(ValueError, match="external file symlink"):
        seal_bundle(bundle)
    assert not (bundle / "FINALIZED.json").exists()


@pytest.mark.parametrize("link_type", ["dangling_file", "external_directory"])
def test_seal_rejects_external_symlink_even_when_not_a_regular_file(tmp_path, link_type):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    target = tmp_path / "external"
    if link_type == "external_directory":
        target.mkdir()
        (target / "record.json").write_text("outside", encoding="utf-8")
    (bundle / "outside-link").symlink_to(target, target_is_directory=link_type == "external_directory")
    with pytest.raises(ValueError, match="external.*symlink"):
        seal_bundle(bundle)
    assert not (bundle / "FINALIZED.json").exists()
