from pathlib import Path

import pytest

from rcqasyn.storage import append_jsonl, create_run_dir, read_json, read_jsonl, write_json


def test_json_atomic_and_no_silent_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "artifact.json"
    write_json(path, {"b": 2, "a": 1})
    assert read_json(path) == {"a": 1, "b": 2}
    with pytest.raises(FileExistsError):
        write_json(path, {})
    write_json(path, {"ok": True}, overwrite=True)


def test_jsonl_and_run_directory(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    append_jsonl(path, [{"n": 1}, {"n": 2}])
    assert list(read_jsonl(path)) == [{"n": 1}, {"n": 2}]
    run = create_run_dir(tmp_path / "runs", "run-1")
    assert run.is_dir()
    with pytest.raises(FileExistsError):
        create_run_dir(tmp_path / "runs", "run-1")
