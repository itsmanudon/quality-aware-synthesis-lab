from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from rcqasyn.experiments.specification import fingerprint
from rcqasyn.storage.artifacts import create_run_dir, read_json, write_json, write_text
from rcqasyn.storage.ownership import file_hash, seal_bundle, verify_seal

from .contracts import FREEZE


def digest(value: Any) -> str:
    return fingerprint(value)


def source_path(root: Path, relative: str) -> Path:
    path = root / relative
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("source locator must be relative and bounded")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("source locator escapes root")
    return path


def jsonl(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if any(not line.strip() for line in lines):
        raise ValueError("blank source lines cannot be assigned implicit occurrence ordinals")
    return [json.loads(line) for line in lines]


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def csv_text(rows: list[dict[str, Any]]) -> str:
    if not rows:
        raise ValueError("CSV export needs a nonempty schema")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, sort_keys=True) if isinstance(v, (dict, list))
                         else v for k, v in row.items()})
    return stream.getvalue()


def snapshot(root: Path, files: list[Path]) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): file_hash(p) for p in sorted(set(files))}


def verify_sources(root: Path, sources: dict[str, str]) -> None:
    for relative, expected in sources.items():
        if file_hash(source_path(root, relative)) != expected:
            raise ValueError(f"source integrity mismatch: {relative}")


def envelope(kind: str, data: dict[str, Any]) -> dict[str, Any]:
    value = {"schema_version": kind, "phase1_freeze_sha": FREEZE,
             "creation_tool": "rcqasyn-phase2-v1", **data}
    return {**value, "fingerprint": digest(value)}


def verify_envelope(value: dict[str, Any], kind: str) -> None:
    if value.get("schema_version") != kind or value.get("phase1_freeze_sha") != FREEZE:
        raise ValueError("unsupported Phase-2 schema or freeze")
    if value.get("fingerprint") != digest({k: v for k, v in value.items()
                                           if k != "fingerprint"}):
        raise ValueError("artifact fingerprint mismatch")


def write_bundle(output: Path, value: dict[str, Any],
                 extras: dict[str, str] | None = None) -> Path:
    """Reserve through M1 guards before any output; seal only this new derivative."""
    if output.exists():
        verify_seal(output)
        if read_json(output / "artifact.json") != value:
            raise FileExistsError("immutable derivative differs; choose a new version")
        for name, text in (extras or {}).items():
            if (output / name).read_text(encoding="utf-8") != text:
                raise ValueError("derivative export mismatch")
        return output
    for name in extras or {}:
        if Path(name).name != name:
            raise ValueError("export name must be a single filename")
    directory = create_run_dir(output.parent, output.name)
    write_json(directory / "artifact.json", value)
    for name, text in (extras or {}).items():
        write_text(directory / name, text)
    seal_bundle(directory)
    return directory


def read_bundle(path: Path) -> dict[str, Any]:
    verify_seal(path)
    return read_json(path / "artifact.json")
