"""Execution ownership and immutable bundle seals."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import stat
import tempfile
import threading
import time
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

_owned: ContextVar[list[Path] | None] = ContextVar("m1_owned_run", default=None)
_preexisting: ContextVar[dict[Path, set[Path]] | None] = ContextVar(
    "m1_owned_existing", default=None
)
_STAGE_PREFIX = ".rcqasyn-stage-"
_lock_guard = threading.Lock()
_thread_locks: dict[str, Any] = {}
_held = threading.local()
_open_handles: set[int] = set()


def _after_fork() -> None:
    # A child must not inherit its parent's local reentrancy or open flock handles.
    global _lock_guard, _thread_locks, _held, _open_handles
    for descriptor in _open_handles:
        os.close(descriptor)
    _lock_guard = threading.Lock()
    _thread_locks = {}
    _held = threading.local()
    _open_handles = set()


_register_at_fork = getattr(os, "register_at_fork", None)
if _register_at_fork is not None:
    _register_at_fork(after_in_child=_after_fork)


def _lock_file(descriptor: int) -> None:
    if os.name == "nt":
        import msvcrt

        while True:
            try:
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                return
            except OSError as error:
                if error.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                    raise
                time.sleep(0.01)
    else:
        import fcntl

        fcntl.flock(descriptor, fcntl.LOCK_EX)


@contextmanager
def _directory_lock(path: Path) -> Iterator[None]:
    key = os.path.normcase(str(path))
    with _lock_guard:
        local_lock = _thread_locks.setdefault(key, threading.RLock())
    with local_lock:
        held = getattr(_held, "paths", None)
        if held is None:
            held = _held.paths = set()
        if key in held:
            yield
            return
        lock_root = Path(tempfile.gettempdir()) / "rcqasyn-bundle-locks"
        lock_root.mkdir(parents=True, exist_ok=True)
        lock_path = lock_root / (hashlib.sha256(key.encode("utf-8")).hexdigest() + ".lock")
        descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            # Windows byte-range locks need a byte; writing the same byte is harmless.
            if os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b"\0")
            _lock_file(descriptor)
            held.add(key)
            with _lock_guard:
                _open_handles.add(descriptor)
            try:
                yield
            finally:
                held.remove(key)
                with _lock_guard:
                    _open_handles.remove(descriptor)
        finally:
            # Closing releases the OS lock, including after exceptions/process exit.
            os.close(descriptor)


@contextmanager
def bundle_lock(path: Path, *additional_paths: Path) -> Iterator[None]:
    """Serialize helpers with seals of any enclosing directory across processes.

    Ancestors are locked from the filesystem root downward so arbitrary nested
    destinations share the seal's lock even before a manifest exists. Locks live
    in TEMP, never in the bundle. Local reentrancy lets sealing use normal writers.
    """
    directories = {
        identity
        for item in (path, *additional_paths)
        for identity in (Path(item).absolute(), Path(item).resolve())
    }
    ancestors = {parent for directory in directories for parent in (directory, *directory.parents)}
    ordered = sorted(ancestors, key=lambda item: (len(item.parts), os.path.normcase(str(item))))
    held_paths = getattr(_held, "paths", set())
    held_roots = {key for key in held_paths if Path(key).parent == Path(key)}
    new_roots = {
        os.path.normcase(str(item))
        for item in ordered
        if item.parent == item and os.path.normcase(str(item)) not in held_paths
    }
    if held_roots and new_roots and min(new_roots) < max(held_roots):
        raise RuntimeError("nested helper lock order would deadlock")
    with ExitStack() as stack:
        for parent in ordered:
            stack.enter_context(_directory_lock(parent))
        yield


@contextmanager
def write_scope(path: Path) -> Iterator[None]:
    """Hold exclusion through validation, staging, installation and cleanup."""
    path = Path(path)
    destinations = _destination_paths(path)
    with bundle_lock(*(destination.parent for destination in destinations)):
        assert_writable(path)
        writes = getattr(_held, "writes", None)
        if writes is None:
            writes = _held.writes = []
        writes.extend(destinations)
        try:
            yield
        finally:
            del writes[-len(destinations) :]


@contextmanager
def execution_scope() -> Iterator[list[Path]]:
    paths: list[Path] = []
    token = _owned.set(paths)
    existing_token = _preexisting.set({})
    try:
        yield paths
    finally:
        _preexisting.reset(existing_token)
        _owned.reset(token)


def own_run(path: Path) -> None:
    paths = _owned.get()
    existing = _preexisting.get()
    if paths is None or existing is None:
        raise RuntimeError("execution ownership scope required")
    directory = path.resolve()
    with bundle_lock(directory):
        if directory not in existing:
            existing[directory] = {
                identity
                for file in _walk_real_entries(directory)
                if _is_alias(file) or file.is_file()
                for identity in (file.absolute(), file.parent.resolve() / file.name, file.resolve())
            }
            paths.append(directory)


def _is_alias(path: Path) -> bool:
    """Inspect the entry itself, including Windows junction/other reparse tags."""
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    return bool(
        stat.S_ISLNK(metadata.st_mode)
        or getattr(metadata, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        or path.is_symlink()
        or path.is_junction()
    )


def _destination_paths(path: Path) -> tuple[Path, ...]:
    """Keep lexical and physical identities, including intermediate alias ancestors."""
    lexical = path.absolute()
    destinations = {lexical, path.parent.resolve() / path.name, path.resolve()}
    # An outside alias can enter history and a second alias can leave it again.
    # Preserve that intermediate namespace rather than checking only the endpoint.
    for parent in lexical.parents:
        if _is_alias(parent):
            destinations.add(parent.resolve() / lexical.relative_to(parent))
    return tuple(sorted(destinations, key=str))


def assert_writable(path: Path) -> None:
    path = Path(path)
    lexical = path.absolute()
    aliased = any(_is_alias(entry) for entry in (lexical, *lexical.parents))
    for destination in _destination_paths(path):
        _assert_destination_writable(destination, aliased=aliased)


def _assert_destination_writable(destination: Path, *, aliased: bool = False) -> None:
    owned = _owned.get() or []
    existing = _preexisting.get() or {}
    for parent in (destination.parent, *destination.parent.parents):
        if (parent / "FINALIZED.json").exists():
            raise FileExistsError(f"immutable finalized bundle: {parent}")
        manifest = parent / "manifest.json"
        if manifest.is_file():
            try:
                value = json.loads(manifest.read_text(encoding="utf-8"))
                if not isinstance(value, dict):
                    raise TypeError("manifest must be an object")
            except (ValueError, TypeError, OSError):
                raise FileExistsError(f"unreadable historical manifest: {manifest}") from None
            schema = value.get("schema_version")
            if schema in {None, "m1-run-v1"} and value.get("status") == "completed":
                raise FileExistsError(f"immutable completed legacy bundle: {parent}")
            if str(schema).startswith("m1-run-") and (
                parent not in owned or manifest.resolve() in existing.get(parent, set())
            ):
                raise FileExistsError(f"historical/foreign execution is immutable: {parent}")
    parts = tuple(part.casefold() for part in destination.parts)
    protected = bool({"test-history", "test-results"}.intersection(parts)) or any(
        parts[index : index + 2]
        in {
            ("artifacts", "reports"),
            ("artifacts", "derived"),
            ("artifacts", "manifests"),
            ("data", "manifests"),
        }
        for index in range(len(parts) - 1)
    )
    active_owned = not aliased and any(
        parent in destination.parents and destination not in existing.get(parent, {destination})
        for parent in owned
    )
    if protected and (aliased or destination.exists()) and not active_owned:
        raise FileExistsError(f"immutable historical artifact: {destination}")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _walk_real_entries(path: Path, *, exclude_staging: bool = False) -> Iterator[Path]:
    """Walk top down; inspect aliases before deciding whether to visit children."""
    pending = [path]
    while pending:
        directory = pending.pop()
        for entry in sorted(directory.iterdir()):
            if exclude_staging and entry.name.startswith(_STAGE_PREFIX):
                continue
            yield entry
            if not _is_alias(entry) and entry.is_dir():
                pending.append(entry)


def _assert_real_bundle_path(path: Path) -> None:
    lexical = path.absolute()
    if any(_is_alias(entry) for entry in (lexical, *lexical.parents)):
        raise ValueError(f"bundle path contains filesystem alias: {path}")


def _bundle_inventory(path: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    _assert_real_bundle_path(path)
    resolved = path.resolve()
    for file in _walk_real_entries(path, exclude_staging=True):
        relative = file.relative_to(path)
        if _is_alias(file):
            if file.is_symlink():
                location = "internal" if file.resolve().is_relative_to(resolved) else "external"
                kind = "file" if file.is_file() else "directory" if file.is_dir() else "dangling"
                raise ValueError(f"bundle contains {location} {kind} symlink: {file}")
            raise ValueError(f"bundle contains junction or reparse alias: {file}")
        if file == path / "FINALIZED.json":
            continue
        if file.is_file():
            hashes[relative.as_posix()] = file_hash(file)
    return hashes


def seal_bundle(path: Path) -> None:
    from .artifacts import write_json

    path = Path(path).absolute()
    if any(path.resolve() in destination.parents for destination in getattr(_held, "writes", [])):
        raise RuntimeError(f"cannot seal bundle during an active helper write: {path}")
    with bundle_lock(path):
        assert_writable(path / "FINALIZED.json")
        hashes = _bundle_inventory(path)
        write_json(path / "FINALIZED.json", {"schema_version": "m1-seal-v1", "files": hashes})


def verify_seal(path: Path) -> None:
    path = Path(path)
    _assert_real_bundle_path(path)
    if _is_alias(path / "FINALIZED.json"):
        raise ValueError(f"bundle seal contains filesystem alias: {path}")
    seal = json.loads((path / "FINALIZED.json").read_text(encoding="utf-8"))
    if not isinstance(seal, dict) or seal.get("schema_version") != "m1-seal-v1":
        raise ValueError(f"unsupported or missing seal schema: {path}")
    expected = seal.get("files")
    if not isinstance(expected, dict) or any(
        not isinstance(name, str) or not isinstance(digest, str)
        for name, digest in expected.items()
    ):
        raise ValueError(f"invalid seal inventory: {path}")
    actual = _bundle_inventory(path)
    if actual != expected:
        raise ValueError(f"bundle integrity mismatch: {path}")


def is_owned(path: Path) -> bool:
    return path.resolve() in (_owned.get() or [])
