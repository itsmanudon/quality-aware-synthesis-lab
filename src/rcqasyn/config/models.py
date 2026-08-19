from pathlib import Path

from pydantic import ConfigDict, Field, StrictInt, field_validator

from rcqasyn.contracts._base import ContractModel, NonEmptyStr


class ProjectConfig(ContractModel):
    name: NonEmptyStr
    seed: StrictInt = Field(ge=0)


class ArtifactsConfig(ContractModel):
    root: Path

    @field_validator("root", mode="before")
    @classmethod
    def _parse_path(cls, value: Path | str) -> Path:
        return value if isinstance(value, Path) else Path(value)


class LiteratureConfig(ContractModel):
    papers_dir: Path
    notes_dir: Path

    @field_validator("papers_dir", "notes_dir", mode="before")
    @classmethod
    def _parse_path(cls, value: Path | str) -> Path:
        return value if isinstance(value, Path) else Path(value)


class Config(ContractModel):
    project: ProjectConfig
    artifacts: ArtifactsConfig
    literature: LiteratureConfig


class ResolvedConfig(Config):
    model_config = ConfigDict(strict=True, extra="forbid", validate_assignment=True, arbitrary_types_allowed=True)
    project_root: Path
    config_path: Path
