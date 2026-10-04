"""Derive scientific requirements from recorded inputs without rerunning science."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from rcqasyn.config.experiment import ExperimentConfig
from rcqasyn.datasets.profile import DatasetProfile
from rcqasyn.datasets.registry import DatasetDefinition

from .specification import fingerprint, resolved_control_policies


def _same(expected: Any, observed: Any, label: str) -> None:
    # Canonical JSON distinguishes otherwise equal Python values, such as True and 1.
    if fingerprint(expected) != fingerprint(observed):
        raise ValueError(f"recorded {label} identity mismatch")


def validate_recorded_requirements(
    spec: dict[str, Any],
    config: ExperimentConfig,
    profile: DatasetProfile,
    *,
    train_classes: list[str] | None = None,
) -> None:
    """Bind complete control descriptors and result families to recorded sources.

    The caller validates the recorded config, profile, prompt bytes, and provider
    identities first. No registry, raw source, current prompt, metric evaluation,
    admission logic, or installed estimator defaults are consulted here.
    """
    try:
        recorded = spec["dataset"]["definition"]
        if not isinstance(recorded, dict):
            raise TypeError("required recorded dataset definition must be an object")
        # Scientific snapshots intentionally omit these location/display fields.
        # Restore inert values solely to run the real DatasetDefinition validators.
        definition = DatasetDefinition.model_validate(
            {**recorded, "raw_path": Path("recorded-dataset"), "display_name": "recorded dataset"}
        )
        _same(
            definition.model_dump(
                mode="json", exclude={"raw_path", "accepted_filenames", "display_name"}
            ),
            recorded,
            "dataset definition",
        )
        _same(config.dataset.dataset_id, definition.dataset_id, "dataset configuration")
        _same(definition.dataset_id, profile.dataset_id, "dataset profile")
        _same(list(definition.feature_columns), list(profile.feature_columns), "profile features")
        _same(definition.target_column, profile.target_column, "profile target")
        _same(
            {column: "numerical" for column in definition.numerical_columns}
            | {column: "categorical" for column in definition.categorical_columns},
            profile.column_types,
            "profile column types",
        )
        _same(
            sorted([*definition.categorical_columns, definition.target_column]),
            sorted(profile.domains),
            "profile categorical domains",
        )
        if not set(profile.numeric_summary) <= set(definition.numerical_columns):
            raise ValueError("recorded profile numeric summary identity mismatch")

        evaluation = spec["evaluation"]
        parameters = evaluation["estimator_parameters"]
        if not isinstance(parameters, dict):
            raise TypeError("required recorded estimator parameters must be an object")
        _same(sorted(config.metrics.classifiers), sorted(parameters), "estimator families")
        for name, values in parameters.items():
            if not isinstance(values, dict):
                raise TypeError(f"required recorded {name} estimator parameters must be an object")
            _same(config.dataset.root_seed, values.get("random_state"), f"{name} estimator seed")

        expected_controls = resolved_control_policies(
            config,
            definition,
            profile,
            prompt_hashes=spec["prompts"],
            provider_identities=spec["providers"],
            estimator_parameters=parameters,
        )
        _same(expected_controls, spec["controls"], "control requirements")

        # The profile uses this sentinel for null TRAIN targets; the writer's
        # class-conditional family declaration excludes null targets.
        # A normalized TRAIN snapshot, when available, also disambiguates a
        # literal label named '<MISSING>' from the profile's null sentinel.
        classes = (
            train_classes
            if train_classes is not None
            else sorted(label for label in profile.class_counts if label != "<MISSING>")
        )
        expected_evaluation = {
            "version": "m1-metrics-v1",
            "pr_auc": "alias_average_precision",
            "positive_label": "existing_minority_or_max_train_label",
            "classifiers": list(config.metrics.classifiers),
            "result_families": {
                "numeric_columns": list(definition.numerical_columns),
                "categorical_columns": [*definition.categorical_columns, definition.target_column],
                "class_categorical_columns": list(definition.categorical_columns),
                "classes": classes,
                "populations": ["TRTR", "TSTR"],
            },
            "estimator_parameters": parameters,
            "preprocessing": {
                "numeric": ["median_imputation", "standard_scaler"],
                "categorical": ["most_frequent_imputation", "onehot_ignore_unknown"],
            },
        }
        _same(expected_evaluation, evaluation, "evaluation requirements")
    except (KeyError, TypeError, AttributeError, ValidationError) as error:
        raise ValueError("required recorded scientific requirements are missing or invalid") from error
