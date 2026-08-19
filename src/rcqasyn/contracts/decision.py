from datetime import datetime

from pydantic import Field, field_validator

from ._base import (
    ContractModel,
    Metadata,
    NonEmptyStr,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveVersion,
    utc_datetime,
)
from .enums import DecisionAction


class Decision(ContractModel):
    decision_id: NonEmptyStr
    candidate_id: NonEmptyStr
    candidate_version: PositiveVersion
    action: DecisionAction
    reason: NonEmptyStr
    triggered_by_defects: tuple[NonEmptyStr, ...] = ()
    assessment_id: NonEmptyStr
    attempt_number: NonNegativeInt = 0
    estimated_cost: NonNegativeFloat | None = None
    created_at: datetime
    metadata: Metadata = Field(default_factory=dict)

    @field_validator("action", mode="before")
    @classmethod
    def _parse_action(cls, value: DecisionAction | str) -> DecisionAction:
        return value if isinstance(value, DecisionAction) else DecisionAction(value)

    @field_validator("created_at")
    @classmethod
    def _aware_created_at(cls, value: datetime) -> datetime:
        return utc_datetime(value)
