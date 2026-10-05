"""Reconcile execution summaries with recorded attempts, without evaluating metrics."""

from __future__ import annotations

import json
from typing import Any


def _check(expected: Any, observed: Any, label: str) -> None:
    if expected != observed:
        raise ValueError(f"durable accounting identity mismatch: {label}")


def validate_call_purpose(call: dict[str, Any]) -> None:
    roles = {"generation": "generation", "judge": "judge", "generation_smoke": "generation"}
    purpose = call.get("purpose")
    if purpose not in roles:
        raise ValueError("unsupported durable call purpose identity")
    _check(roles[purpose], call["request"].get("role"), "purpose/request role")


def validate_call_accounting(
    manifest: dict[str, Any],
    comparison: dict[str, Any],
    calls: dict[str, dict[str, Any]],
    generation_failures: list[dict[str, Any]],
    judge_failures: list[dict[str, Any]],
    judge_decisions: list[dict[str, Any]],
) -> None:
    """Keep existing attempts, returned-response and failure-event definitions."""
    generation = [c for c in calls.values() if c["purpose"] == "generation"]
    judge = [c for c in calls.values() if c["purpose"] == "judge"]
    smoke = [c for c in calls.values() if c["purpose"] == "generation_smoke"]
    generation_returned = sum(c["status"] == "returned" for c in generation)
    judge_returned = sum(c["status"] == "returned" for c in judge)
    judge_failed = len(judge) - judge_returned
    malformed = sum(f["parser_version"] == "judge-json-v1" for f in judge_failures)
    rejections = sum(
        not d["accepted"] and d["reason"] != "malformed judge output; configured reject policy"
        for d in judge_decisions
    )
    expected = {
        "generation_attempted_calls": len(generation),
        "generation_successful_calls": generation_returned,
        "generation_calls": len(generation),
        "judge_attempted_calls": len(judge),
        "judge_successful_calls": judge_returned,
        "judge_calls": len(judge),
        "judge_provider_failures": judge_failed,
        "provider_calls": len(calls),
        "parse_failures": len(generation_failures),
        "parse_failure_event_count": len(generation_failures),
    }
    for key, count in expected.items():
        _check(count, comparison.get(key), f"comparison/{key}")
    _check(len(calls), manifest.get("provider_call_count"), "manifest provider calls")
    if "generation_provider_failures" in comparison:
        _check(
            len(generation) - generation_returned,
            comparison["generation_provider_failures"],
            "generation failures",
        )
    for key, count in {
        "provider_attempted_calls": len(calls),
        "provider_successful_calls": generation_returned
        + judge_returned
        + sum(c["status"] == "returned" for c in smoke),
        "provider_failed_calls": sum(c["status"] == "failed" for c in calls.values()),
    }.items():
        if key in comparison:
            if type(comparison[key]) is not int:
                raise ValueError(f"durable accounting count is invalid: {key}")
            _check(count, comparison[key], key)
    expected_smoke = 0 if manifest["replay"] else 1
    _check(expected_smoke, len(smoke), "smoke attempt population")
    report = comparison["provider_smoke"]
    _check("ok" if smoke else "not_run", report.get("status"), "smoke status")
    if smoke:
        request = smoke[0]["request"]
        for key, expected_value in {
            "prompt": 'Return exactly this JSON object and no other text: {"ok":true}',
            "temperature": 0.0,
            "request_index": 0,
            "seed": manifest["seed_provenance"]["generation"]["base_provider_seed"],
            "max_tokens": min(manifest["generation_max_tokens"], 64),
            "reasoning_effort": manifest["generation_reasoning_effort"],
            "response_format": {"type": manifest["generation_response_format"]}
            if manifest["generation_response_format"]
            else None,
        }.items():
            _check(expected_value, request.get(key), f"smoke request {key}")
        _check("returned", smoke[0]["status"], "smoke response status")
        response = json.loads(smoke[0]["response"]["response"])
        if not isinstance(response, dict) or response.get("ok") is not True:
            raise ValueError("smoke success contradicts durable response identity")
        _check(1, report.get("call_count"), "smoke report call count")
    elif "call_count" in report:
        _check(0, report["call_count"], "absent smoke count")
    b3 = comparison["baselines"]["b3"]
    for key, count in {
        "judge_attempted_calls": len(judge),
        "judge_successful_calls": judge_returned,
        "judge_calls": len(judge),
        "judge_provider_failures": judge_failed,
        "judge_malformed": malformed,
        "judge_rejections": rejections,
    }.items():
        _check(count, b3.get(key), f"b3/{key}")
    for key, count in {
        "judge_rejection": rejections,
        "judge_rejections": rejections,
        "judge_malformed": malformed,
        "judge_provider_failure": judge_failed,
    }.items():
        _check(count, b3["failure_counts"].get(key), f"b3/failure_counts/{key}")
    rows = comparison["baseline_comparison"]
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("required baseline comparison accounting rows are invalid")
    names = [row.get("baseline") for row in rows]
    if len(names) != len(set(names)) or set(names) != set(comparison["baselines"]):
        raise ValueError(
            "required baseline comparison accounting population is missing or duplicated"
        )
    for row in rows:
        source = comparison["baselines"][row["baseline"]]
        for key in ("requested", "raw_pool_count", "accepted"):
            _check(source[key], row.get(key), f"baseline comparison/{key}")
        # Retain the report writer's existing replay representation (None, not zero).
        if not isinstance(row.get("smoke"), dict):
            raise TypeError("required baseline smoke accounting is missing")
        if "call_count" not in row["smoke"]:
            raise ValueError("required baseline smoke call accounting is missing")
        _check(report.get("call_count"), row["smoke"].get("call_count"), "baseline smoke calls")
        for role, attempted, returned in (
            ("generation", len(generation), generation_returned),
            (
                "judge",
                len(judge) if row["baseline"] == "b3" else 0,
                judge_returned if row["baseline"] == "b3" else 0,
            ),
        ):
            _check(attempted, row["calls"][role]["attempted"], f"baseline calls/{role}/attempted")
            _check(returned, row["calls"][role]["successful"], f"baseline calls/{role}/successful")


def validate_comparison_identities(
    value: Any, expected: dict[str, Any], controls: dict[str, Any]
) -> None:
    """Check source IDs throughout comparison trees, retaining baseline context."""
    if isinstance(value, dict):
        context = dict(expected)
        declarations = [value[k] for k in ("baseline", "control_id", "baseline_id") if k in value]
        if declarations:
            name = declarations[0]
            if (
                not isinstance(name, str)
                or name not in controls
                or any(x != name for x in declarations)
            ):
                raise ValueError("comparison control identity mismatch")
            if "baseline" in context:
                _check(context["baseline"], name, "nested comparison control")
            context.update(
                baseline=name,
                control_id=name,
                baseline_id=name,
                control_fingerprint=controls[name]["fingerprint"],
            )
        for key, item in value.items():
            if key in context:
                _check(context[key], item, f"comparison/{key}")
            elif key == "control_fingerprint":
                if item not in [control["fingerprint"] for control in controls.values()]:
                    raise ValueError("comparison control fingerprint identity mismatch")
            else:
                validate_comparison_identities(item, context, controls)
    elif isinstance(value, list):
        for item in value:
            validate_comparison_identities(item, expected, controls)
