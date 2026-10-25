from __future__ import annotations

import hashlib

import pytest

from rcqasyn.phase2 import empirical_outputs, workflow
from rcqasyn.phase2.common import envelope
from rcqasyn.storage.ownership import file_hash


@pytest.fixture
def source(tmp_path, monkeypatch):
    root = tmp_path / "source"
    original = root / "data/original.csv"
    original.parent.mkdir(parents=True)
    original.write_bytes(b"frozen\n")
    inventory = envelope("historical-integrity-v1", {
        "source_files": workflow.historical_inventory(root), "file_count": 1})
    relative = "artifacts/reports/empirical-v2/run-v2/result.json"
    output = root / relative
    output.parent.mkdir(parents=True)
    output.write_bytes(b'{"approved":true}\r\n')
    configuration = "configs/empirical/protocol-v1.json"
    config = root / configuration
    config.parent.mkdir(parents=True)
    config.write_bytes(b'{"seed":13}\r\n')
    monkeypatch.setattr(empirical_outputs, "EMPIRICAL_RAW_FILES", {relative: file_hash(output)})
    monkeypatch.setattr(empirical_outputs, "EMPIRICAL_TEXT_CONFIGURATIONS", {
        configuration: hashlib.sha256(b'{"seed":13}\n').hexdigest()})
    return root, inventory, output, config


def test_approved_empirical_outputs_preserve_original_inventory(source):
    root, inventory, _, _ = source
    workflow.validate_historical_inventory(root, inventory)
    assert workflow.historical_inventory(root) == inventory["source_files"]


@pytest.mark.parametrize("target", ["output", "configuration", "original"])
def test_tampered_release_or_original_source_is_rejected(source, target):
    root, inventory, output, config = source
    path = {"output": output, "configuration": config, "original": root/"data/original.csv"}[target]
    path.write_bytes(b"tampered\n")
    with pytest.raises(ValueError, match="integrity mismatch|configuration changed"):
        workflow.validate_historical_inventory(root, inventory)


def test_missing_registered_output_is_rejected(source):
    root, inventory, output, _ = source
    output.unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        workflow.validate_historical_inventory(root, inventory)


@pytest.mark.parametrize("relative", ["artifacts/reports/empirical-v2/unknown.txt",
                                      "configs/empirical/unapproved.json"])
def test_unknown_files_in_empirical_namespace_still_fail(source, relative):
    root, inventory, _, _ = source
    (root/relative).write_bytes(b"unregistered")
    with pytest.raises(ValueError, match="historical file set"):
        workflow.validate_historical_inventory(root, inventory)


def test_configuration_platform_newlines_do_not_change_semantic_identity(source):
    root, inventory, _, config = source
    config.write_bytes(b'{"seed":13}\n')
    workflow.validate_historical_inventory(root, inventory)


def test_registered_raw_output_line_endings_remain_strict(source):
    root, inventory, output, _ = source
    output.write_bytes(b'{"approved":true}\n')
    with pytest.raises(ValueError, match="output integrity mismatch"):
        workflow.validate_historical_inventory(root, inventory)
