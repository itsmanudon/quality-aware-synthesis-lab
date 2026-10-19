from __future__ import annotations

import pytest
from typer.testing import CliRunner

from rcqasyn.cli.app import app
from rcqasyn.phase2.common import csv_text, envelope, read_bundle, write_bundle
from rcqasyn.phase2.workflow import prepare
from rcqasyn.storage.ownership import file_hash


def inventory(root):
    return {str(p.relative_to(root)): file_hash(p) for p in root.rglob("*") if p.is_file()}


def test_immutable_bundle_csv_idempotent_and_changed_output_refused(tmp_path):
    path = tmp_path / "new-bundle"
    value = envelope("fixture-v1", {"value": 1})
    exports = {"table.csv": csv_text([{"text": "first\nsecond", "n": 1}])}
    write_bundle(path, value, exports)
    before = inventory(path)
    assert read_bundle(path) == value
    assert write_bundle(path, value, exports) == path
    assert inventory(path) == before
    with pytest.raises(FileExistsError):
        write_bundle(path, envelope("fixture-v1", {"value": 2}), exports)
    with pytest.raises(FileExistsError):
        write_bundle(path / "forbidden-child", value)
    assert inventory(path) == before


def test_invalid_export_name_denied_without_reservation(tmp_path):
    path = tmp_path / "new-bundle"
    with pytest.raises(ValueError):
        write_bundle(path, envelope("fixture", {}), {"../escape.csv": "bad"})
    assert not path.exists()
    assert not (tmp_path / "escape.csv").exists()


def test_preparation_destination_refused_before_side_effects(tmp_path):
    bad = tmp_path / "artifacts/reports/historical-path"
    with pytest.raises(ValueError, match="version under"):
        prepare(tmp_path, bad)
    assert not bad.exists()
    assert not (tmp_path / "artifacts").exists()


def test_cli_discovery_and_gate_commands_available():
    result = CliRunner().invoke(app, ["phase2", "--help"])
    assert result.exit_code == 0
    for command in ("prepare", "validate", "submit", "batches", "review", "analyze"):
        assert command in result.stdout


@pytest.mark.parametrize("command", ["batches", "submit", "review-export", "review", "analyze"])
def test_future_cli_writes_cannot_target_read_only_source_root(tmp_path, monkeypatch, command):
    from rcqasyn.phase2 import cli
    worktree, source = tmp_path / "worktree", tmp_path / "canonical-source"
    monkeypatch.setattr(cli, "discover_project_root", lambda: worktree)
    forbidden = str(source / "artifacts/reports/phase2/should-not-exist")
    allowed = str(worktree / "artifacts/reports/phase2/output")
    arguments = {
        "batches": ["approval.json", forbidden, allowed],
        "submit": ["approval.json", "answers.json", "agent", "execution", forbidden],
        "review-export": [forbidden, allowed],
        "review": ["approval.json", "decisions.json", forbidden, allowed],
        "analyze": ["approval.json", forbidden, allowed, allowed],
    }[command]
    result = CliRunner().invoke(app, ["phase2", command, *arguments, "--source-root", str(source)])
    assert isinstance(result.exception, ValueError)
    assert "derivative output" in str(result.exception)
    assert not worktree.exists() and not source.exists()
