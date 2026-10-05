from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, cast

from rcqasyn.contracts import (
    CandidateRecord,
    Evidence,
    Metadata,
    QualityDimension,
    Severity,
    ValidationContext,
    Verdict,
)
from rcqasyn.datasets import DatasetDefinition


class ValidatorProfile(Protocol):
    @property
    def domains(self) -> dict[str, tuple[str, ...]]: ...

    @property
    def numeric_summary(self) -> dict[str, dict[str, float]]: ...


class _BaseValidator:
    validator_id = "validator"

    def __init__(self, spec: DatasetDefinition, profile: ValidatorProfile) -> None:
        self.spec = spec
        self.profile = profile

    def _evidence(
        self,
        candidate: CandidateRecord,
        dimension: QualityDimension,
        verdict: Verdict,
        severity: Severity,
        message: str,
        *,
        fields: tuple[str, ...] = (),
        metadata: Metadata | None = None,
    ) -> Evidence:
        return Evidence(
            evidence_id=f"{self.validator_id}-{candidate.record_id}",
            candidate_id=candidate.record_id,
            candidate_version=candidate.version,
            validator_id=self.validator_id,
            validator_version="1",
            dimension=dimension,
            verdict=verdict,
            severity=severity,
            affected_fields=fields,
            message=message,
            created_at=datetime.now(UTC),
            metadata=metadata or {},
        )


class SchemaValidator(_BaseValidator):
    """Check exactly the declared feature/target columns and primitive types."""

    validator_id = "schema"

    def validate(self, candidate: CandidateRecord, context: ValidationContext | None = None) -> tuple[Evidence, ...]:
        expected = set(self.spec.feature_columns) | {self.spec.target_column}
        actual = set(candidate.data)
        missing = tuple(sorted(expected - actual))
        unknown = tuple(sorted(actual - expected))
        fields = tuple(sorted(set(missing) | set(unknown)))
        if missing or unknown:
            return (self._evidence(
                candidate, QualityDimension.SCHEMA_VALIDITY, Verdict.FAIL, Severity.HIGH,
                f"schema mismatch; missing={list(missing)}, unknown={list(unknown)}",
                fields=fields, metadata={"missing_fields": list(missing), "unknown_fields": list(unknown)},
            ),)
        bad_numeric = tuple(
            column for column in self.spec.numerical_columns
            if candidate.data.get(column) is not None
            and (not isinstance(candidate.data.get(column), (int, float)) or isinstance(candidate.data.get(column), bool))
        )
        if bad_numeric:
            return (self._evidence(
                candidate, QualityDimension.SCHEMA_VALIDITY, Verdict.FAIL, Severity.HIGH,
                "numeric field has non-numeric value", fields=bad_numeric,
                metadata={"type_error_fields": list(bad_numeric)},
            ),)
        return (self._evidence(
            candidate, QualityDimension.SCHEMA_VALIDITY, Verdict.PASS, Severity.INFO,
            "declared schema present",
        ),)


class CategoricalDomainValidator(_BaseValidator):
    """Reject categorical values outside domains observed in TRAIN."""

    validator_id = "categorical-domain"

    def validate(self, candidate: CandidateRecord, context: ValidationContext | None = None) -> tuple[Evidence, ...]:
        invalid: list[str] = []
        for column in [*self.spec.categorical_columns, self.spec.target_column]:
            value = candidate.data.get(column)
            if value is not None and column in self.profile.domains and str(value) not in self.profile.domains[column]:
                invalid.append(column)
        if invalid:
            return (self._evidence(
                candidate, QualityDimension.CONSTRAINT_VALIDITY, Verdict.FAIL, Severity.HIGH,
                "categorical value outside TRAIN observed domain", fields=tuple(invalid),
                metadata=cast(Metadata, {"invalid_fields": invalid}),
            ),)
        return (self._evidence(
            candidate, QualityDimension.CONSTRAINT_VALIDITY, Verdict.PASS, Severity.INFO,
            "categorical values in TRAIN domains",
        ),)


