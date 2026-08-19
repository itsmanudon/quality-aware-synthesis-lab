from pathlib import Path

from typer.testing import CliRunner

from rcqasyn.cli.app import app


def test_help_and_index(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "doctor" in result.stdout
    root = tmp_path
    (root / "configs").mkdir()
    (root / "literature" / "papers").mkdir(parents=True)
    (root / "literature" / "notes").mkdir()
    (root / "artifacts").mkdir()
    (root / "configs" / "base.yaml").write_text(
        "project:\n  name: x\n  seed: 1\nartifacts:\n  root: artifacts\nliterature:\n  papers_dir: literature/papers\n  notes_dir: literature/notes\n",
        encoding="utf-8",
    )
    result = CliRunner().invoke(app, ["papers", "index", "--root", str(root)])
    assert result.exit_code == 0
    assert (root / "literature" / "paper_inventory.csv").is_file()
