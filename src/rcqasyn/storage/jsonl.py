from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .ownership import _STAGE_PREFIX, write_scope


def append_jsonl(path: Path, records: Iterable[Any]) -> None:
    """Install a durable appended copy without mutating other hard-link entries."""
    path = Path(path)
    with write_scope(path):
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f"{_STAGE_PREFIX}{path.name}-", dir=path.parent
        )
        try:
            with os.fdopen(descriptor, "wb") as stream:
                try:
                    source = path.open("rb")
                except FileNotFoundError:
                    pass
                else:
                    with source:
                        shutil.copyfileobj(source, stream)
                for record in records:
                    value = record.model_dump(mode="json") if isinstance(record, BaseModel) else record
                    payload = json.dumps(
                        value, ensure_ascii=False, sort_keys=True,
                        separators=(",", ":"), allow_nan=False,
                    )
                    stream.write((payload + "\n").encode("utf-8"))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def read_jsonl(path: Path) -> Iterator[Any]:
    with Path(path).open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSONL at {path}:{line_number}") from error
