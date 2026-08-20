from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
type JsonValue = dict[str, "JsonValue"] | list["JsonValue"] | str | int | float | bool | None
type Metadata = dict[str, JsonValue]


class ContractModel(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        validate_assignment=True,
        use_enum_values=True,
    )


def utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC)


Score = Annotated[float, Field(ge=0.0, le=1.0)]
NonNegativeFloat = Annotated[float, Field(ge=0.0)]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveVersion = Annotated[int, Field(gt=0)]
PositiveInt = Annotated[int, Field(gt=0)]
