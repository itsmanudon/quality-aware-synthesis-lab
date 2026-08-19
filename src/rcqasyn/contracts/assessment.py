from datetime import datetime

from pydantic import Field, field_validator

from ._base import ContractModel, Metadata, NonEmptyStr, PositiveVersion, Score, utc_datetime
from .enums import QualityDimension, Severity


class Defect(ContractModel):
    defect_id: NonEmptyStr
    dimension: QualityDimension
    severity: Severity
    affected_fields: tuple[NonEmptyStr, ...] = ()
    description: NonEmptyStr
    evidence_ids: tuple[NonEmptyStr, ...] = ()
    repairable: bool
    metadata: Metadata = Field(default_factory=dict)

    @field_validator("dimension", mode="before")
    @classmethod
    def _parse_dimension(cls, value: QualityDimension | str) -> QualityDimension:
        return value if isinstance(value, QualityDimension) else QualityDimension(value)

    @field_validator("severity", mode="before")
    @classmethod
    def _parse_severity(cls, value: Severity | str) -> Severity:
        return value if isinstance(value, Severity) else Severity(value)


class Assessment(ContractModel):
    assessment_id: NonEmptyStr
    candidate_id: NonEmptyStr
    candidate_version: PositiveVersion
    quality_scores: dict[QualityDimension, Score] = Field(default_factory=dict)
    risk_scores: dict[QualityDimension, Score] = Field(default_factory=dict)
    uncertainty_scores: dict[QualityDimension, Score] = Field(default_factory=dict)
    defects: tuple[Defect, ...] = ()
    critic_disagreement: Score | None = None
    hard_constraints_passed: bool
    critical_risk: bool
    evidence_ids: tuple[NonEmptyStr, ...] = ()
    created_at: datetime
    metadata: Metadata = Field(default_factory=dict)

    @field_validator("created_at")
    @classmethod
    def _aware_created_at(cls, value: datetime) -> datetime:
        return utc_datetime(value)


class DatasetContribution(ContractModel):
    candidate_id: NonEmptyStr
    utility_delta: float
    coverage_delta: float
    redundancy: Score
    accepted: bool
    metadata: Metadata = Field(default_factory=dict)


class AuditResult(ContractModel):
    audit_id: NonEmptyStr
    dataset_id: NonEmptyStr
    passed: bool
    findings: tuple[NonEmptyStr, ...] = ()
    scores: dict[NonEmptyStr, Score] = Field(default_factory=dict)
    created_at: datetime
    metadata: Metadata = Field(default_factory=dict)

    @field_validator("created_at")
    @classmethod
    def _aware_created_at(cls, value: datetime) -> datetime:
        return utc_datetime(value)
