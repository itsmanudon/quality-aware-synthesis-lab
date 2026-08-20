from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator, model_validator

from rcqasyn.contracts import GenerationObjective, Severity
from rcqasyn.contracts._base import ContractModel, NonEmptyStr, NonNegativeFloat, NonNegativeInt


class DatasetRunConfig(ContractModel):
    dataset_id: NonEmptyStr
    root_seed: NonNegativeInt
    reference_example_count: NonNegativeInt = 3
    reference_examples_enabled: bool = True


class GenerationConfig(ContractModel):
    requested_count: NonNegativeInt = Field(gt=0)
    class_strategy: NonEmptyStr = "preserve_reference"
    class_quotas: dict[str, NonNegativeInt] = Field(default_factory=dict)
    batch_size: NonNegativeInt = Field(gt=0)
    objective: GenerationObjective = GenerationObjective.DATA_EMULATION
    generator_id: NonEmptyStr = "replay-generator"
    generator_version: NonEmptyStr = "1"
    prompt_version: NonEmptyStr = "v1"
    temperature: NonNegativeFloat = 0.0
    max_tokens: NonNegativeInt = Field(default=2048, gt=0)
    provider_seed: NonNegativeInt | None = None

    @field_validator("objective", mode="before")
    @classmethod
    def _objective(cls, value: GenerationObjective | str) -> GenerationObjective:
        return value if isinstance(value, GenerationObjective) else GenerationObjective(value)


class ProviderConfig(ContractModel):
    kind: NonEmptyStr = "replay"
    fixture: Path | None = None
    model: NonEmptyStr = "replay"
    base_url: str | None = None
    api_key_env: str | None = None
    timeout_seconds: NonNegativeFloat = 60.0

    @field_validator("fixture", mode="before")
    @classmethod
    def _fixture(cls, value: Path | str | None) -> Path | None:
        return value if value is None or isinstance(value, Path) else Path(value)


class JudgeConfig(ContractModel):
    provider: ProviderConfig = ProviderConfig()
    judge_id: NonEmptyStr = "single-judge"
    judge_version: NonEmptyStr = "1"
    prompt_version: NonEmptyStr = "v1"
    threshold: float = Field(ge=0.0, le=1.0)
    malformed_policy: NonEmptyStr = "reject"

    @field_validator("malformed_policy")
    @classmethod
    def _malformed_policy(cls, value: str) -> str:
        if value != "reject":
            raise ValueError("malformed_policy currently supports only 'reject'")
        return value


class BaselineConfig(ContractModel):
    reject_severities: tuple[Severity, ...] = (Severity.HIGH, Severity.CRITICAL)
    range_severity: Severity = Severity.MEDIUM

    @field_validator("reject_severities", mode="before")
    @classmethod
    def _severities(cls, values: object) -> tuple[Severity, ...]:
        if not isinstance(values, (list, tuple)):
            raise TypeError("reject_severities must be an array")
        return tuple(value if isinstance(value, Severity) else Severity(value) for value in values)

    @field_validator("range_severity", mode="before")
    @classmethod
    def _range_severity(cls, value: Severity | str) -> Severity:
        return value if isinstance(value, Severity) else Severity(value)


class MetricsConfig(ContractModel):
    classifiers: tuple[NonEmptyStr, ...] = ("logistic_regression", "random_forest")

    @field_validator("classifiers", mode="before")
    @classmethod
    def _classifiers(cls, values: object) -> tuple[str, ...]:
        if isinstance(values, tuple):
            result = values
        elif isinstance(values, list):
            result = tuple(values)
        else:
            raise TypeError("classifiers must be an array")
        supported = {"logistic_regression", "random_forest"}
        unknown = sorted(set(result) - supported)
        if unknown:
            raise ValueError(f"unsupported classifiers: {unknown}; supported: {sorted(supported)}")
        if not result:
            raise ValueError("at least one classifier must be configured")
        return result


class ExperimentConfig(ContractModel):
    experiment_name: NonEmptyStr
    run_id: NonEmptyStr | None = None
    dataset: DatasetRunConfig
    generation: GenerationConfig
    generator: ProviderConfig
    judge: JudgeConfig
    baselines: BaselineConfig = BaselineConfig()
    metrics: MetricsConfig = MetricsConfig()
    artifact_root: Path = Path("artifacts")

    @field_validator("artifact_root", mode="before")
    @classmethod
    def _artifact_root(cls, value: Path | str) -> Path:
        return value if isinstance(value, Path) else Path(value)

    @model_validator(mode="after")
    def _supported_objective(self) -> ExperimentConfig:
        if self.generation.class_strategy not in {"explicit", "preserve_reference"}:
            raise ValueError("class_strategy must be explicit or preserve_reference")
        return self

    def canonical_hash(self) -> str:
        return hashlib.sha256(json.dumps(self.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()


def load_experiment_config(config_path: Path, project_root: Path | None = None) -> tuple[ExperimentConfig, Path]:
    root = (project_root or Path.cwd()).resolve()
    path = Path(config_path)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    with path.open("r", encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    if not isinstance(raw, dict):
        raise TypeError("experiment config must contain a YAML mapping")
    try:
        config = ExperimentConfig.model_validate(raw)
    except Exception as error:
        raise ValueError(f"invalid experiment config {path}: {error}") from error
    config = config.model_copy(update={
        "artifact_root": _resolve(root, config.artifact_root),
        "generator": config.generator.model_copy(update={"fixture": _resolve_optional(root, config.generator.fixture)}),
        "judge": config.judge.model_copy(update={"provider": config.judge.provider.model_copy(update={"fixture": _resolve_optional(root, config.judge.provider.fixture)})}),
    })
    return config, path


def _resolve(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else (root / path).resolve()


def _resolve_optional(root: Path, path: Path | None) -> Path | None:
    return _resolve(root, path) if path else None
