from __future__ import annotations

import json
import os
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .ownership import assert_writable


def append_jsonl(path: Path, records: Iterable[Any]) -> None:
    path = Path(path)
    assert_writable(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        for record in records:
            value = record.model_dump(mode="json") if isinstance(record, BaseModel) else record
            stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())


def read_jsonl(path: Path) -> Iterator[Any]:
    with Path(path).open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSONL at {path}:{line_number}") from error