class MissingValueValidator(_BaseValidator):
    """Apply the dataset's declared missing-value policy without imputing."""

    validator_id = "missing"

    def validate(self, candidate: CandidateRecord, context: ValidationContext | None = None) -> tuple[Evidence, ...]:
        missing = tuple(column for column in [*self.spec.feature_columns, self.spec.target_column] if candidate.data.get(column) is None)
        if missing and self.spec.missing_policy == "reject":
            return (self._evidence(
                candidate, QualityDimension.SCHEMA_VALIDITY, Verdict.FAIL, Severity.HIGH,
                "missing values are rejected by dataset policy", fields=missing,
                metadata={"missing_fields": list(missing)},
            ),)
        if missing:
            return (self._evidence(
                candidate, QualityDimension.SCHEMA_VALIDITY, Verdict.WARN, Severity.MEDIUM,
                "missing values preserved under dataset policy", fields=missing,
                metadata={"missing_fields": list(missing)},
            ),)
        return (self._evidence(
            candidate, QualityDimension.SCHEMA_VALIDITY, Verdict.PASS, Severity.INFO,
            "no missing declared fields",
        ),)


class TargetConditionValidator(_BaseValidator):
    """Check a candidate's target against the concrete class requested by generation."""

    validator_id = "target-condition"

    def validate(self, candidate: CandidateRecord, expected_class: str | None = None,
                 context: ValidationContext | None = None) -> tuple[Evidence, ...]:
        value = candidate.data.get(self.spec.target_column)
        if expected_class is not None and str(value) != str(expected_class):
            return (self._evidence(
                candidate, QualityDimension.CONSTRAINT_VALIDITY, Verdict.FAIL, Severity.HIGH,
                f"target class {value!r} does not match requested {expected_class!r}",
                fields=(self.spec.target_column,),
                metadata={"expected_class": expected_class, "observed_class": None if value is None else str(value)},
            ),)
        return (self._evidence(
            candidate, QualityDimension.CONSTRAINT_VALIDITY, Verdict.PASS, Severity.INFO,
            "target condition satisfied", fields=(self.spec.target_column,),
        ),)


class ObservedRangeValidator(_BaseValidator):
    """Diagnostic observed-range check; WARN is intentionally not rejected by default."""

    validator_id = "observed-range"

    def __init__(self, spec: DatasetDefinition, profile: ValidatorProfile, *, severity: Severity = Severity.MEDIUM) -> None:
        super().__init__(spec, profile)
        self.severity = severity

    def validate(self, candidate: CandidateRecord, context: ValidationContext | None = None) -> tuple[Evidence, ...]:
        out: list[str] = []
        for column, summary in self.profile.numeric_summary.items():
            value = candidate.data.get(column)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and (value < summary["min"] or value > summary["max"]):
                out.append(column)
        if out:
            return (self._evidence(
                candidate, QualityDimension.CONSTRAINT_VALIDITY, Verdict.WARN, self.severity,
                "numeric value outside observed TRAIN range (diagnostic only by default)", fields=tuple(out),
                metadata=cast(Metadata, {"observed_range_violation_fields": out}),
            ),)
        return (self._evidence(
            candidate, QualityDimension.CONSTRAINT_VALIDITY, Verdict.PASS, Severity.INFO,
            "numeric values within observed TRAIN range",
        ),)


class ValidatorSuite:
    """Compose independent deterministic validators used by B2."""

    def __init__(self, spec: DatasetDefinition, profile: ValidatorProfile, *, range_severity: Severity = Severity.MEDIUM) -> None:
        self.schema = SchemaValidator(spec, profile)
        self.categorical = CategoricalDomainValidator(spec, profile)
        self.missing = MissingValueValidator(spec, profile)
        self.target = TargetConditionValidator(spec, profile)
        self.observed_range = ObservedRangeValidator(spec, profile, severity=range_severity)

    def validate(self, candidate: CandidateRecord, *, expected_class: str | None = None) -> tuple[Evidence, ...]:
        context = ValidationContext(dataset_id=self.schema.spec.dataset_id)
        evidence: list[Evidence] = []
        evidence.extend(self.schema.validate(candidate, context))
        evidence.extend(self.categorical.validate(candidate, context))
        evidence.extend(self.missing.validate(candidate, context))
        evidence.extend(self.target.validate(candidate, expected_class, context))
        evidence.extend(self.observed_range.validate(candidate, context))
        return tuple(evidence)


def rejects(evidence: tuple[Evidence, ...], severities: frozenset[Severity]) -> bool:
    return any(item.verdict in {Verdict.FAIL, Verdict.WARN} and item.severity in severities for item in evidence)


__all__ = [
    "CategoricalDomainValidator",
    "MissingValueValidator",
    "ObservedRangeValidator",
    "SchemaValidator",
    "TargetConditionValidator",
    "ValidatorSuite",
    "rejects",
]
