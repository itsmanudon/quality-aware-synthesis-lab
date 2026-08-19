from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from rcqasyn.contracts import (
    Assessment,
    CandidateRecord,
    DatasetSpec,
    Decision,
    DecisionAction,
    Evidence,
    ProvenanceSource,
    QualityDimension,
    Severity,
    SourceType,
    Verdict,
)

NOW = datetime(2025, 1, 1, tzinfo=UTC)


def test_candidate_evidence_json_round_trip_and_evidence_frozen() -> None:
    source = ProvenanceSource(source_id="paper-1", source_type="paper", reference="local.pdf")
    candidate = CandidateRecord(
        record_id="record-1",
        version=2,
        data={"label": "ok", "count": 2},
        generator_id="generator",
        generator_version="0.1",
        created_at=NOW,
        provenance=(source,),
    )
    evidence = Evidence(
        evidence_id="e-1",
        candidate_id="record-1",
        candidate_version=2,
        validator_id="schema",
        validator_version="1",
        dimension=QualityDimension.SCHEMA_VALIDITY,
        verdict=Verdict.PASS,
        severity=Severity.INFO,
        message="valid",
        created_at=NOW,
    )
    assert CandidateRecord.model_validate_json(candidate.model_dump_json()) == candidate
    assert Evidence.model_validate_json(evidence.model_dump_json()) == evidence
    with pytest.raises(ValidationError):
        evidence.message = "mutated"


def test_contracts_keep_quality_risk_uncertainty_separate() -> None:
    assessment = Assessment(
        assessment_id="assessment-1",
        candidate_id="record-1",
        candidate_version=2,
        quality_scores={QualityDimension.FACTUAL_VALIDITY: 0.8},
        risk_scores={QualityDimension.FACTUAL_VALIDITY: 0.2},
        uncertainty_scores={QualityDimension.FACTUAL_VALIDITY: 0.4},
        hard_constraints_passed=True,
        critical_risk=False,
        created_at=NOW,
    )
    assert len(Assessment.model_fields) >= 3
    assert assessment.quality_scores != assessment.risk_scores
    assert Assessment.model_validate_json(assessment.model_dump_json()).candidate_version == 2


def test_bounds_versions_and_dataset_column_validation() -> None:
    with pytest.raises(ValidationError):
        Evidence(
            evidence_id="e",
            candidate_id="c",
            candidate_version=2,
            validator_id="v",
            validator_version="1",
            dimension="schema_validity",
            verdict="pass",
            severity="info",
            score=1.1,
            message="bad",
            created_at=NOW,
        )
    with pytest.raises(ValidationError):
        DatasetSpec(
            dataset_id="d",
            display_name="D",
            task_type="classification",
            feature_columns=("x",),
            categorical_columns=("x",),
            numerical_columns=("x",),
        )
    decision = Decision(
        decision_id="d-1",
        candidate_id="c",
        candidate_version=2,
        action=DecisionAction.ACCEPT,
        reason="ok",
        assessment_id="a",
        created_at=NOW,
    )
    assert decision.action == DecisionAction.ACCEPT
    assert Decision.model_validate_json(decision.model_dump_json()).candidate_version == 2


def test_candidate_versions_are_positive_strict_integers() -> None:
    base = {
        "record_id": "record-1",
        "data": {"x": 1},
        "generator_id": "generator",
        "generator_version": "0.1",
        "created_at": NOW,
    }
    for invalid in (0, -1, True, "2"):
        with pytest.raises(ValidationError):
            CandidateRecord(version=invalid, **base)
    candidate = CandidateRecord(version=2, **base)
    assert CandidateRecord.model_validate_json(candidate.model_dump_json()).version == 2


def test_non_web_provenance_is_optional_reference_and_round_trips() -> None:
    for source_type in (
        SourceType.REFERENCE_DATASET,
        SourceType.KNOWLEDGE_BASE,
        SourceType.DOCUMENT,
        SourceType.API,
        SourceType.DETERMINISTIC_RULE,
        SourceType.HUMAN_ANNOTATION,
        SourceType.EXTERNAL_DATABASE,
    ):
        source = ProvenanceSource(source_id=f"source-{source_type}", source_type=source_type)
        assert ProvenanceSource.model_validate_json(source.model_dump_json()) == source


def test_decision_action_values_are_exact() -> None:
    assert {action.value for action in DecisionAction} == {
        "accept",
        "repair",
        "revalidate",
        "regenerate",
        "reject",
    }
