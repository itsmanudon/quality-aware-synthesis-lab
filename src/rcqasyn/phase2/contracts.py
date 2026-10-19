from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

from rcqasyn.contracts._base import ContractModel, NonEmptyStr, PositiveInt

FREEZE = "341fc2ce647c180b0f4a34fdbdeb49a0acfdcbcc"
CROSSWALK = "legacy-occurrence-crosswalk-v1"
COHORT = "review-cohort-v2"
PROTOCOL = "annotation-protocol-v1"
type Label = Literal["VALID", "INVALID", "INDETERMINATE"]


class Locator(ContractModel):
    artifact: NonEmptyStr
    sha256: NonEmptyStr
    line: PositiveInt


class Occurrence(ContractModel):
    crosswalk_version: Literal["legacy-occurrence-crosswalk-v1"] = CROSSWALK
    occurrence_id: NonEmptyStr
    legacy_candidate_id: NonEmptyStr
    dataset_id: NonEmptyStr
    source_execution_id: NonEmptyStr
    source_artifact: NonEmptyStr
    source_artifact_sha256: NonEmptyStr
    source_manifest_sha256: NonEmptyStr
    source_attempt_id_or_evidenced_locator: Locator
    source_occurrence_ordinal: PositiveInt
    response_ordinal: PositiveInt
    item_index: int = Field(ge=0)
    payload: dict[str, Any]
    payload_sha256: NonEmptyStr
    recorded_payload_sha256: NonEmptyStr
    raw_response_sha256: NonEmptyStr
    generation_metadata: dict[str, Any]
    controls: dict[str, Any]
    diagnostics: dict[str, Any]
    binding_status: Literal["VERIFIED"] = "VERIFIED"
    reconciliation_notes: str = "Legacy ID is an alias; trace locator is not a durable attempt ID."


class Rule(ContractModel):
    rule_id: NonEmptyStr
    authority: Literal["AUTHORITATIVE", "INFERRED", "UNVERIFIED"]
    statement: NonEmptyStr
    evidence: tuple[str, ...] = ()
    hard_rejection_allowed: bool = False

    @model_validator(mode="after")
    def authority_required(self) -> Rule:
        if self.authority == "AUTHORITATIVE" and not self.evidence:
            raise ValueError("authoritative rules require source evidence")
        if self.hard_rejection_allowed and self.authority != "AUTHORITATIVE":
            raise ValueError("unsupported hard rule")
        return self


class DatasetSpecification(ContractModel):
    specification_version: Literal["dataset-specification-v1"] = "dataset-specification-v1"
    dataset_id: NonEmptyStr
    source_identity: dict[str, Any]
    original_task: dict[str, Any]
    target_semantics: dict[str, Any]
    features: tuple[dict[str, Any], ...]
    missing_policy: NonEmptyStr
    rules: tuple[Rule, ...]
    train_profile: dict[str, Any]
    split_provenance: dict[str, Any]
    ambiguity: tuple[str, ...]
    evaluation_applicability: NonEmptyStr
    documentation_references: tuple[str, ...]
    status: Literal["DRAFT_REQUIRES_SUPERVISOR_APPROVAL"] = "DRAFT_REQUIRES_SUPERVISOR_APPROVAL"


class GateAApproval(ContractModel):
    cohort_fingerprint: NonEmptyStr
    crosswalk_fingerprints: tuple[str, ...]
    protocol_fingerprint: NonEmptyStr
    supervisor_reference: NonEmptyStr
    supervisor_approval_provenance: NonEmptyStr
    independent_verifier_reference: NonEmptyStr
    independent_verification_provenance: NonEmptyStr
    implementation_owner_reference: NonEmptyStr
    decision: Literal["APPROVED"]
    personnel_independent: Literal[True]

    @model_validator(mode="after")
    def independent(self) -> GateAApproval:
        if self.independent_verifier_reference == self.implementation_owner_reference:
            raise ValueError("implementation owner cannot independently verify Gate A")
        return self


