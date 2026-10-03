"""Validated new bundles and explicit read-only legacy compatibility."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from rcqasyn.contracts.m1 import validate_comparison
from rcqasyn.storage.artifacts import create_run_dir, read_json, write_json
from rcqasyn.storage.ownership import assert_writable, file_hash, verify_seal

from .specification import fingerprint


def validate_source(path: Path, *, allow_active: bool = False) -> dict[str, Any]:
    from rcqasyn.storage.ownership import is_owned

    value = read_json(path / "manifest.json")
    if allow_active and is_owned(path):
        return value
    schema = value.get("schema_version")
    if schema == "m1-run-v2":
        if value.get("status") != "finalized" or not (path / "FINALIZED.json").is_file():
            raise ValueError(f"incomplete M1 execution: {path}")
        verify_seal(path)
        scientific = read_json(path / "scientific_specification.json")
        if fingerprint(scientific["specification"]) != scientific["fingerprint"] or scientific[
            "fingerprint"
        ] != value.get("specification_fingerprint"):
            raise ValueError("scientific specification identity mismatch")
        comparison = read_json(path / "comparison.json")
        if (
            comparison.get("run_id") != value.get("run_id")
            or value.get("execution_id") != value.get("run_id")
            or comparison.get("specification_fingerprint") != scientific["fingerprint"]
        ):
            raise ValueError("execution identity mismatch")
        validate_comparison(comparison)
        split = read_json(path / "dataset" / "split_manifest.json")
        bound = scientific["specification"]["dataset"]["normalized_fingerprint"]
        if bound != value.get("dataset_fingerprint") or bound != split.get("dataset_fingerprint"):
            raise ValueError("scientific dataset/source identity mismatch")
        if (
            value.get("outcome") != comparison["outcome"]
            or value.get("success") != comparison["outcome"]["success"]
        ):
            raise ValueError("manifest/result outcome mismatch")
    elif schema not in {"m1-run-v1", None} or value.get("status") != "completed":
        raise ValueError(f"legacy bundle requires recorded completed status: {path}")
    return value


def read_bundle(path: Path) -> dict[str, Any]:
    manifest = validate_source(Path(path))
    comparison = read_json(Path(path) / "comparison.json")
    if manifest.get("schema_version") != "m1-run-v2":
        comparison = {
            **comparison,
            "legacy_compatibility": {
                "lifecycle": "recorded_completed",
                "success_verified": False,
                "schema_validation": "legacy",
                "immutable_seal": False,
            },
        }
    return comparison


def derived_directory(source: Path, purpose: str, output_dir: Path | None = None) -> Path:
    validate_source(source)
    if output_dir is None:
        directory = create_run_dir(
            source.parent.parent / "derived", f"{source.name}-{purpose}-{uuid4().hex}"
        )
    else:
        directory = Path(output_dir).resolve()
        if directory == source.resolve() or source.resolve() in directory.parents:
            raise ValueError("derived output must be outside the historical source bundle")
        assert_writable(directory / "source.json")
        directory.mkdir(parents=True, exist_ok=False)
    write_json(
        directory / "source.json",
        {
            "source_run_id": source.name,
            "completion": "requires_FINALIZED.json",
            "manifest_sha256": file_hash(source / "manifest.json"),
            "comparison_sha256": file_hash(source / "comparison.json")
            if (source / "comparison.json").exists()
            else None,
            "source_files": {
                p.relative_to(source).as_posix(): file_hash(p)
                for p in source.rglob("*")
                if p.is_file()
            },
        },
    )
    return directory
