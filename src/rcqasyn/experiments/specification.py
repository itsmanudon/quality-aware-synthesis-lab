"""Versioned scientific policy identity, separate from an execution and environment."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import sys
from pathlib import Path
from typing import Any

from rcqasyn.config.experiment import ExperimentConfig
from rcqasyn.datasets import (
    DatasetDefinition,
    DatasetRegistry,
    build_profile,
    load_dataset,
    make_split,
)
from rcqasyn.datasets.loader import LoadedDataset
from rcqasyn.datasets.profile import DatasetProfile
from rcqasyn.datasets.split import SplitManifest
from rcqasyn.generation.prompts import load_prompt
from rcqasyn.metrics.utility import resolve_estimators
from rcqasyn.storage.ownership import file_hash


def fingerprint(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def control_policies(config: ExperimentConfig) -> dict[str, Any]:
    """Legacy unbound v1 descriptors, retained for snapshot compatibility.

    Execution identity must use :func:`resolved_control_policies` instead.
    """
    shared = {
        "parser": "json-wrapper-v2"
        if config.generation.transport_version == "v2"
        else "json-array-v1",
        "parser_policy": "fenced_or_embedded_array_or_records_wrapper; object_items_only; no_truncation",
        "evaluation": "m1-metrics-v1",
        "classifiers": list(config.metrics.classifiers),
        "classifier_seed": config.dataset.root_seed,
        "preprocessing": "numeric_median_standard_scaler; categorical_most_frequent_onehot_ignore_unknown",
        "estimator_parameters": {
            "logistic_regression": {"max_iter": 300, "solver": "liblinear"},
            "random_forest": {"n_estimators": 50},
        },
    }
    policies = {
        "b1": {"version": "b1-policy-v1", "admission": "all_parseable", **shared},
        "b2": {
            "version": "b2-policy-v1",
            "validators": [
                "schema",
                "categorical-domain",
                "missing",
                "target-condition",
                "observed-range",
            ],
            "configuration": config.baselines.model_dump(mode="json"),
            "categories": "reject_train_unseen",
            "missing": "dataset_policy_reject_FAIL_HIGH_else_preserve_WARN_MEDIUM",
            "duplicates": "exact_canonical_json_all_keys_first_seen_even_if_rejected",
            "ordering": "generation_pool_order",
            "rejection": "FAIL_or_WARN_with_configured_severity_or_duplicate",
            "range": "outside_TRAIN_min_max_WARN_configured_severity",
            "schema": "exact_declared_keys; numeric_primitive_not_bool; null_allowed",
            **shared,
        },
        "b3": {
            "version": "b3-policy-v1",
            "threshold": config.judge.threshold,
            "verdicts": ["pass", "warn"],
            "malformed": config.judge.malformed_policy,
            "judge": config.judge.model_dump(mode="json", exclude={"provider"}),
            "context_transport": config.generation.transport_version,
            "seed": config.generation.provider_seed,
            "seed_route": "unchanged_base_seed_each_judge",
            "max_tokens": config.generation.max_tokens,
            "temperature": 0.0,
            "judge_parser": "judge-json-v1",
            **shared,
        },
    }
    return {
        name: {"descriptor": value, "fingerprint": fingerprint(value)}
        for name, value in policies.items()
    }


def _estimator_parameters(config: ExperimentConfig) -> dict[str, Any]:
    models = resolve_estimators(config.dataset.root_seed)
    return {name: models[name].get_params(deep=False) for name in config.metrics.classifiers}


def resolved_control_policies(
    config: ExperimentConfig,
    spec: DatasetDefinition,
    profile: DatasetProfile,
    *,
    prompt_hashes: dict[str, str],
    provider_identities: dict[str, dict[str, Any]],
    estimator_parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bind policy semantics to effective execution inputs, using TRAIN only.

    Full profile lineage includes held-out fingerprints and artifact IDs; the
    bounded context intentionally excludes those from the control identity.
    """
    policies = {name: policy["descriptor"] for name, policy in control_policies(config).items()}
    parameters = (
        estimator_parameters if estimator_parameters is not None else _estimator_parameters(config)
    )
    evaluation_schema = spec.model_dump(
        mode="json",
        include={
            "feature_columns",
            "target_column",
            "numerical_columns",
            "categorical_columns",
            "minority_label",
        },
    )
    for name, descriptor in policies.items():
        descriptor["version"] = f"{name}-resolved-policy-v2"
        descriptor["binding"] = "resolved-execution-inputs-v1"
        descriptor["estimator_parameters"] = parameters
        descriptor["evaluation_schema"] = evaluation_schema
    policies["b2"]["dataset_validation"] = spec.model_dump(
        mode="json",
        include={
            "feature_columns",
            "target_column",
            "numerical_columns",
            "categorical_columns",
            "missing_policy",
        },
    )
    policies["b2"]["train_domains"] = profile.model_dump(mode="json", include={"domains"})[
        "domains"
    ]
    policies["b2"]["train_ranges"] = {
        column: {bound: summary[bound] for bound in ("min", "max")}
        for column, summary in profile.numeric_summary.items()
    }
    policies["b3"]["provider"] = provider_identities["judge"]
    policies["b3"]["prompt_sha256"] = prompt_hashes["judge"]
    policies["b3"]["train_context_sha256"] = fingerprint(profile.to_generation_context())
    policies["b3"]["context_identity"] = "bounded-train-profile-v1"
    return {
        name: {"descriptor": descriptor, "fingerprint": fingerprint(descriptor)}
        for name, descriptor in policies.items()
    }


