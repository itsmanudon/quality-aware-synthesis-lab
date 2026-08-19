from datetime import datetime

from pydantic import Field, field_validator

from ._base import ContractModel, Metadata, NonEmptyStr, utc_datetime
from .enums import SourceType


class ProvenanceSource(ContractModel):
    source_id: NonEmptyStr
    source_type: SourceType
    uri: str | None = None
    reference: str | None = None
    title: str | None = None
    version: NonEmptyStr | None = None
    retrieved_at: datetime | None = None
    content_hash: str | None = None
    metadata: Metadata = Field(default_factory=dict)

    @field_validator("source_type", mode="before")
    @classmethod
    def _parse_source_type(cls, value: SourceType | str) -> SourceType:
        return value if isinstance(value, SourceType) else SourceType(value)

    @field_validator("retrieved_at")
    @classmethod
    def _aware_retrieved_at(cls, value: datetime | None) -> datetime | None:
        return utc_datetime(value) if value is not None else None
