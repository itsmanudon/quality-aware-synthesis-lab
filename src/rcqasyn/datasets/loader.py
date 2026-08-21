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


@dataclass(frozen=True)
class KeelAttribute:
    name: str
    declaration: str
    kind: str
    categories: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "declaration": self.declaration,
            "kind": self.kind,
            "categories": list(self.categories),
        }


@dataclass(frozen=True)
class KeelSchema:
    relation: str | None
    attributes: tuple[KeelAttribute, ...]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    frame: pd.DataFrame
    missing_representation: str


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
    return inspect_keel(path).frame


def inspect_keel(path: Path) -> KeelSchema:
    """Parse KEEL declarations and data, retaining metadata for audit reports."""

    attributes: list[tuple[str, list[str] | None]] = []
    declarations: list[str] = []
    rows: list[list[Any]] = []
    relation: str | None = None
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    in_data = False
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for raw_line in stream:
            line = raw_line.strip()
            if not line or line.startswith("%"):
                continue
            lower = line.lower()
            if lower.startswith("@relation"):
                bits = line.split(None, 1)
                if len(bits) == 2:
                    relation = bits[1].strip().strip("'\"")
            elif lower.startswith("@inputs"):
                inputs = _parse_name_list(line)
            elif lower.startswith("@outputs"):
                outputs = _parse_name_list(line)
            elif lower.startswith("@attribute"):
                bits = line.split(None, 2)
                if len(bits) < 3:
                    raise ValueError(f"malformed KEEL @attribute line in {path}: {line}")
                name = bits[1].strip("'\"")
                declaration = bits[2].strip()
                declarations.append(declaration)
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
    parsed_attributes: list[KeelAttribute] = []
    for (name, categories), declaration in zip(attributes, declarations):
        lower_declaration = declaration.lower()
        kind = "nominal" if categories is not None else "numerical" if any(
            token in lower_declaration for token in ("integer", "real", "numeric")
        ) else "declared"
        parsed_attributes.append(KeelAttribute(name, declaration, kind, tuple(categories or ())))
        if categories is None:
            raw_values = frame[name].replace("?", pd.NA)
            numeric = pd.to_numeric(raw_values, errors="coerce")
            if numeric.notna().sum() == raw_values.notna().sum():
                frame[name] = numeric
            else:
                frame[name] = raw_values
        else:
            frame[name] = frame[name].replace("?", pd.NA)
    return KeelSchema(
        relation=relation,
        attributes=tuple(parsed_attributes),
        inputs=inputs,
        outputs=outputs,
        frame=frame,
        missing_representation="?",
    )


def _parse_name_list(line: str) -> tuple[str, ...]:
    bits = line.split(None, 1)
    values = bits[1] if len(bits) == 2 else ""
    return tuple(item.strip().strip("'\"") for item in values.split(",") if item.strip())


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
