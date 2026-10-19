from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from rcqasyn.contracts._base import ContractModel, NonEmptyStr
from rcqasyn.phase2.common import digest
from rcqasyn.phase2.contracts import Hex32

PARENT = "6c4634fabd2f8cba2ed7365b0b9559c3df17055a"


class M2Config(ContractModel):
    schema_version: Literal["m2-config-v1"] = "m2-config-v1"
    k: int = Field(default=5, ge=1)
    shrinkage: float = Field(default=0.1, gt=0, le=1)
    ridge: float = Field(default=1e-8, gt=0)
    seed: int = Field(default=42, ge=0)


class M2Evidence(ContractModel):
    schema_version: Literal["m2-evidence-v1"] = "m2-evidence-v1"
    occurrence_id: NonEmptyStr
    payload_sha256: Hex32
    dataset_id: NonEmptyStr
    specification_fingerprint: Hex32
    validator_family: Literal["authoritative_structure", "local_support", "cross_feature"]
    validator_version: Literal["1"] = "1"
    status: Literal["AVAILABLE", "PARTIAL", "UNAVAILABLE"]
    authoritative_validity: Literal["INVALID", "NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    raw_score: float | None = Field(default=None, allow_inf_nan=False)
    quantities: dict[str, Any] = Field(default_factory=dict)
    reason_codes: tuple[str, ...] = ()
    unsupported_fields: tuple[str, ...] = ()
    rule_or_model_evidence: dict[str, Any] = Field(default_factory=dict)
    reference_fingerprint: Hex32
    configuration_fingerprint: Hex32
    uncertainty: NonEmptyStr

    @model_validator(mode="after")
    def separate_statistics(self) -> M2Evidence:
        if self.validator_family != "authoritative_structure" and self.authoritative_validity != "NOT_ESTABLISHED":
            raise ValueError("statistical evidence cannot declare record invalidity")
        if self.status == "UNAVAILABLE" and self.raw_score is not None:
            raise ValueError("unavailable evidence cannot invent a score")
        digest(self.model_dump(mode="python"))  # Reject nonfinite nested diagnostic quantities too.
        return self
