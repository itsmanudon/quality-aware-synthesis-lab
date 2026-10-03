"""Execution ownership and immutable bundle seals."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

_owned: ContextVar[list[Path] | None] = ContextVar("m1_owned_run", default=None)


@contextmanager
def execution_scope() -> Iterator[list[Path]]:
    paths: list[Path] = []
    token = _owned.set(paths)
    try:
        yield paths
    finally:
        _owned.reset(token)


def own_run(path: Path) -> None:
    paths = _owned.get()
    if paths is None:
        raise RuntimeError("execution ownership scope required")
    paths.append(path.resolve())


def assert_writable(path: Path) -> None:
    destination = path.resolve()
    owned = _owned.get() or []
    for parent in (destination.parent, *destination.parents):
        if (parent / "FINALIZED.json").exists():
            raise FileExistsError(f"immutable finalized bundle: {parent}")
        manifest = parent / "manifest.json"
        if manifest.is_file():
            try:
                value = json.loads(manifest.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                raise FileExistsError(f"unreadable historical manifest: {manifest}") from None
            if str(value.get("schema_version", "")).startswith("m1-run-") and parent not in owned:
                raise FileExistsError(f"historical/foreign execution is immutable: {parent}")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seal_bundle(path: Path) -> None:
    from .artifacts import write_json

    hashes = {
        file.relative_to(path).as_posix(): file_hash(file)
        for file in sorted(path.rglob("*"))
        if file.is_file()
    }
    write_json(path / "FINALIZED.json", {"schema_version": "m1-seal-v1", "files": hashes})


def verify_seal(path: Path) -> None:
    seal = json.loads((path / "FINALIZED.json").read_text(encoding="utf-8"))
    expected = seal["files"]
    actual = {
        file.relative_to(path).as_posix(): file_hash(file)
        for file in path.rglob("*")
        if file.is_file() and file.name != "FINALIZED.json"
    }
    if actual != expected:
        raise ValueError(f"bundle integrity mismatch: {path}")


def is_owned(path: Path) -> bool:
    return path.resolve() in (_owned.get() or [])
