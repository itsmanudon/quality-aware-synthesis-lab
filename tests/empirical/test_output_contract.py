from pathlib import Path

import pytest

from rcqasyn.empirical.study import Study


def test_versioned_output_refuses_overwrite(tmp_path):
    with pytest.raises(FileExistsError, match="fresh"):
        Study(Path.cwd(), Path.cwd(), tmp_path)


def test_foreign_source_revision_refused_before_loading(monkeypatch, tmp_path):
    monkeypatch.setattr("rcqasyn.empirical.study.subprocess.check_output", lambda *a, **k: "foreign-sha")
    with pytest.raises(ValueError, match="frozen base"):
        Study(Path.cwd(), Path.cwd(), tmp_path/"new")
