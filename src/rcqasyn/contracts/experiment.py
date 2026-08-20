from datetime import datetime

from pydantic import ConfigDict, Field, field_validator

from ._base import (
    ContractModel,
    Metadata,
    NonEmptyStr,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveInt,
    Score,
    utc_datetime,
)
from .enums import GenerationObjective, Severity, Verdict


class ClassQuota(ContractModel):
    label: NonEmptyStr
    count: PositiveInt


class GenerationPlan(ContractModel):
    """Fully resolved generation request; distribution choices are never implicit."""

    model_config = ConfigDict(strict=True, extra="forbid")

    plan_id: NonEmptyStr
    requested_count: PositiveInt
    requested_class: str | None = None
    dataset_id: NonEmptyStr
    objective: GenerationObjective
    class_strategy: NonEmptyStr
    class_quotas: tuple[ClassQuota, ...] = ()
    reference_example_count: NonNegativeInt = 0
    reference_examples_enabled: bool = True
    source_profile_id: NonEmptyStr
    source_profile_hash: NonEmptyStr
    generator_id: NonEmptyStr
    generator_version: NonEmptyStr
    generator_config: Metadata = Field(default_factory=dict)
    prompt_version: NonEmptyStr
    prompt_hash: NonEmptyStr
    batch_size: PositiveInt
    seed: NonNegativeInt
    metadata: Metadata = Field(default_factory=dict)

    @field_validator("objective", mode="before")
    @classmethod
    def _objective(cls, value: GenerationObjective | str) -> GenerationObjective:
        return value if isinstance(value, GenerationObjective) else GenerationObjective(value)


class ProviderCallTrace(ContractModel):
    """Serializable trace for a generator or judge call; secrets are never retained."""

    call_id: NonEmptyStr
    run_id: NonEmptyStr
    role: NonEmptyStr
    provider: NonEmptyStr
    model: NonEmptyStr
    endpoint: str | None = None
    prompt_version: NonEmptyStr | None = None
    prompt_hash: NonEmptyStr | None = None
    prompt: str | None = None
    raw_response: str | None = None
    requested_class: str | None = None
    requested_count: PositiveInt | None = None
    max_tokens: PositiveInt | None = None
    temperature: NonNegativeFloat | None = None
    seed: NonNegativeInt | None = None
    input_tokens: NonNegativeInt | None = None
    output_tokens: NonNegativeInt | None = None
    total_tokens: NonNegativeInt | None = None
    cost_usd: NonNegativeFloat | None = None
    latency_ms: NonNegativeFloat | None = None
    created_at: datetime
    replay_source_id: NonEmptyStr | None = None
    metadata: Metadata = Field(default_factory=dict)

    @field_validator("created_at")
    @classmethod
    def _aware_created_at(cls, value: datetime) -> datetime:
        return utc_datetime(value)


class ParseFailureEvent(ContractModel):
    event_id: NonEmptyStr
    run_id: NonEmptyStr
    call_id: NonEmptyStr
    parser_version: NonEmptyStr
    raw_output: str | None = None
    raw_response_reference: NonEmptyStr | None = None
    error: NonEmptyStr
    recoverable: bool
    item_index: NonNegativeInt | None = None
    created_at: datetime
    metadata: Metadata = Field(default_factory=dict)

    @field_validator("created_at")
    @classmethod
    def _aware_created_at(cls, value: datetime) -> datetime:
        return utc_datetime(value)


class JudgeResult(ContractModel):
    result_id: NonEmptyStr
    run_id: NonEmptyStr
    candidate_id: NonEmptyStr
    judge_call_id: NonEmptyStr
    score: Score
    verdict: Verdict
    reasons: tuple[NonEmptyStr, ...] = ()
    affected_fields: tuple[NonEmptyStr, ...] = ()
    self_confidence: Score | None = None
    confidence_calibration: NonEmptyStr = "uncalibrated"
    created_at: datetime
    metadata: Metadata = Field(default_factory=dict)

    @field_validator("verdict", mode="before")
    @classmethod
    def _verdict(cls, value: Verdict | str) -> Verdict:
        return value if isinstance(value, Verdict) else Verdict(value)

    @field_validator("created_at")
    @classmethod
    def _aware_created_at(cls, value: datetime) -> datetime:
        return utc_datetime(value)


class FailureAggregate(ContractModel):
    parse_failure: NonNegativeInt = 0
    missing_field: NonNegativeInt = 0
    category_invalid: NonNegativeInt = 0
    target_wrong: NonNegativeInt = 0
    duplicate: NonNegativeInt = 0
    deterministic_structural_rejection: NonNegativeInt = 0
    judge_rejection: NonNegativeInt = 0
    judge_malformed: NonNegativeInt = 0
    judge_provider_failure: NonNegativeInt = 0


class MetricValue(ContractModel):
    value: float | None = None
    status: NonEmptyStr = "ok"
    metadata: Metadata = Field(default_factory=dict)


class EvidenceSummary(ContractModel):
    candidate_id: NonEmptyStr
    accepted: bool
    evidence_ids: tuple[NonEmptyStr, ...] = ()
    severities: tuple[Severity, ...] = ()
    verdicts: tuple[Verdict, ...] = ()
    metadata: Metadata = Field(default_factory=dict)


class BaselineDecision(ContractModel):
    candidate_id: NonEmptyStr
    baseline: NonEmptyStr
    accepted: bool
    reason: NonEmptyStr
    evidence_ids: tuple[NonEmptyStr, ...] = ()
    judge_result_id: NonEmptyStr | None = None
    created_at: datetime
    metadata: Metadata = Field(default_factory=dict)

    @field_validator("created_at")
    @classmethod
    def _aware_created_at(cls, value: datetime) -> datetime:
        return utc_datetime(value)
