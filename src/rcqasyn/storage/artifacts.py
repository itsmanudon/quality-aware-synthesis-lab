from __future__ import annotations

import io
import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .ownership import _STAGE_PREFIX, write_scope


def _jsonable(value: Any) -> Any:
    return value.model_dump(mode="json") if isinstance(value, BaseModel) else value


def write_text(path: Path, payload: str, *, overwrite: bool = False) -> None:
    """Durable atomic write; immutable creation uses atomic exclusive hard-linking."""
    path = Path(path)
    with write_scope(path):
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f"{_STAGE_PREFIX}{path.name}-", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            if overwrite:
                os.replace(temporary, path)
            else:
                os.link(temporary, path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def write_json(path: Path, value: Any, *, overwrite: bool = False) -> None:
    payload = (
        json.dumps(
            _jsonable(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    )
    write_text(path, payload, overwrite=overwrite)


def read_json(path: Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as stream:
        return json.load(stream)


def create_run_dir(root: Path, run_id: str, *, exist_ok: bool = False) -> Path:
    if not run_id or Path(run_id).name != run_id or run_id in {".", ".."}:
        raise ValueError("run_id must be a non-empty single directory name")
    root = Path(root)
    destination = root / run_id
    with write_scope(destination / "manifest.json"):
        root.mkdir(parents=True, exist_ok=True)
        destination.mkdir(exist_ok=exist_ok)
    return destination


write_json_atomic = write_json
create_safe_run_directory = create_run_dir


@contextmanager
def immutable_text_stream(path: Path) -> Iterator[io.StringIO]:
    stream = io.StringIO(newline="")
    yield stream
    write_text(path, stream.getvalue())
