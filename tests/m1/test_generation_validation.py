from datetime import UTC, datetime
from pathlib import Path

import pytest

from rcqasyn.baselines import (
    CategoricalDomainValidator,
    MissingValueValidator,
    ObservedRangeValidator,
    SchemaValidator,
    SingleLLMJudge,
    TargetConditionValidator,
    ValidatorSuite,
)
from rcqasyn.config.experiment import JudgeConfig
from rcqasyn.contracts import CandidateRecord, Severity, Verdict
from rcqasyn.datasets import DatasetRegistry, build_profile, load_dataset, make_split
from rcqasyn.generation.parser import parse_generation_response
from rcqasyn.generation.provider import ProviderResponse, ReplayGenerator, _sanitized_endpoint


def _profile() -> tuple[object, object]:
    registry = DatasetRegistry(project_root=Path.cwd())
    spec = registry.get("dev-small")
    dataset = load_dataset(spec, registry)
    split = make_split(dataset, 42)
    return spec, build_profile(dataset, split, seed=42)


def _candidate(data: dict[str, object], record_id: str = "candidate") -> CandidateRecord:
    return CandidateRecord(
        record_id=record_id, version=1, data=data, generator_id="test", generator_version="1",
        created_at=datetime.now(UTC), metadata={"provider_call_id": "call", "requested_class": "no"},
    )


def test_replay_generator_is_deterministic_and_exhaustion_is_explicit() -> None:
    fixture = Path("tests/fixtures/replay_fixture.json")
    first = ReplayGenerator(fixture, model="fixture")
    second = ReplayGenerator(fixture, model="fixture")
    a = first.generate_batch(prompt="class no", request_index=0)
    b = second.generate_batch(prompt="class no", request_index=0)
    assert a.response == b.response and a.call_id == b.call_id
    first.generate_batch(prompt="class yes", request_index=1)
    with pytest.raises(RuntimeError, match="exhausted"):
        first.generate_batch(prompt="extra", request_index=2)


def test_provider_endpoint_sanitization_removes_userinfo_query_and_fragment() -> None:
    sanitized = _sanitized_endpoint("https://user:secret@example.test:443/v1?api_key=secret#fragment")
    assert sanitized == "https://example.test:443/v1"


def test_parser_handles_valid_malformed_wrong_shape_partial_and_raw_retention() -> None:
    valid = parse_generation_response(
        '[{"x": 1}]', run_id="r", call_id="c", generator_id="g", generator_version="1",
        prompt_version="p", seed=1, requested_class="yes",
    )
    assert valid.candidates[0].metadata["requested_class"] == "yes"
    malformed = parse_generation_response(
        "not-json", run_id="r", call_id="c2", generator_id="g", generator_version="1",
        prompt_version="p", seed=1,
    )
    assert malformed.failures[0].raw_output == "not-json"
    wrong_shape = parse_generation_response(
        '{"x": 1}', run_id="r", call_id="c3", generator_id="g", generator_version="1",
        prompt_version="p", seed=1,
    )
    assert "array" in wrong_shape.failures[0].error
    partial = parse_generation_response(
        '[{"x": 1}, 5]', run_id="r", call_id="c4", generator_id="g", generator_version="1",
        prompt_version="p", seed=1,
    )
    assert len(partial.candidates) == 1 and partial.failures[0].item_index == 1
    assert partial.candidates[0].raw_output == '[{"x": 1}, 5]'


def test_public_validators_emit_expected_evidence_and_range_is_warn() -> None:
    spec, profile = _profile()
    complete = {"age": 30, "score": 0.5, "color": "red", "label": "no"}
    schema = SchemaValidator(spec, profile)
    assert schema.validate(_candidate({"age": 30, "score": 0.5, "color": "red"}))[0].verdict == Verdict.FAIL
    category = CategoricalDomainValidator(spec, profile).validate(_candidate({**complete, "color": "purple"}))[0]
    assert category.severity == Severity.HIGH and category.verdict == Verdict.FAIL
    missing = MissingValueValidator(spec, profile).validate(_candidate({**complete, "score": None}))[0]
    assert missing.verdict == Verdict.WARN
    target = TargetConditionValidator(spec, profile).validate(_candidate(complete), expected_class="yes")[0]
    assert target.verdict == Verdict.FAIL and target.severity == Severity.HIGH
    out_of_range = ObservedRangeValidator(spec, profile).validate(_candidate({**complete, "age": 999}))[0]
    assert out_of_range.verdict == Verdict.WARN
    suite = ValidatorSuite(spec, profile)
    assert any(item.validator_id == "target-condition" for item in suite.validate(_candidate(complete), expected_class="yes"))


def test_single_judge_parses_structured_result_and_marks_confidence_uncalibrated() -> None:
    class FakeProvider:
        def call(self, **_: object) -> ProviderResponse:
            return ProviderResponse(
                response='{"score": 0.8, "verdict": "pass", "reasons": ["plausible"], "affected_fields": [], "self_confidence": 0.9}',
                provider="fake", model="fake", endpoint=None, call_id="judge-call",
            )

    judge = SingleLLMJudge(FakeProvider(), threshold=0.7)
    evaluation = judge.evaluate(prompt="judge", run_id="r", candidate_id="c", request_index=0, seed=1, max_tokens=20)
    assert evaluation.result is not None
    assert evaluation.result.confidence_calibration == "uncalibrated"
    assert judge.accepts(evaluation.result)
    class MalformedProvider:
        def call(self, **_: object) -> ProviderResponse:
            return ProviderResponse(response="not-json", provider="fake", model="fake", endpoint=None, call_id="bad")

    malformed = SingleLLMJudge(MalformedProvider(), threshold=0.7).evaluate(
        prompt="judge", run_id="r", candidate_id="c", request_index=0, seed=1, max_tokens=20,
    )
    assert malformed.result is None and malformed.error is not None
    with pytest.raises(ValueError, match="only 'reject'"):
        JudgeConfig.model_validate({"threshold": 0.7, "malformed_policy": "retry"})