def scientific_specification(
    config: ExperimentConfig,
    root: Path,
    *,
    replay: bool,
    dataset: LoadedDataset | None = None,
    split: SplitManifest | None = None,
    profile: DatasetProfile | None = None,
    prompt_hashes: dict[str, str] | None = None,
    raw_source_sha256: str | None = None,
    provider_sources: dict[str, str] | None = None,
) -> dict[str, Any]:
    registry = DatasetRegistry(project_root=root)
    if dataset is None:
        spec = registry.get(config.dataset.dataset_id)
        raw_source_sha256 = file_hash(registry.resolve_path(spec))
        dataset = load_dataset(spec, registry)
    if raw_source_sha256 is None:
        raise ValueError("resolved scientific specification requires captured raw source identity")
    if file_hash(dataset.path) != raw_source_sha256:
        raise ValueError("dataset source provenance changed during resolution")
    split = split or make_split(dataset, config.dataset.root_seed)
    profile = profile or build_profile(
        dataset,
        split,
        reference_example_count=config.dataset.reference_example_count,
        reference_examples_per_class=config.dataset.reference_examples_per_class,
        seed=config.dataset.root_seed,
        enabled=config.dataset.reference_examples_enabled,
    )
    resolved_prompts = (
        prompt_hashes
        if prompt_hashes is not None
        else {
            role: load_prompt(role, version, root).sha256
            for role, version in (
                ("generation", config.generation.prompt_version),
                ("judge", config.judge.prompt_version),
            )
        }
    )
    estimator_parameters = _estimator_parameters(config)
    definition = dataset.spec.model_dump(
        mode="json", exclude={"raw_path", "accepted_filenames", "display_name"}
    )
    providers = {}
    for name, provider in (("generator", config.generator), ("judge", config.judge.provider)):
        resolved = provider.model_dump(
            mode="json", exclude={"fixture", "api_key_env", "timeout_seconds"}
        )
        if provider.fixture:
            path = provider.fixture if provider.fixture.is_absolute() else root / provider.fixture
            captured = (provider_sources or {}).get(name)
            current = file_hash(path)
            if captured is not None and captured != current:
                raise ValueError(f"{name} recorded-response provenance changed during resolution")
            resolved["recorded_responses_sha256"] = captured or current
        providers[name] = resolved
    specification = {
        "schema_version": "m1-scientific-spec-v1",
        "dataset": {
            "definition": definition,
            "normalized_fingerprint": dataset.fingerprint,
            "raw_source_sha256": raw_source_sha256,
        },
        "dataset_run": config.dataset.model_dump(mode="json"),
        "split_protocol": "stratified_hash_order_v1",
        "split_seed": split.split_seed,
        "generation": config.generation.model_dump(mode="json"),
        "providers": providers,
        "prompts": resolved_prompts,
        "controls": resolved_control_policies(
            config,
            dataset.spec,
            profile,
            prompt_hashes=resolved_prompts,
            provider_identities=providers,
            estimator_parameters=estimator_parameters,
        ),
        "evaluation": {
            "version": "m1-metrics-v1",
            "pr_auc": "alias_average_precision",
            "positive_label": "existing_minority_or_max_train_label",
            "classifiers": list(config.metrics.classifiers),
            "result_families": {
                "numeric_columns": list(dataset.spec.numerical_columns),
                "categorical_columns": [
                    *dataset.spec.categorical_columns,
                    dataset.spec.target_column,
                ],
                "class_categorical_columns": list(dataset.spec.categorical_columns),
                "classes": sorted(
                    set(
                        dataset.frame.loc[list(split.train_indices), dataset.spec.target_column]
                        .dropna()
                        .astype(str)
                    )
                ),
                "populations": ["TRTR", "TSTR"],
            },
            "estimator_parameters": estimator_parameters,
            "preprocessing": {
                "numeric": ["median_imputation", "standard_scaler"],
                "categorical": ["most_frequent_imputation", "onehot_ignore_unknown"],
            },
        },
        "execution_protocol": "recorded_response_only"
        if replay and config.judge.provider.kind in {"replay", "fixture"}
        else "fresh",
        "generator_judge_same_model": config.generator_judge_same_model,
    }
    return {"specification": specification, "fingerprint": fingerprint(specification)}


def seed_provenance(
    config: ExperimentConfig, split: Any, seed_plan: dict[str, Any]
) -> dict[str, Any]:
    return {
        "root_seed": config.dataset.root_seed,
        "split_seed": split.split_seed,
        "reference_examples": {
            "seed": config.dataset.root_seed,
            "algorithm": "sha256_order_profile_v1",
        },
        "generation": seed_plan,
        "judge_seed": config.generation.provider_seed,
        "judge_seed_route": "same_generation_base_seed_each_candidate",
        "classifier_seed": config.dataset.root_seed,
        "provider_reproduction_guaranteed": False,
        "provider_limitation": "seed absent"
        if config.generation.provider_seed is None
        else "provider seed support and deterministic execution are not guaranteed",
    }


def environment_snapshot() -> dict[str, Any]:
    packages = {}
    for name in ("rcqasyn", "numpy", "pandas", "scipy", "scikit-learn", "pydantic", "PyYAML"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {"python": sys.version, "platform": platform.platform(), "packages": packages}
