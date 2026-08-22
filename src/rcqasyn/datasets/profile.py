# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportOptionalMemberAccess=false
from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np
import pandas as pd
from pydantic import Field

from rcqasyn.contracts._base import ContractModel, JsonValue, Metadata, NonEmptyStr, NonNegativeInt

from .loader import LoadedDataset
from .split import SplitManifest


class DatasetProfile(ContractModel):
    profile_id: NonEmptyStr
    profile_version: NonEmptyStr
    dataset_id: NonEmptyStr
    dataset_fingerprint: NonEmptyStr
    split_fingerprint: NonEmptyStr
    train_indices: tuple[NonNegativeInt, ...]
    train_row_count: NonNegativeInt
    feature_columns: tuple[NonEmptyStr, ...]
    target_column: NonEmptyStr
    column_types: dict[NonEmptyStr, NonEmptyStr]
    domains: dict[NonEmptyStr, tuple[str, ...]] = Field(default_factory=dict)
    missing_rates: dict[NonEmptyStr, float] = Field(default_factory=dict)
    numeric_summary: dict[NonEmptyStr, dict[str, float]] = Field(default_factory=dict)
    class_counts: dict[str, NonNegativeInt] = Field(default_factory=dict)
    class_proportions: dict[str, float] = Field(default_factory=dict)
    reference_examples: tuple[dict[str, JsonValue], ...] = ()
    reference_indices: tuple[NonNegativeInt, ...] = ()
    reference_enabled: bool = True
    reference_policy: NonEmptyStr = "total_count"
    reference_example_count: NonNegativeInt = 0
    reference_examples_per_class: NonNegativeInt | None = None
    config_version: NonEmptyStr = "profile-v1"
    metadata: Metadata = Field(default_factory=dict)

    def to_generation_context(self) -> dict[str, Any]:
        """Return the bounded TRAIN-only view intended for provider prompts.

        The full profile remains the authoritative artifact and retains split
        indices/fingerprints for lineage.  Generation does not need those
        implementation details: serializing them scales prompt size with the
        number of TRAIN rows and consumes the model's output budget.
        """

        fields = {
            column: {
                "type": self.column_types.get(column, "unknown"),
                "missing_rate": self.missing_rates.get(column, 0.0),
            }
            for column in self.feature_columns
        }
        return {
            "dataset_id": self.dataset_id,
            "fields": fields,
            "target_column": self.target_column,
            "categorical_domains": self.domains,
            "numeric_summary": self.numeric_summary,
            "class_counts": self.class_counts,
            "class_proportions": self.class_proportions,
            "reference_examples": self.reference_examples,
        }


def build_profile(
    dataset: LoadedDataset,
    split: SplitManifest,
    *,
    reference_example_count: int = 3,
    reference_examples_per_class: int | None = None,
    seed: int = 0,
    enabled: bool = True,
) -> DatasetProfile:
    train = dataset.frame.loc[list(split.train_indices)].copy()
    spec = dataset.spec
    numeric_summary: dict[str, dict[str, float]] = {}
    for column in spec.numerical_columns:
        values = pd.to_numeric(train[column], errors="coerce").dropna().to_numpy(dtype=float)
        if len(values):
            quantiles = np.quantile(values, [0.0, 0.25, 0.5, 0.75, 1.0])
            numeric_summary[column] = {
                "min": float(quantiles[0]), "q25": float(quantiles[1]), "median": float(quantiles[2]),
                "q75": float(quantiles[3]), "max": float(quantiles[4]),
            }
    domains = {
        column: tuple(sorted(str(v) for v in train[column].dropna().unique()))
        for column in spec.categorical_columns
    }
    target = train[spec.target_column].astype("string").fillna("<MISSING>")
    domains[spec.target_column] = tuple(sorted(str(v) for v in target.unique()))
    class_counts = {str(label): int(count) for label, count in target.value_counts().sort_index().items()}
    total = len(target)
    class_proportions = {label: count / total for label, count in class_counts.items()} if total else {}
    reference_indices: list[int] = []
    policy = "per_class" if reference_examples_per_class is not None else "total_count"
    if enabled and (reference_examples_per_class or reference_example_count) > 0:
        if reference_examples_per_class is not None:
            for label in sorted(class_counts):
                candidates = [i for i in split.train_indices if str(target.loc[i]) == label]
                candidates.sort(key=lambda i: hashlib.sha256(f"{seed}:{label}:{i}".encode()).hexdigest())
                reference_indices.extend(candidates[:reference_examples_per_class])
        else:
            # Legacy behavior is retained for old configs: ensure class
            # coverage first, then fill the requested total deterministically.
            for label in sorted(class_counts):
                candidates = [i for i in split.train_indices if str(target.loc[i]) == label]
                candidates.sort(key=lambda i: hashlib.sha256(f"{seed}:{label}:{i}".encode()).hexdigest())
                if candidates:
                    reference_indices.append(candidates[0])
            remaining = [i for i in split.train_indices if i not in reference_indices]
            remaining.sort(key=lambda i: hashlib.sha256(f"{seed}:reference:{i}".encode()).hexdigest())
            reference_indices.extend(remaining)
            reference_indices = reference_indices[:reference_example_count]
    examples = tuple(_json_record(dataset.frame.loc[index].to_dict()) for index in reference_indices)
    profile_payload = {
        "dataset_id": spec.dataset_id, "dataset_fingerprint": dataset.fingerprint,
        "split_fingerprint": split.to_dict()["split_fingerprint"], "train_indices": list(split.train_indices),
        "reference_indices": reference_indices, "reference_enabled": enabled,
        "reference_policy": policy, "reference_example_count": len(reference_indices),
        "reference_examples_per_class": reference_examples_per_class,
        "config_version": "profile-v1",
    }
    profile_id = "profile-" + hashlib.sha256(json.dumps(profile_payload, sort_keys=True).encode()).hexdigest()[:16]
    return DatasetProfile(
        profile_id=profile_id,
        profile_version="1",
        dataset_id=spec.dataset_id,
        dataset_fingerprint=dataset.fingerprint,
        split_fingerprint=split.to_dict()["split_fingerprint"],
        train_indices=tuple(split.train_indices),
        train_row_count=len(train),
        feature_columns=spec.feature_columns,
        target_column=spec.target_column,
        column_types={column: "categorical" for column in spec.categorical_columns} | {column: "numerical" for column in spec.numerical_columns},
        domains=domains,
        missing_rates={column: float(train[column].isna().mean()) for column in [*spec.feature_columns, spec.target_column]},
        numeric_summary=numeric_summary,
        class_counts=class_counts,
        class_proportions=class_proportions,
        reference_examples=examples,
        reference_indices=tuple(reference_indices),
        reference_enabled=enabled,
        reference_policy=policy,
        reference_example_count=len(reference_indices),
        reference_examples_per_class=reference_examples_per_class,
    )


def _json_record(values: dict[str, Any]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in values.items():
        if pd.isna(value):
            result[key] = None
        elif isinstance(value, (np.integer,)):
            result[key] = int(value)
        elif isinstance(value, (np.floating,)):
            result[key] = float(value)
        elif isinstance(value, (str, int, float, bool)):
            result[key] = value
        else:
            result[key] = str(value)
    return result
