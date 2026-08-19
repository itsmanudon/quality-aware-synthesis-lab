from pydantic import Field

from ._base import ContractModel, Metadata, NonEmptyStr


class ValidationContext(ContractModel):
    run_id: NonEmptyStr | None = None
    dataset_id: NonEmptyStr
    reference_sources: tuple[NonEmptyStr, ...] = ()
    metadata: Metadata = Field(default_factory=dict)
