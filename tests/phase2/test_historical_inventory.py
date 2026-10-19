from __future__ import annotations

import copy
import json
import shutil

import pytest

from rcqasyn.phase2 import workflow
from rcqasyn.phase2.common import digest, envelope, write_bundle
from rcqasyn.storage.ownership import file_hash


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "source"
    for relative in (
        "data/source.csv",
        "configs/datasets/fixture.json",
        "prompts/generate.txt",
        "artifacts/runs/original/manifest.json",
        "artifacts/reports/p1/report.json",
        "test-results/result.txt",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("original fixture bytes\n", encoding="utf-8")
    assert root.resolve().is_relative_to(tmp_path.resolve())
    inventory = envelope(
        "historical-integrity-v1",
        {"source_files": workflow.historical_inventory(root), "file_count": 6},
    )
    return root, inventory


def register(root, monkeypatch, phase=3, nested=False):
    relative = f"artifacts/reports/phase{phase}/fixture-v1"
    directory = root / relative
    target = directory / "manifest" if nested else directory
    value = envelope("research-fixture-v1", {"phase": phase, "source": "fixture-only"})
    write_bundle(target, value, {"report.md": "# Fixture research output\n"})
    catalog = {
        p.relative_to(directory).as_posix(): file_hash(p) for p in directory.rglob("FINALIZED.json")
    }
    monkeypatch.setattr(
        workflow,
        "RESEARCH_SEAL_CATALOGS",
        {**workflow.RESEARCH_SEAL_CATALOGS, relative: digest(catalog)},
    )
    return directory, target


def test_original_inventory_alone_passes(source):
    root, inventory = source
    workflow.validate_historical_inventory(root, inventory)
    assert workflow.historical_inventory(root) == inventory["source_files"]


@pytest.mark.parametrize("phase", [3, 4, 5, 6])
def test_authorized_versioned_phase_outputs_preserve_original_inventory(source, monkeypatch, phase):
    root, inventory = source
    register(root, monkeypatch, phase)
    workflow.validate_historical_inventory(root, inventory)
    assert workflow.historical_inventory(root) == inventory["source_files"]


def test_missing_original_file_fails_even_with_legitimate_output(source, monkeypatch):
    root, inventory = source
    register(root, monkeypatch)
    (root / "data/source.csv").unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        workflow.validate_historical_inventory(root, inventory)


def test_modified_original_file_fails(source):
    root, inventory = source
    (root / "data/source.csv").write_text("modified\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source integrity mismatch"):
        workflow.validate_historical_inventory(root, inventory)


def test_replacement_at_original_filename_fails(source, tmp_path):
    root, inventory = source
    substitute = tmp_path / "substitute"
    substitute.write_bytes(b"different bytes at the same filename")
    substitute.replace(root / "data/source.csv")
    with pytest.raises(ValueError, match="source integrity mismatch"):
        workflow.validate_historical_inventory(root, inventory)


def test_corrupt_recorded_hash_fails_even_with_recomputed_envelope(source):
    root, inventory = source
    corrupted = copy.deepcopy(inventory["source_files"])
    corrupted["data/source.csv"] = "0" * 64
    value = envelope("historical-integrity-v1", {"source_files": corrupted, "file_count": 6})
    with pytest.raises(ValueError, match="source integrity mismatch"):
        workflow.validate_historical_inventory(root, value)


def test_corrupt_inventory_envelope_or_count_fails(source):
    root, inventory = source
    invalid = {**inventory, "file_count": 1438}
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        workflow.validate_historical_inventory(root, invalid)
    invalid = envelope(
        "historical-integrity-v1", {"file_count": 1438, "source_files": inventory["source_files"]}
    )
    with pytest.raises(ValueError, match="count contradicts"):
        workflow.validate_historical_inventory(root, invalid)


def test_new_registered_report_is_not_rebaselined_as_original(source, monkeypatch):
    root, inventory = source
    original_fingerprint = inventory["fingerprint"]
    register(root, monkeypatch, 3)
    register(root, monkeypatch, 4)
    workflow.validate_historical_inventory(root, inventory)
    assert inventory["fingerprint"] == original_fingerprint and inventory["file_count"] == 6


@pytest.mark.parametrize(
    "relative",
    [
        "data/unknown.csv",
        "artifacts/reports/p1/unknown.json",
        "configs/phase3/unregistered.json",
        "prompts/unknown.txt",
    ],
)
def test_unregistered_original_namespace_additions_fail(source, relative):
    root, inventory = source
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("unregistered", encoding="utf-8")
    with pytest.raises(ValueError, match="historical file set"):
        workflow.validate_historical_inventory(root, inventory)


def test_unregistered_sealed_version_is_rejected(source):
    root, inventory = source
    write_bundle(
        root / "artifacts/reports/phase3/unregistered-v9",
        envelope("research-fixture-v1", {"value": "not registered"}),
    )
    with pytest.raises(ValueError, match="historical file set"):
        workflow.validate_historical_inventory(root, inventory)


def test_unmanifested_file_in_nested_registered_root_remains_visible(source, monkeypatch):
    root, inventory = source
    directory, _ = register(root, monkeypatch, nested=True)
    (directory / "unmanifested.txt").write_text("not sealed", encoding="utf-8")
    with pytest.raises(ValueError, match="historical file set"):
        workflow.validate_historical_inventory(root, inventory)


@pytest.mark.parametrize("name", ["artifact.json", "FINALIZED.json", "report.md"])
def test_tampered_later_manifest_seal_or_export_fails(source, monkeypatch, name):
    root, inventory = source
    _, target = register(root, monkeypatch)
    path = target / name
    path.write_bytes(path.read_bytes() + b"\nchanged")
    with pytest.raises(ValueError, match="catalog changed|integrity mismatch"):
        workflow.validate_historical_inventory(root, inventory)


def test_new_seal_inside_registered_version_is_not_implicitly_registered(source, monkeypatch):
    root, inventory = source
    directory, _ = register(root, monkeypatch, nested=True)
    write_bundle(directory / "unknown-child", envelope("research-fixture-v1", {"new": True}))
    with pytest.raises(ValueError, match="catalog changed"):
        workflow.validate_historical_inventory(root, inventory)


def test_registered_configuration_has_independent_identity(source, monkeypatch):
    root, inventory = source
    relative = "configs/phase3/fixture.json"
    path = root / relative
    path.parent.mkdir(parents=True)
    value = {"schema_version": "fixture-plan-v1", "seed": 42}
    path.write_text(json.dumps(value), encoding="utf-8")
    monkeypatch.setattr(workflow, "RESEARCH_CONFIGURATIONS", {relative: digest(value)})
    workflow.validate_historical_inventory(root, inventory)
    path.write_text(json.dumps({**value, "seed": 99}), encoding="utf-8")
    with pytest.raises(ValueError, match="configuration changed"):
        workflow.validate_historical_inventory(root, inventory)


def test_canonical_source_root_relocation_preserves_relative_identities(source, tmp_path):
    root, inventory = source
    relocated = tmp_path / "relocated-source"
    shutil.copytree(root, relocated)
    workflow.validate_historical_inventory(relocated, inventory)
    assert workflow.historical_inventory(relocated) == inventory["source_files"]
