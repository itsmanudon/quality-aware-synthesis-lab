
from pydantic import Field

from ._base import ContractModel, JsonValue, Metadata, NonEmptyStr, NonNegativeInt
from .candidate import CandidateRecord


class GenerationContext(ContractModel):
    run_id: NonEmptyStr | None = None
    dataset_id: NonEmptyStr
    constraints: tuple[NonEmptyStr, ...] = ()
    metadata: Metadata = Field(default_factory=dict)


class GenerationRequest(ContractModel):
    request_id: NonEmptyStr
    generator_id: NonEmptyStr
    generator_version: NonEmptyStr
    prompt_version: NonEmptyStr | None = None
    context: GenerationContext
    seed: NonNegativeInt | None = None
    inputs: dict[str, JsonValue] = Field(default_factory=dict)
    metadata: Metadata = Field(default_factory=dict)


class RepairRequest(ContractModel):
    request_id: NonEmptyStr
    candidate: CandidateRecord
    defect_ids: tuple[NonEmptyStr, ...] = ()
    instructions: tuple[NonEmptyStr, ...] = ()
    attempt_number: NonNegativeInt = 0
    seed: NonNegativeInt | None = None
    metadata: Metadata = Field(default_factory=dict)
