from pathlib import Path

from typer.testing import CliRunner

from rcqasyn.cli.app import app


def test_dataset_cli_lists_inspects_and_explains_missing_prepare() -> None:
    runner = CliRunner()
    listed = runner.invoke(app, ["datasets", "list", "--root", str(Path.cwd())])
    assert listed.exit_code == 0
    assert "page-blocks0" in listed.stdout and "dev-small" in listed.stdout
    inspected = runner.invoke(app, ["datasets", "inspect", "page-blocks0", "--root", str(Path.cwd())])
    assert inspected.exit_code == 0
    raw_path = Path.cwd() / "data" / "raw" / "page-blocks0" / "page-blocks0.dat"
    if raw_path.is_file():
        assert "Presence: present" in inspected.stdout and "Schema reconciliation: OK" in inspected.stdout
    else:
        assert "Presence: missing" in inspected.stdout and "accepted" in inspected.stdout
    prepared = runner.invoke(app, ["datasets", "prepare", "page-blocks0", "--root", str(Path.cwd())])
    if raw_path.is_file():
        assert prepared.exit_code == 0
    else:
        assert prepared.exit_code == 1
        assert "does not download KEEL" in prepared.stdout or "does not download KEEL" in (prepared.stderr or "")
