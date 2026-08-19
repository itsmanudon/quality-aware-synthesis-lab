from datetime import datetime

from pydantic import ConfigDict, Field, field_validator

from ._base import (
    ContractModel,
    Metadata,
    NonEmptyStr,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveVersion,
    Score,
    utc_datetime,
)
from .enums import QualityDimension, Severity, Verdict
from .provenance import ProvenanceSource


class Evidence(ContractModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, use_enum_values=True)

    evidence_id: NonEmptyStr
    candidate_id: NonEmptyStr
    candidate_version: PositiveVersion
    validator_id: NonEmptyStr
    validator_version: NonEmptyStr
    dimension: QualityDimension
    verdict: Verdict
    severity: Severity
    score: Score | None = None
    confidence: Score | None = None
    affected_fields: tuple[NonEmptyStr, ...] = ()
    message: NonEmptyStr
    provenance: tuple[ProvenanceSource, ...] = ()
    latency_ms: NonNegativeFloat | None = None
    cost_usd: NonNegativeFloat | None = None
    input_tokens: NonNegativeInt | None = None
    output_tokens: NonNegativeInt | None = None
    created_at: datetime
    metadata: Metadata = Field(default_factory=dict)

    @field_validator("dimension", mode="before")
    @classmethod
    def _parse_dimension(cls, value: QualityDimension | str) -> QualityDimension:
        return value if isinstance(value, QualityDimension) else QualityDimension(value)

    @field_validator("verdict", mode="before")
    @classmethod
    def _parse_verdict(cls, value: Verdict | str) -> Verdict:
        return value if isinstance(value, Verdict) else Verdict(value)

    @field_validator("severity", mode="before")
    @classmethod
    def _parse_severity(cls, value: Severity | str) -> Severity:
        return value if isinstance(value, Severity) else Severity(value)

    @field_validator("created_at")
    @classmethod
    def _aware_created_at(cls, value: datetime) -> datetime:
        return utc_datetime(value)
