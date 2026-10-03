"""Acquisition, source-identity, and raw-schema records for registered datasets.

The project deliberately does not guess download URLs.  A caller acquires an
official source file out of band and then records the immutable facts about the
file here.  This keeps raw data ignored by Git while making every run auditable.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from rcqasyn.storage.artifacts import write_json

from .loader import LoadedDataset, inspect_keel
from .registry import DatasetDefinition
from .split import SplitManifest


@dataclass(frozen=True)
class AcquisitionRecord:
    dataset_id: str
    exact_source_url: str
    filename: str
    acquired_at_utc: str
    size_bytes: int
    sha256: str
    extracted_filename: str | None = None
    extracted_size_bytes: int | None = None
    extracted_sha256: str | None = None

    @property
    def source_url(self) -> str:
        return self.exact_source_url

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "source_url": self.exact_source_url,
            "exact_source_url": self.exact_source_url,
            "filename": self.filename,
            "acquired_at_utc": self.acquired_at_utc,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "extracted_filename": self.extracted_filename,
            "extracted_size_bytes": self.extracted_size_bytes,
            "extracted_sha256": self.extracted_sha256,
        }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record_acquisition(
    spec: DatasetDefinition,
    path: Path,
    *,
    source_url: str | None = None,
    acquired_at: datetime | None = None,
    archive_path: Path | None = None,
) -> AcquisitionRecord:
    """Build an acquisition record after checking the exact declared filename.

    ``source_url`` is intentionally required when a spec has no authoritative
    URL; otherwise the URL from the spec is used.  No network request occurs.
    """

    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    if spec.accepted_filenames and path.name not in spec.accepted_filenames:
        raise ValueError(f"dataset path must use one of {spec.accepted_filenames}; found {path.name}")
    exact_url = source_url or spec.source_url
    if not exact_url:
        raise ValueError(f"dataset {spec.dataset_id!r} has no authoritative source URL")
    timestamp_value = acquired_at or datetime.now(UTC)
    if timestamp_value.tzinfo is None:
        timestamp_value = timestamp_value.replace(tzinfo=UTC)
    timestamp = timestamp_value.astimezone(UTC).isoformat()
    archive = Path(archive_path) if archive_path else path.with_suffix(".zip")
    if archive == path or not archive.is_file():
        archive = None
    source_path = archive or path
    return AcquisitionRecord(
        dataset_id=spec.dataset_id,
        exact_source_url=exact_url,
        filename=source_path.name,
        acquired_at_utc=timestamp,
        size_bytes=source_path.stat().st_size,
        sha256=sha256_file(source_path),
        extracted_filename=path.name,
        extracted_size_bytes=path.stat().st_size,
        extracted_sha256=sha256_file(path),
    )


def write_acquisition(path: Path, record: AcquisitionRecord, *, overwrite: bool = False) -> None:
    """Write one source manifest atomically, refusing accidental overwrite."""

    from rcqasyn.storage.ownership import assert_writable
    destination = Path(path)
    assert_writable(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        existing = json.loads(destination.read_text(encoding="utf-8"))
        if existing == record.to_dict():
            return
        raise FileExistsError(f"existing acquisition manifest is incompatible: {destination}")
    write_json(destination, record.to_dict())


def inspect_dataset_schema(path: Path, spec: DatasetDefinition) -> dict[str, Any]:
    """Inspect authoritative raw declarations and observed values.

    This report is descriptive: it never turns observed ranges into generation
    constraints and never mutates a dataset specification.
    """

    path = Path(path)
    schema = inspect_keel(path) if path.suffix.lower() == ".dat" else None
    if schema is None:
        raise ValueError("raw schema inspection currently supports KEEL .dat files only")
    frame = schema.frame
    target = spec.target_column
    raw_target = next((column for column in frame.columns if str(column).lower() == target.lower()), None)
    labels = frame[raw_target].astype("string").fillna("<MISSING>") if raw_target else pd.Series(dtype="string")
    counts = {str(label): int(count) for label, count in labels.value_counts().sort_index().items()}
    non_missing = sorted((count for label, count in counts.items() if label != "<MISSING>"))
    minority = min(non_missing) if non_missing else None
    majority = max(non_missing) if non_missing else None
    return {
        "dataset_id": spec.dataset_id,
        "filename": path.name,
        "relation": schema.relation,
        "rows": len(frame),
        "attributes": [attribute.to_dict() for attribute in schema.attributes],
        "inputs": list(schema.inputs),
        "outputs": list(schema.outputs),
        "target_column": target,
        "labels": counts,
        "minority_label": _minority_label(counts),
        "minority_count": minority,
        "majority_label": _majority_label(counts),
        "majority_count": majority,
        "missing_representation": schema.missing_representation,
        "missing_count": int(frame.isna().sum().sum()),
        "types": {attribute.name: attribute.kind for attribute in schema.attributes},
        "declared_columns": [str(column) for column in frame.columns],
    }


def reconcile_schema(path: Path, spec: DatasetDefinition) -> dict[str, Any]:
    """Compare a raw KEEL declaration with a registry spec without changing it."""

    schema = inspect_keel(Path(path))
    declared = [attribute.name for attribute in schema.attributes]
    expected = [*spec.feature_columns, spec.target_column]
    errors: list[str] = []
    if schema.relation and schema.relation.lower() != spec.dataset_id.lower():
        errors.append(f"relation {schema.relation!r} does not identify {spec.dataset_id!r}")
    if [name.lower() for name in declared] != [name.lower() for name in expected]:
        errors.append(f"declared columns {declared!r} do not match spec columns {expected!r}")
    if tuple(schema.inputs) and tuple(name.lower() for name in schema.inputs) != tuple(name.lower() for name in spec.feature_columns):
        errors.append(f"@inputs {schema.inputs!r} do not match spec features {list(spec.feature_columns)!r}")
    if tuple(schema.outputs) and tuple(name.lower() for name in schema.outputs) != (spec.target_column.lower(),):
        errors.append(f"@outputs {schema.outputs!r} do not match spec target {spec.target_column!r}")
    observed_categorical = {
        attribute.name.lower() for attribute in schema.attributes if attribute.kind == "nominal"
    }
    expected_categorical = {name.lower() for name in spec.categorical_columns} | {spec.target_column.lower()}
    if not expected_categorical.issuperset(observed_categorical - {spec.target_column.lower()}):
        errors.append("raw nominal feature declarations disagree with spec categorical columns")
    if errors:
        raise ValueError(f"raw schema/spec mismatch for {spec.dataset_id}: {'; '.join(errors)}")
    return {"status": "ok", "dataset_id": spec.dataset_id, "relation": schema.relation, "columns": declared}


def build_dataset_report(
    dataset: LoadedDataset,
    split: SplitManifest,
    *,
    acquisition: AcquisitionRecord | None = None,
) -> dict[str, Any]:
    """Build the compact machine-readable preparation/TRTR input report."""

    spec = dataset.spec
    labels = dataset.frame[spec.target_column].astype("string").fillna("<MISSING>")
    counts = {str(label): int(count) for label, count in labels.value_counts().sort_index().items()}
    concrete_counts = {label: count for label, count in counts.items() if label != "<MISSING>"}
    min_count = min(concrete_counts.values()) if concrete_counts else None
    max_count = max(concrete_counts.values()) if concrete_counts else None
    return {
        "dataset_id": spec.dataset_id,
        "rows": len(dataset.frame),
        "features": len(spec.feature_columns),
        "numeric": len(spec.numerical_columns),
        "categorical": len(spec.categorical_columns),
        "target": spec.target_column,
        "labels": counts,
        "class_counts": counts,
        "minority_label": str(spec.minority_label) if spec.minority_label is not None else _minority_label(counts),
        "majority_label": _majority_label(counts),
        "minority_count": min_count,
        "majority_count": max_count,
        "imbalance_ratio": (max_count / min_count) if min_count is not None and max_count is not None and min_count > 0 else None,
        "missing_count": int(dataset.missing_count),
        "missing_rates": {str(column): float(series.isna().mean()) for column, series in dataset.frame.items()},
        "dataset_sha256": dataset.fingerprint,
        "archive_sha256": acquisition.sha256 if acquisition else None,
        "extracted_dataset_sha256": acquisition.extracted_sha256 if acquisition else None,
        "split_sha256": split.to_dict()["split_fingerprint"],
        "train_rows": len(split.train_indices),
        "test_rows": len(split.test_indices),
        "acquisition": acquisition.to_dict() if acquisition else None,
    }


def assert_no_test_leakage(dataset: LoadedDataset, split: SplitManifest, profile: Any) -> None:
    """Executable assertions for split partitioning and train-only profile inputs."""

    train = set(split.train_indices)
    test = set(split.test_indices)
    all_indices = set(range(len(dataset.frame)))
    if train & test:
        raise AssertionError("train and test indices overlap")
    if train | test != all_indices:
        raise AssertionError("train and test indices do not cover the dataset")
    if not set(profile.train_indices).issubset(train):
        raise AssertionError("dataset profile contains non-training indices")
    if not set(profile.reference_indices).issubset(train):
        raise AssertionError("reference examples contain non-training indices")


def _minority_label(counts: dict[str, int]) -> str | None:
    concrete = {label: count for label, count in counts.items() if label != "<MISSING>"}
    return min(concrete, key=lambda label: (concrete[label], label)) if concrete else None


def _majority_label(counts: dict[str, int]) -> str | None:
    concrete = {label: count for label, count in counts.items() if label != "<MISSING>"}
    return max(concrete, key=lambda label: (concrete[label], label)) if concrete else None