class Proposal(ContractModel):
    review_row_id: NonEmptyStr
    occurrence_id: NonEmptyStr
    dataset_id: NonEmptyStr
    payload_sha256: NonEmptyStr
    protocol_version: Literal["annotation-protocol-v1"] = PROTOCOL
    proposed_label: Label
    proposed_rationale: NonEmptyStr
    supporting_evidence_ids: tuple[str, ...]
    uncertainty_or_ambiguity: NonEmptyStr
    annotator_type: Literal["AGENT"] = "AGENT"
    annotator_model_or_agent_version: NonEmptyStr
    proposal_timestamp_or_execution_identity: NonEmptyStr
    review_status: Literal["PENDING_HUMAN_APPROVAL"] = "PENDING_HUMAN_APPROVAL"
    human_final_label: None = None
    human_correction_note: None = None
    human_reviewer_reference: None = None
    human_approval_provenance: None = None

    @model_validator(mode="after")
    def evidence_required(self) -> Proposal:
        if self.proposed_label != "INDETERMINATE" and not self.supporting_evidence_ids:
            raise ValueError("a determinate proposal requires evidence")
        return self


class HumanDecision(ContractModel):
    review_row_id: NonEmptyStr
    occurrence_id: NonEmptyStr
    payload_sha256: NonEmptyStr
    proposal_fingerprint: NonEmptyStr
    review_status: Literal["SUBMITTED", "APPROVED", "UNRESOLVED"]
    human_final_label: Label | None = None
    human_correction_note: str = ""
    human_reviewer_reference: NonEmptyStr
    human_approval_provenance: NonEmptyStr

    @model_validator(mode="after")
    def explicit_decision(self) -> HumanDecision:
        if self.review_status == "APPROVED" and self.human_final_label is None:
            raise ValueError("approval requires an explicit final label")
        if self.review_status == "UNRESOLVED" and self.human_final_label is not None:
            raise ValueError("unresolved is not an approved label")
        return self

# These approval-specific contracts do not change the frozen cohort or protocol.
type Hex32 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
type Hex64 = Annotated[str, Field(pattern=r"^[0-9a-f]{128}$")]


class ApprovalLedger(ContractModel):
    schema_version: Literal["supervisor-approval-ledger-v1"] = "supervisor-approval-ledger-v1"
    phase1_freeze_sha: Literal["341fc2ce647c180b0f4a34fdbdeb49a0acfdcbcc"] = FREEZE
    cohort_fingerprint: NonEmptyStr
    crosswalk_fingerprints: tuple[str, ...]
    protocol_version: Literal["annotation-protocol-v1"]
    protocol_fingerprint: NonEmptyStr
    gate_a_approval_fingerprint: NonEmptyStr
    population_kind: Literal["research", "synthetic_fixture"]
    proposal_ledger_fingerprint: NonEmptyStr
    reviewer_reference: NonEmptyStr
    correction_history_tip: NonEmptyStr
    correction_history_fingerprints: tuple[str, ...]
    decisions: tuple[HumanDecision, ...]


class DetachedSupervisorSignature(ContractModel):
    schema_version: Literal["supervisor-signature-v1"] = "supervisor-signature-v1"
    key_id: Hex32
    signature_hex: Hex64


class SupervisorAttestation(ContractModel):
    schema_version: Literal["supervisor-attestation-v1"] = "supervisor-attestation-v1"
    ledger: ApprovalLedger
    signature: DetachedSupervisorSignature


class SupervisorTrust(ContractModel):
    schema_version: Literal["supervisor-trust-v1"] = "supervisor-trust-v1"
    reviewer_reference: NonEmptyStr
    key_id: Hex32
    public_key_hex: Hex32


class SupervisorEnrollment(ContractModel):
    """Public offline enrollment record; never itself a production capability."""

    schema_version: Literal["offline-supervisor-enrollment-v1"] = "offline-supervisor-enrollment-v1"
    deployment_status: Literal["PENDING_PROTECTED_DEPLOYMENT"] = "PENDING_PROTECTED_DEPLOYMENT"
    trust: SupervisorTrust
    expected_key_id: Hex32
    expected_history_tip: Hex32

    @model_validator(mode="after")
    def pinned_key(self) -> SupervisorEnrollment:
        from hashlib import sha256

        actual = sha256(bytes.fromhex(self.trust.public_key_hex)).hexdigest()
        if actual != self.trust.key_id or actual != self.expected_key_id:
            raise ValueError("supervisor public key differs from independently established pin")
        return self
