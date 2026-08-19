from pathlib import Path

import pytest

from rcqasyn.config import load_config


def test_base_config_resolves_paths() -> None:
    config = load_config()
    assert config.project.seed == 42
    assert config.artifacts.root.is_absolute()
    assert config.literature.papers_dir == (Path.cwd() / "literature/papers").resolve()


def test_config_rejects_boolean_seed(tmp_path: Path) -> None:
    config_file = tmp_path / "base.yaml"
    config_file.write_text(
        "project:\n  name: x\n  seed: true\nartifacts:\n  root: artifacts\nliterature:\n  papers_dir: p\n  notes_dir: n\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_config(config_file, tmp_path)
