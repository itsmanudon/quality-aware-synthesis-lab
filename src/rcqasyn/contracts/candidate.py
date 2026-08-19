from datetime import datetime

from pydantic import Field, field_validator

from ._base import (
    ContractModel,
    JsonValue,
    Metadata,
    NonEmptyStr,
    NonNegativeInt,
    PositiveVersion,
    utc_datetime,
)
from .provenance import ProvenanceSource


class CandidateRecord(ContractModel):
    record_id: NonEmptyStr
    version: PositiveVersion
    data: dict[str, JsonValue]
    raw_output: str | None = None
    generator_id: NonEmptyStr
    generator_version: NonEmptyStr
    prompt_version: NonEmptyStr | None = None
    seed: NonNegativeInt | None = None
    created_at: datetime
    parent_record_id: NonEmptyStr | None = None
    metadata: Metadata = Field(default_factory=dict)
    provenance: tuple[ProvenanceSource, ...] = ()

    @field_validator("created_at")
    @classmethod
    def _aware_created_at(cls, value: datetime) -> datetime:
        return utc_datetime(value)
