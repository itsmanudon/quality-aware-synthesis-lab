"""Validated new bundles and explicit read-only legacy compatibility."""

from __future__ import annotations

import hashlib
import json
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
    if not isinstance(value, dict):
        raise TypeError("source manifest must be an object")
    schema = value.get("schema_version")
    if schema == "m1-run-v2":
        if value.get("status") != "finalized" or not (path / "FINALIZED.json").is_file():
            raise ValueError(f"incomplete M1 execution: {path}")
        verify_seal(path)
        scientific = read_json(path / "scientific_specification.json")
        comparison = read_json(path / "comparison.json")
        split = read_json(path / "dataset" / "split_manifest.json")
        try:
            _validate_identities(path, value, scientific, comparison, split)
        except (KeyError, TypeError, AttributeError) as error:
            raise ValueError("required artifact identity is missing or invalid") from error
        validate_comparison(comparison)
        if (
            value.get("outcome") != comparison["outcome"]
            or value.get("success") != comparison["outcome"]["success"]
        ):
            raise ValueError("manifest/result outcome mismatch")
    elif schema not in {"m1-run-v1", None} or value.get("status") != "completed":
        raise ValueError(f"legacy bundle requires recorded completed status: {path}")
    return value


def _required_identity(value: dict[str, Any], key: str, artifact: str) -> str:
    identity = value.get(key)
    if not isinstance(identity, str) or not identity.strip():
        raise ValueError(f"required identity {artifact}/{key} is missing or invalid")
    return identity


def _same_identity(expected: Any, observed: Any, label: str) -> None:
    if expected != observed:
        raise ValueError(f"{label} identity mismatch")


def _validate_identities(
    path: Path,
    manifest: dict[str, Any],
    scientific: dict[str, Any],
    comparison: dict[str, Any],
    split: dict[str, Any],
) -> None:
    specification = scientific.get("specification")
    if (
        not isinstance(specification, dict)
        or specification.get("schema_version") != "m1-scientific-spec-v1"
    ):
        raise ValueError("unsupported scientific specification schema identity")
    _same_identity("m1-comparison-v2", comparison.get("schema_version"), "comparison schema")
    for key in (
        "run_id",
        "execution_id",
        "dataset_id",
        "dataset_fingerprint",
        "split_fingerprint",
        "specification_fingerprint",
    ):
        expected = _required_identity(manifest, key, "manifest")
        _same_identity(expected, _required_identity(comparison, key, "comparison"), key)
    _same_identity(manifest["run_id"], manifest["execution_id"], "execution")
    identity = _required_identity(scientific, "fingerprint", "scientific specification")
    _same_identity(fingerprint(specification), identity, "scientific specification")
    _same_identity(identity, manifest["specification_fingerprint"], "scientific specification")
    definition = specification["dataset"]["definition"]
    _same_identity(manifest["dataset_id"], definition.get("dataset_id"), "scientific dataset")
    _same_identity(
        manifest["dataset_id"], specification["dataset_run"].get("dataset_id"), "configured dataset"
    )
    _same_identity(
        manifest["dataset_id"], _required_identity(split, "dataset_id", "split"), "split dataset"
    )
    bound = specification["dataset"]["normalized_fingerprint"]
    _same_identity(bound, manifest["dataset_fingerprint"], "scientific dataset/source")
    _same_identity(
        bound, _required_identity(split, "dataset_fingerprint", "split"), "split dataset/source"
    )
    # The approved split uses its existing JSON serialization, not the compact spec encoding.
    split_hash = hashlib.sha256(
        json.dumps(
            {key: value for key, value in split.items() if key != "split_fingerprint"},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    _same_identity(split_hash, _required_identity(split, "split_fingerprint", "split"), "split")
    _same_identity(split_hash, manifest["split_fingerprint"], "split")
    _same_identity(
        split_hash, comparison.get("metadata", {}).get("split_fingerprint"), "comparison split"
    )
    _same_identity(specification["split_seed"], split.get("split_seed"), "split seed")
    _same_identity(
        specification["dataset_run"]["root_seed"], split.get("root_seed"), "split root seed"
    )
    _same_identity(
        specification["evaluation"]["classifiers"],
        comparison.get("configured_classifiers"),
        "configured classifiers",
    )
    _same_identity(
        specification["evaluation"].get("result_families"),
        comparison.get("configured_results"),
        "configured result families",
    )
    if "result_families" not in specification["evaluation"]:
        raise ValueError("required configured result family identity is missing")
    profile = read_json(path / "dataset/profile.json")
    plan = read_json(path / "generation_plan.json")
    for artifact, record in (("profile", profile), ("generation plan", plan)):
        _same_identity(manifest["dataset_id"], record.get("dataset_id"), f"{artifact} dataset")
    for key in ("dataset_fingerprint", "split_fingerprint"):
        _same_identity(manifest[key], profile.get(key), f"profile {key}")
    _same_identity(
        split.get("train_indices"), profile.get("train_indices"), "profile TRAIN partition"
    )
    for name, baseline in comparison.get("baselines", {}).items():
        for filename, key in (
            ("metrics.json", "intrinsic"),
            ("classifier_metrics.json", "utility"),
        ):
            _same_identity(
                baseline.get(key), read_json(path / "baselines" / name / filename), f"{name} result"
            )
    for relative in (
        "generation_failures.jsonl",
        "provider_calls.jsonl",
        "baselines/b3/judge_results.jsonl",
        "baselines/b3/judge_failures.jsonl",
        "baselines/b3/provider_calls.jsonl",
    ):
        for line in (path / relative).read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                _same_identity(manifest["run_id"], record.get("run_id"), f"{relative} execution")
    # Candidate contracts have no execution field: their identity is scoped by this
    # bundle and their authoritative durable generation call reference.
    for line in (path / "candidates_raw.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            candidate = json.loads(line)
            call_id = candidate.get("metadata", {}).get("provider_call_id")
            if not isinstance(call_id, str) or Path(call_id).name != call_id:
                raise ValueError("required candidate call identity is missing or invalid")
            call_path = path / "calls" / f"{call_id}.json"
            if not call_path.is_file() or read_json(call_path).get("status") != "returned":
                raise ValueError("candidate/durable call identity mismatch")
    for call_path in (path / "calls").glob("*.json"):
        call = read_json(call_path)
        _same_identity(manifest["execution_id"], call.get("execution_id"), "durable call execution")
        _same_identity(call_path.stem, call.get("attempt_id"), "durable call attempt")


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
                "cross_artifact_identity": "legacy_fields_only; new_required_identities_unverified",
            },
        }
    return comparison


def derived_directory(source: Path, purpose: str, output_dir: Path | None = None) -> Path:
    manifest = validate_source(source)
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
            "source_run_id": manifest.get("run_id", source.name),
            "source_execution_id": manifest.get("execution_id"),
            "source_specification_fingerprint": manifest.get("specification_fingerprint"),
            "source_dataset_id": manifest.get("dataset_id"),
            "source_dataset_fingerprint": manifest.get("dataset_fingerprint"),
            "source_split_fingerprint": manifest.get("split_fingerprint"),
            "source_schema_version": manifest.get("schema_version"),
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
