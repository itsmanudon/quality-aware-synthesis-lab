from pydantic import Field, model_validator

from ._base import ContractModel, Metadata, NonEmptyStr
from .provenance import ProvenanceSource


class DatasetSpec(ContractModel):
    dataset_id: NonEmptyStr
    display_name: NonEmptyStr
    task_type: NonEmptyStr
    target_column: NonEmptyStr | None = None
    feature_columns: tuple[NonEmptyStr, ...] = ()
    categorical_columns: tuple[NonEmptyStr, ...] = ()
    numerical_columns: tuple[NonEmptyStr, ...] = ()
    sensitive_columns: tuple[NonEmptyStr, ...] = ()
    reference_source: ProvenanceSource | None = None
    split_policy: NonEmptyStr | None = None
    constraints: tuple[NonEmptyStr, ...] = ()
    metadata: Metadata = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_columns(self) -> "DatasetSpec":
        groups = {
            "feature_columns": set(self.feature_columns),
            "categorical_columns": set(self.categorical_columns),
            "numerical_columns": set(self.numerical_columns),
            "sensitive_columns": set(self.sensitive_columns),
        }
        if groups["categorical_columns"] & groups["numerical_columns"]:
            raise ValueError("categorical_columns and numerical_columns must not overlap")
        for name in ("categorical_columns", "numerical_columns", "sensitive_columns"):
            if not groups[name] <= groups["feature_columns"]:
                raise ValueError(f"{name} must be a subset of feature_columns")
        if self.target_column and self.target_column in groups["feature_columns"]:
            raise ValueError("target_column must not also be a feature column")
        return self


class DatasetState(ContractModel):
    dataset_id: NonEmptyStr
    spec: DatasetSpec
    record_count: int = Field(ge=0)
    accepted_record_ids: tuple[NonEmptyStr, ...] = ()
    metadata: Metadata = Field(default_factory=dict)
