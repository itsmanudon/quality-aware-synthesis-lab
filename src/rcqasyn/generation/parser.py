from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from rcqasyn.contracts import CandidateRecord, JudgeResult, ParseFailureEvent


@dataclass(frozen=True)
class ParsedCandidates:
    candidates: tuple[CandidateRecord, ...]
    failures: tuple[ParseFailureEvent, ...]


def parse_generation_response(raw: str, *, run_id: str, call_id: str, generator_id: str, generator_version: str,
                              prompt_version: str | None, seed: int | None,
                              requested_class: str | None = None,
                              requested_count: int | None = None,
                              transport_version: str = "v1") -> ParsedCandidates:
    now = datetime.now(UTC)
    try:
        parsed = _decode_json(raw)
    except ValueError as error:
        return ParsedCandidates((), (_failure(run_id, call_id, raw, str(error), False, None, now, requested_class, requested_count, transport_version),))
    if isinstance(parsed, dict) and isinstance(parsed.get("records"), list):
        parsed = parsed["records"]
    if not isinstance(parsed, list):
        expected = "JSON object with a records array" if transport_version == "v2" else "JSON array"
        return ParsedCandidates((), (_failure(run_id, call_id, raw, f"expected {expected}", False, None, now, requested_class, requested_count, transport_version),))
    candidates: list[CandidateRecord] = []
    failures: list[ParseFailureEvent] = []
    for index, item in enumerate(parsed):
        if not isinstance(item, dict):
            failures.append(_failure(run_id, call_id, raw, "array item must be an object", True, index, now, requested_class, requested_count, transport_version))
            continue
        try:
            candidates.append(CandidateRecord(
                record_id=f"{call_id}-item-{index}", version=1, data=_jsonable(item), raw_output=raw,
                generator_id=generator_id, generator_version=generator_version, prompt_version=prompt_version,
                seed=seed, created_at=now,
                metadata={
                    "provider_call_id": call_id,
                    "item_index": index,
                    **({"requested_class": requested_class} if requested_class is not None else {}),
                    **({"requested_count": requested_count} if requested_count is not None else {}),
                },
            ))
        except (TypeError, ValueError) as error:
            failures.append(_failure(run_id, call_id, raw, f"candidate contract error: {error}", True, index, now, requested_class, requested_count, transport_version))
    return ParsedCandidates(tuple(candidates), tuple(failures))


def parse_judge_response(raw: str, *, run_id: str, candidate_id: str, judge_call_id: str) -> JudgeResult:
    parsed = _decode_json(raw)
    if not isinstance(parsed, dict):
        raise ValueError("judge output must be a JSON object")  # noqa: TRY004
    score = parsed.get("score")
    verdict = parsed.get("verdict")
    reasons = parsed.get("reasons", [])
    fields = parsed.get("affected_fields", [])
    confidence = parsed.get("self_confidence")
    if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= float(score) <= 1:
        raise ValueError("judge score must be a number in [0, 1]")
    if verdict not in {"pass", "fail", "warn", "unknown"}:
        raise ValueError("judge verdict must be pass/fail/warn/unknown")
    if not isinstance(reasons, list) or not all(isinstance(item, str) and item.strip() for item in reasons):
        raise ValueError("judge reasons must be an array of non-empty strings")
    if not isinstance(fields, list) or not all(isinstance(item, str) and item.strip() for item in fields):
        raise ValueError("judge affected_fields must be an array of non-empty strings")
    if confidence is not None and (not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1):
        raise ValueError("judge self_confidence must be in [0, 1]")
    return JudgeResult(
        result_id=f"judge-{candidate_id}", run_id=run_id, candidate_id=candidate_id, judge_call_id=judge_call_id,
        score=float(score), verdict=verdict, reasons=tuple(reasons), affected_fields=tuple(fields),
        self_confidence=float(confidence) if confidence is not None else None, created_at=datetime.now(UTC),
    )


def _decode_json(raw: str) -> Any:
    text = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        raise ValueError(f"malformed JSON: {error.msg}") from error


def _failure(run_id: str, call_id: str, raw: str, error: str, recoverable: bool, item_index: int | None, now: datetime,
             requested_class: str | None = None, requested_count: int | None = None, transport_version: str = "v1") -> ParseFailureEvent:
    suffix = f"-{item_index}" if item_index is not None else ""
    return ParseFailureEvent(
        event_id=f"parse-{call_id}{suffix}", run_id=run_id, call_id=call_id,
        parser_version="json-wrapper-v2" if transport_version == "v2" else "json-array-v1",
        raw_output=raw, error=error, recoverable=recoverable, item_index=item_index, created_at=now,
        metadata={key: value for key, value in (
            ("requested_class", requested_class), ("requested_count", requested_count)
        ) if value is not None},
    )


def _jsonable(values: dict[str, Any]) -> dict[str, Any]:
    return {str(key): _jsonable_value(value) for key, value in values.items()}


def _jsonable_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable_value(item) for item in value]
    return value
