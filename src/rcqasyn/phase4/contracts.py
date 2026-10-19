from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from rcqasyn.contracts._base import ContractModel, NonEmptyStr
from rcqasyn.phase2.common import digest
from rcqasyn.phase2.contracts import Hex32

PARENT = "c47cccb54c2c1cc4f2eff4cb2f83489a0e02b855"
STATISTICAL = ("local_support", "cross_feature")
FAMILIES = ("authoritative_structure", *STATISTICAL)
ACTIONS = ("REJECT_STRUCTURAL", "REVIEW_REQUIRED", "PROVISIONAL_PASS", "ABSTAIN")


class Policy(ContractModel):
    schema_version: Literal["shadow-policy-v1"] = "shadow-policy-v1"
    name: NonEmptyStr
    families: tuple[Literal["local_support", "cross_feature"], ...] = ()
    review_cutoff: float = Field(default=0.9, gt=0, lt=1, allow_inf_nan=False)
    combination: Literal["union-max-uncalibrated-v1"] = "union-max-uncalibrated-v1"

    @model_validator(mode="after")
    def unique(self) -> Policy:
        if len(set(self.families)) != len(self.families):
            raise ValueError("duplicate required family")
        return self


class EvidenceVector(ContractModel):
    schema_version: Literal["m4-evidence-vector-v1"] = "m4-evidence-vector-v1"
    occurrence_id: NonEmptyStr
    payload_sha256: Hex32
    dataset_id: NonEmptyStr
    m2_bundle_fingerprint: Hex32
    specification_fingerprint: Hex32
    train_reference_fingerprint: Hex32
    m2_configuration_fingerprint: Hex32
    input_evidence_fingerprints: dict[str, str]
    structural: dict[str, Any]
    normalized: dict[str, Any]
    family_reasons: dict[str, Any]
    fusion: dict[str, Any]
    calibration_status: Literal["NOT_ELIGIBLE_UNAPPROVED_LABELS"] = "NOT_ELIGIBLE_UNAPPROVED_LABELS"

    @model_validator(mode="after")
    def finite(self) -> EvidenceVector:
        digest(self.model_dump(mode="python"))
        if set(self.input_evidence_fingerprints) != set(FAMILIES):
            raise ValueError("incomplete input families")
        if set(self.normalized) != set(STATISTICAL):
            raise ValueError("incomplete statistical vector")
        return self
