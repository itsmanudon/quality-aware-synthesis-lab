import platform
import sys
from datetime import datetime

from pydantic import Field, field_validator, model_validator

from ._base import ContractModel, Metadata, NonEmptyStr, NonNegativeInt, utc_datetime
from .dataset import DatasetSpec
from .enums import RunStatus


class RunManifest(ContractModel):
    run_id: NonEmptyStr
    experiment_name: NonEmptyStr
    started_at: datetime
    completed_at: datetime | None = None
    status: RunStatus
    git_commit: str | None = None
    git_dirty: bool | None = None
    python_version: NonEmptyStr = sys.version.split()[0]
    platform: NonEmptyStr = platform.platform()
    config_hash: NonEmptyStr
    root_seed: NonNegativeInt
    dataset: DatasetSpec
    generator: NonEmptyStr
    artifact_schema_version: NonEmptyStr
    metadata: Metadata = Field(default_factory=dict)

    @field_validator("status", mode="before")
    @classmethod
    def _parse_status(cls, value: RunStatus | str) -> RunStatus:
        return value if isinstance(value, RunStatus) else RunStatus(value)

    @field_validator("started_at", "completed_at")
    @classmethod
    def _aware_timestamps(cls, value: datetime | None) -> datetime | None:
        return utc_datetime(value) if value else None

    @model_validator(mode="after")
    def _completion_consistency(self) -> "RunManifest":
        if self.status == RunStatus.COMPLETED and self.completed_at is None:
            raise ValueError("completed runs require completed_at")
        if self.status in {RunStatus.PENDING, RunStatus.RUNNING} and self.completed_at is not None:
            raise ValueError("pending or running runs must not have completed_at")
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at must not precede started_at")
        return self
