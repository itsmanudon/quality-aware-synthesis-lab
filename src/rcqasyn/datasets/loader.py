# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportOptionalMemberAccess=false
from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .registry import DatasetDefinition, DatasetRegistry


@dataclass(frozen=True)
class LoadedDataset:
    spec: DatasetDefinition
    path: Path
    frame: pd.DataFrame
    fingerprint: str
    missing_count: int


def load_dataset(spec: DatasetDefinition, registry: DatasetRegistry | None = None) -> LoadedDataset:
    root = registry or DatasetRegistry()
    path = root.resolve_path(spec)
    if not path.exists():
        names = ", ".join(spec.accepted_filenames) or path.name
        raise FileNotFoundError(
            f"dataset {spec.dataset_id!r} is not placed at {path}. "
            f"Place the verified local source file there (accepted filename(s): {names}); "
            "the registry does not download KEEL data."
        )
    if spec.accepted_filenames and path.name not in spec.accepted_filenames:
        raise ValueError(f"dataset path must use one of {spec.accepted_filenames}; found {path.name}")
    if spec.format.lower() in {"keel_dat", "dat"} or path.suffix.lower() == ".dat":
        frame = _read_keel(path)
    elif spec.format.lower() in {"csv", "tsv"}:
        frame = pd.read_csv(path, sep="\t" if spec.format.lower() == "tsv" else ",")
    else:
        raise ValueError(f"unsupported dataset format {spec.format!r}")
    columns = [*spec.feature_columns, spec.target_column]
    frame = _align_declared_columns(frame, columns)
    missing = [name for name in columns if name not in frame.columns]
    if missing:
        raise ValueError(f"dataset {spec.dataset_id} missing declared columns: {missing}; found {list(frame.columns)}")
    frame = frame.loc[:, columns].copy()
    frame = _normalize(frame, spec)
    fingerprint = _frame_fingerprint(frame)
    return LoadedDataset(spec, path, frame, fingerprint, int(frame.isna().sum().sum()))


def _align_declared_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Accept KEEL's occasional capitalization differences without changing values."""
    available = {str(column).lower(): str(column) for column in frame.columns}
    rename = {available[column.lower()]: column for column in columns if column not in frame.columns and column.lower() in available}
    return frame.rename(columns=rename) if rename else frame


def _read_keel(path: Path) -> pd.DataFrame:
    attributes: list[tuple[str, list[str] | None]] = []
    rows: list[list[Any]] = []
    in_data = False
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for raw_line in stream:
            line = raw_line.strip()
            if not line or line.startswith("%"):
                continue
            lower = line.lower()
            if lower.startswith("@attribute"):
                bits = line.split(None, 2)
                if len(bits) < 3:
                    raise ValueError(f"malformed KEEL @attribute line in {path}: {line}")
                name = bits[1].strip("'\"")
                declaration = bits[2].strip()
                categories: list[str] | None = None
                if declaration.startswith("{") and declaration.endswith("}"):
                    categories = [item.strip().strip("'\"") for item in declaration[1:-1].split(",")]
                attributes.append((name, categories))
            elif lower == "@data":
                in_data = True
            elif in_data:
                values = next(csv.reader([line], skipinitialspace=True))
                if len(values) != len(attributes):
                    raise ValueError(f"KEEL row has {len(values)} values, expected {len(attributes)} in {path}")
                rows.append(values)
    if not attributes or not in_data:
        raise ValueError(f"KEEL file {path} needs @attribute declarations and @data")
    frame = pd.DataFrame(rows, columns=[name for name, _ in attributes])
    for name, categories in attributes:
        if categories is None:
            numeric = pd.to_numeric(frame[name].replace("?", pd.NA), errors="coerce")
            if numeric.notna().sum() == frame[name].notna().sum():
                frame[name] = numeric
        else:
            frame[name] = frame[name].replace("?", pd.NA)
    return frame


def _normalize(frame: pd.DataFrame, spec: DatasetDefinition) -> pd.DataFrame:
    result = frame.copy()
    for column in spec.numerical_columns:
        result[column] = pd.to_numeric(result[column].replace({"?": pd.NA, "": pd.NA}), errors="coerce")
    for column in [*spec.categorical_columns, spec.target_column]:
        result[column] = result[column].map(lambda value: None if pd.isna(value) or str(value).strip() in {"?", ""} else str(value).strip())
    return result


def _frame_fingerprint(frame: pd.DataFrame) -> str:
    payload = frame.to_json(orient="split", date_format="iso", default_handler=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
