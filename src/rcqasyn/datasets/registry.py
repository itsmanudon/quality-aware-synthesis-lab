from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator, model_validator

from rcqasyn.contracts._base import (
    ContractModel,
    Metadata,
    NonEmptyStr,
    NonNegativeFloat,
    NonNegativeInt,
)


class SplitSpec(ContractModel):
    test_size: NonNegativeFloat = Field(gt=0.0, lt=1.0)
    seed_offset: NonNegativeInt = 0
    stratify: bool = True


class DatasetDefinition(ContractModel):
    dataset_id: NonEmptyStr
    display_name: NonEmptyStr
    raw_path: Path
    accepted_filenames: tuple[NonEmptyStr, ...] = ()
    format: NonEmptyStr = "keel_dat"
    target_column: NonEmptyStr
    feature_columns: tuple[NonEmptyStr, ...]
    categorical_columns: tuple[NonEmptyStr, ...] = ()
    numerical_columns: tuple[NonEmptyStr, ...] = ()
    missing_policy: NonEmptyStr = "preserve_as_null"
    minority_label: str | int | float | None = None
    task_type: NonEmptyStr = "classification"
    source_url: str | None = None
    source_page: str | None = None
    preprocessing: tuple[NonEmptyStr, ...] = ()
    split: SplitSpec = SplitSpec(test_size=0.2)
    metadata: Metadata = Field(default_factory=dict)

    @field_validator("raw_path", mode="before")
    @classmethod
    def _path(cls, value: Path | str) -> Path:
        return value if isinstance(value, Path) else Path(value)

    @field_validator("accepted_filenames", "feature_columns", "categorical_columns", "numerical_columns", "preprocessing", mode="before")
    @classmethod
    def _tuples(cls, value: object) -> tuple[str, ...]:
        if isinstance(value, tuple):
            return value
        if isinstance(value, list):
            return tuple(value)
        raise ValueError("declared column and filename lists must be arrays")

    @model_validator(mode="after")
    def _columns(self) -> DatasetDefinition:
        features = set(self.feature_columns)
        if self.target_column in features:
            raise ValueError("target_column must not be in feature_columns")
        if not set(self.categorical_columns) <= features:
            raise ValueError("categorical_columns must be feature columns")
        if not set(self.numerical_columns) <= features:
            raise ValueError("numerical_columns must be feature columns")
        if set(self.categorical_columns) & set(self.numerical_columns):
            raise ValueError("categorical_columns and numerical_columns must not overlap")
        if set(self.categorical_columns) | set(self.numerical_columns) != features:
            raise ValueError("each feature must have exactly one declared type")
        return self


class DatasetRegistry:
    def __init__(self, specs_dir: Path | None = None, project_root: Path | None = None) -> None:
        self.project_root = (project_root or Path.cwd()).resolve()
        self.specs_dir = (specs_dir or self.project_root / "configs" / "datasets").resolve()
        self._specs: dict[str, DatasetDefinition] | None = None

    def _load(self) -> dict[str, DatasetDefinition]:
        if self._specs is not None:
            return self._specs
        loaded: dict[str, DatasetDefinition] = {}
        if self.specs_dir.is_dir():
            paths = sorted(self.specs_dir.glob("*.yaml")) + sorted(self.specs_dir.glob("*.yml"))
            for path in paths:
                with path.open("r", encoding="utf-8") as stream:
                    raw: Any = yaml.safe_load(stream)
                if not isinstance(raw, dict):
                    raise TypeError(f"dataset spec must be a mapping: {path}")
                try:
                    spec = DatasetDefinition.model_validate(raw)
                except Exception as error:
                    raise ValueError(f"invalid dataset spec {path}: {error}") from error
                if spec.dataset_id in loaded:
                    raise ValueError(f"duplicate dataset_id: {spec.dataset_id}")
                loaded[spec.dataset_id] = spec
        self._specs = loaded
        return loaded

    def list(self) -> tuple[DatasetDefinition, ...]:
        return tuple(self._load()[key] for key in sorted(self._load()))

    def get(self, dataset_id: str) -> DatasetDefinition:
        try:
            return self._load()[dataset_id]
        except KeyError as error:
            available = ", ".join(sorted(self._load())) or "none"
            raise KeyError(f"unknown dataset {dataset_id!r}; available: {available}") from error

    def resolve_path(self, spec: DatasetDefinition) -> Path:
        return spec.raw_path if spec.raw_path.is_absolute() else (self.project_root / spec.raw_path).resolve()
