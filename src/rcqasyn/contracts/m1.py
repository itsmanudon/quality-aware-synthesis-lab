"""M1 execution contracts. These statuses make no scientific quality judgment."""

from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

UTILITY_METRICS = ("f1", "average_precision", "pr_auc", "mcc", "balanced_accuracy", "auroc")


class ComponentState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["complete", "partial", "failed", "unavailable"]
    reasons: list[str]


class M1Outcome(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["m1-outcome-v1"] = "m1-outcome-v1"
    lifecycle: Literal["running", "finalized", "failed"]
    components: dict[str, ComponentState]
    utility_evaluable: bool
    success: bool

    @model_validator(mode="after")
    def consistent(self) -> M1Outcome:
        if not self.components:
            raise ValueError("component states are required")
        expected = (
            self.lifecycle == "finalized"
            and self.utility_evaluable
            and all(c.status == "complete" for c in self.components.values())
        )
        if self.success != expected:
            raise ValueError("success contradicts component/evaluation state")
        return self


def finite_tree(value: Any, path: str = "", issues: dict[str, str] | None = None) -> Any:
    """Convert unavailable numeric outputs to null, preserving their exact location."""
    if isinstance(value, float) and not math.isfinite(value):
        if issues is not None:
            issues[path] = "nonfinite"
        return None
    if isinstance(value, dict):
        return {key: finite_tree(item, f"{path}/{key}", issues) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite_tree(item, f"{path}/{index}", issues) for index, item in enumerate(value)]
    return value


def annotate_utility(utility: dict[str, Any], classifiers: tuple[str, ...]) -> dict[str, Any]:
    issues: dict[str, str] = {}
    result = finite_tree(utility, issues=issues)
    if result.get("status") in {
        "empty",
        "undefined",
        "failed",
        "unavailable",
        "partial",
    } and not _reason(result.get("reason")):
        result["reason"] = f"utility result {result['status']}"
    for population in ("TRTR", "TSTR"):
        entries = result.setdefault(population, {})
        for classifier in classifiers:
            entry = entries.setdefault(
                classifier, {"status": "failed", "reason": "missing classifier result"}
            )
            if entry.get("status") in {
                "empty",
                "undefined",
                "failed",
                "unavailable",
            } and not _reason(entry.get("reason")):
                entry["reason"] = (
                    f"classifier result {entry['status']} at {population}/{classifier}"
                )
            availability = {}
            for metric in UTILITY_METRICS:
                key = f"/{population}/{classifier}/{metric}"
                reason = (
                    "missing"
                    if metric not in entry
                    else issues.get(key)
                    or (
                        entry.get("metric_reasons", {}).get(metric)
                        or entry.get("reason")
                        or "unavailable"
                        if entry[metric] is None
                        else None
                    )
                )
                entry.setdefault(metric, None)
                availability[metric] = {
                    "status": "available" if reason is None else "unavailable",
                    "reason": reason or None,
                }
            entry["metric_availability"] = availability
            entry["evaluation_status"] = (
                "evaluable" if row_evaluable(entry) else "not_fully_evaluable"
            )
    result["evaluation_status"] = (
        "evaluable"
        if result.get("status") == "ok"
        and all(
            result[p][c]["evaluation_status"] == "evaluable"
            for p in ("TRTR", "TSTR")
            for c in classifiers
        )
        else "not_fully_evaluable"
    )
    return result


def row_evaluable(row: dict[str, Any]) -> bool:
    return row.get("status") == "ok" and all(
        metric in row
        and isinstance(row[metric], (int, float))
        and not isinstance(row[metric], bool)
        and math.isfinite(row[metric])
        for metric in UTILITY_METRICS
    )


def utility_evaluable(utility: dict[str, Any], classifiers: list[str] | None = None) -> bool:
    return utility.get("status") == "ok" and all(
        isinstance(utility.get(p), dict)
        and bool(utility[p])
        and (classifiers is None or set(utility[p]) == set(classifiers))
        and all(isinstance(row, dict) and row_evaluable(row) for row in utility[p].values())
        for p in ("TRTR", "TSTR")
    )


INTRINSIC_STATUSES = {"ok", "empty", "degenerate", "partial", "failed", "unavailable"}
NUMERIC_METRICS: dict[str, tuple[float, float | None]] = {
    "ks": (0, 1),
    "ks_statistic": (0, 1),
    "wasserstein": (0, None),
    "wasserstein_distance": (0, None),
}
CATEGORICAL_METRICS: dict[str, tuple[float, float | None]] = {
    "tvd": (0, 1),
    "jsd": (0, 1),
    "jensen_shannon_divergence": (0, 1),
}


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"invalid mapping at {path}")
    return value


def _required(row: dict[str, Any], fields: set[str], path: str) -> None:
    if fields - row.keys():
        raise ValueError(f"missing required {path} fields: {sorted(fields - row.keys())}")


def _reason(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _count(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"invalid nonnegative integer accounting at {path}")
    return value


def _number(value: Any, path: str, minimum: float = 0, maximum: float | None = None) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < minimum
        or (maximum is not None and value > maximum)
    ):
        raise ValueError(f"invalid metric value at {path}")


def _ratio(value: Any, numerator: int, denominator: int, path: str) -> None:
    expected = numerator / denominator if denominator else None
    if expected is None:
        if value is not None:
            raise ValueError(f"inconsistent undefined rate at {path}")
    else:
        _number(value, path)
        if not math.isclose(value, expected, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError(f"inconsistent accounting rate at {path}")


def _configured(value: dict[str, Any], *, required: bool) -> dict[str, list[str]] | None:
    configured = value.get("configured_results")
    if configured is None and not required:
        return None
    configured = _mapping(configured, "configured_results")
    fields = {
        "numeric_columns",
        "categorical_columns",
        "class_categorical_columns",
        "classes",
        "populations",
    }
    _required(configured, fields, "configured results")
    for field in fields:
        names = configured[field]
        if (
            not isinstance(names, list)
            or any(not _reason(name) for name in names)
            or len(set(names)) != len(names)
        ):
            raise ValueError(f"invalid configured {field}")
    if set(configured["populations"]) != {"TRTR", "TSTR"}:
        raise ValueError("invalid configured utility populations")
    if not configured["classes"]:
        raise ValueError("configured class results are required")
    if not set(configured["class_categorical_columns"]) <= set(configured["categorical_columns"]):
        raise ValueError("inconsistent configured categorical columns")
    return configured


def annotate_intrinsic(intrinsic: dict[str, Any]) -> dict[str, Any]:
    """Explain existing unavailable/degenerate results without changing metric values."""

    def annotate(row: dict[str, Any], path: str) -> None:
        status = row.get("status")
        if status in INTRINSIC_STATUSES - {"ok"} and not _reason(row.get("reason")):
            row["reason"] = f"intrinsic result {status} at {path or '/'}"
        metric_reasons = row.setdefault("metric_reasons", {}) if "status" in row else None
        for key, item in list(row.items()):
            if isinstance(item, dict) and key != "metric_reasons":
                annotate(item, f"{path}/{key}")
            elif item is None and metric_reasons is not None:
                metric_reasons.setdefault(
                    key, row.get("reason") or f"undefined intrinsic metric at {path}/{key}"
                )
        # Diversity maps contain numeric leaves rather than status rows.
        if "categorical_entropy" in row or "numeric_variance_ratio" in row:
            for group in ("categorical_entropy", "numeric_variance_ratio"):
                for column, item in row.get(group, {}).items():
                    if item is None:
                        row.setdefault("metric_reasons", {}).setdefault(
                            f"{group}/{column}",
                            f"undefined intrinsic metric at {path}/{group}/{column}",
                        )

    annotate(intrinsic, "")
    return intrinsic


def _intrinsic_state(row: dict[str, Any], path: str, *, reasons: bool) -> None:
    if not isinstance(row.get("status"), str) or row["status"] not in INTRINSIC_STATUSES:
        raise ValueError(f"invalid intrinsic status at {path}")
    if reasons and row["status"] != "ok" and not _reason(row.get("reason")):
        raise ValueError(f"unavailable intrinsic result requires reason at {path}")
    if "metric_reasons" in row:
        explanation = _mapping(row["metric_reasons"], f"{path}/metric_reasons")
        if any(not _reason(value) for value in explanation.values()):
            raise ValueError(f"invalid intrinsic metric reason at {path}")


def _intrinsic_metric(
    row: dict[str, Any],
    metric: str,
    bounds: tuple[float, float | None],
    path: str,
    *,
    reasons: bool,
    issue_map: dict[str, str],
    reason_key: str | None = None,
    reason_row: dict[str, Any] | None = None,
) -> None:
    value = row[metric]
    if value is None:
        source = reason_row if reason_row is not None else row
        explanation = (
            source.get("metric_reasons", {}).get(reason_key or metric)
            or source.get("reason")
            or issue_map.get(f"{path}/{metric}")
        )
        if reasons and not _reason(explanation):
            raise ValueError(f"unavailable intrinsic metric requires reason at {path}/{metric}")
    else:
        _number(value, f"{path}/{metric}", *bounds)


def _intrinsic_family(
    group: Any,
    expected: list[str] | None,
    metrics: dict[str, tuple[float, float | None]],
    path: str,
    *,
    reasons: bool,
    issue_map: dict[str, str],
) -> None:
    entries = _mapping(group, path)
    if expected is not None and set(entries) != set(expected):
        raise ValueError(f"missing or unexpected required configured results at {path}")
    for column, raw in entries.items():
        row = _mapping(raw, f"{path}/{column}")
        _required(row, {"status", *metrics}, f"{path}/{column}")
        _intrinsic_state(row, f"{path}/{column}", reasons=reasons)
        for metric, bounds in metrics.items():
            _intrinsic_metric(
                row, metric, bounds, f"{path}/{column}", reasons=reasons, issue_map=issue_map
            )


def _validate_intrinsic(
    baseline: dict[str, Any], name: str, configured: dict[str, list[str]] | None, *, reasons: bool
) -> None:
    intrinsic = _mapping(baseline["intrinsic"], f"{name}/intrinsic")
    _required(
        intrinsic,
        {"status", "numeric", "categorical", "correlations", "diversity", "class_conditional"},
        f"{name} intrinsic metric groups",
    )
    issue_map = _mapping(baseline["intrinsic_metric_issues"], f"{name}/intrinsic_metric_issues")
    if any(not _reason(value) for value in issue_map.values()):
        raise ValueError("intrinsic metric issues require explicit reasons")
    _intrinsic_state(intrinsic, f"{name}/intrinsic", reasons=reasons)
    numeric = configured["numeric_columns"] if configured else None
    categorical = configured["categorical_columns"] if configured else None
    _intrinsic_family(
        intrinsic["numeric"],
        numeric,
        NUMERIC_METRICS,
        "/numeric",
        reasons=reasons,
        issue_map=issue_map,
    )
    _intrinsic_family(
        intrinsic["categorical"],
        categorical,
        CATEGORICAL_METRICS,
        "/categorical",
        reasons=reasons,
        issue_map=issue_map,
    )
    _intrinsic_family(
        intrinsic["correlations"],
        ["pearson", "spearman"],
        {"mean_abs_error": (0, 2)},
        "/correlations",
        reasons=reasons,
        issue_map=issue_map,
    )
    diversity = _mapping(intrinsic["diversity"], "/diversity")
    _required(
        diversity,
        {
            "status",
            "rows",
            "unique_rows",
            "exact_duplicate_count",
            "exact_duplicate_rate",
            "duplicate_rate",
            "categorical_entropy",
            "numeric_variance_ratio",
            "unique_categorical_combinations",
        },
        f"{name} intrinsic diversity",
    )
    _intrinsic_state(diversity, "/diversity", reasons=reasons)
    for key in ("rows", "unique_rows", "exact_duplicate_count"):
        _count(diversity[key], f"/diversity/{key}")
    if (
        diversity["rows"] != baseline["accepted"]
        or diversity["unique_rows"] + diversity["exact_duplicate_count"] != diversity["rows"]
    ):
        raise ValueError("inconsistent intrinsic diversity accounting")
    for rate in ("exact_duplicate_rate", "duplicate_rate"):
        _ratio(
            diversity[rate],
            diversity["exact_duplicate_count"],
            diversity["rows"],
            f"/diversity/{rate}",
        )
        _intrinsic_metric(
            diversity, rate, (0, 1), "/diversity", reasons=reasons, issue_map=issue_map
        )
    combinations = diversity["unique_categorical_combinations"]
    if combinations is not None:
        if _count(combinations, "/diversity/unique_categorical_combinations") > diversity["rows"]:
            raise ValueError("inconsistent categorical diversity count")
    elif configured and configured["class_categorical_columns"]:
        _intrinsic_metric(
            diversity,
            "unique_categorical_combinations",
            (0, None),
            "/diversity",
            reasons=reasons,
            issue_map=issue_map,
        )
    for group, expected in (
        ("categorical_entropy", configured["class_categorical_columns"] if configured else None),
        ("numeric_variance_ratio", numeric),
    ):
        entries = _mapping(diversity[group], f"/diversity/{group}")
        # An empty population legitimately has empty maps, explicitly explained by its status.
        if (
            expected is not None
            and set(entries) != set(expected)
            and diversity["status"] != "empty"
        ):
            raise ValueError(f"missing required intrinsic diversity {group} results")
        for column in entries:
            _intrinsic_metric(
                entries,
                column,
                (0, None),
                f"/diversity/{group}",
                reasons=reasons,
                issue_map=issue_map,
                reason_key=f"{group}/{column}",
                reason_row=diversity,
            )
    conditional = _mapping(intrinsic["class_conditional"], "/class_conditional")
    _required(conditional, {"status", "classes"}, f"{name} class-conditional")
    _intrinsic_state(conditional, "/class_conditional", reasons=reasons)
    classes = _mapping(conditional["classes"], "/class_conditional/classes")
    if configured and not set(configured["classes"]) <= set(classes):
        raise ValueError("missing required configured class-conditional results")
    for label, raw in classes.items():
        path = f"/class_conditional/classes/{label}"
        row = _mapping(raw, path)
        _required(
            row,
            {
                "status",
                "real_count",
                "synthetic_count",
                "exact_duplicate_count",
                "exact_duplicate_rate",
                "numeric",
                "categorical",
            },
            f"{name} class-conditional metrics",
        )
        _intrinsic_state(row, path, reasons=reasons)
        for key in ("real_count", "synthetic_count", "exact_duplicate_count"):
            _count(row[key], f"{path}/{key}")
        if (
            row["exact_duplicate_count"] > row["synthetic_count"]
            or row["synthetic_count"] > baseline["accepted"]
        ):
            raise ValueError("inconsistent class-conditional accounting")
        _ratio(
            row["exact_duplicate_rate"],
            row["exact_duplicate_count"],
            row["synthetic_count"],
            f"{path}/exact_duplicate_rate",
        )
        _intrinsic_metric(
            row, "exact_duplicate_rate", (0, 1), path, reasons=reasons, issue_map=issue_map
        )
        _intrinsic_family(
            row["numeric"],
            numeric,
            NUMERIC_METRICS,
            f"{path}/numeric",
            reasons=reasons,
            issue_map=issue_map,
        )
        _intrinsic_family(
            row["categorical"],
            configured["class_categorical_columns"] if configured else None,
            CATEGORICAL_METRICS,
            f"{path}/categorical",
            reasons=reasons,
            issue_map=issue_map,
        )


def _generation_accounting(comparison: dict[str, Any]) -> None:
    fields = {
        "requested",
        "raw_pool_count",
        "generation_attempted_calls",
        "generation_successful_calls",
        "parse_failures",
    }
    _required(comparison, fields, "generation accounting")
    for field in fields:
        _count(comparison[field], field)
    attempts, successes = (
        comparison["generation_attempted_calls"],
        comparison["generation_successful_calls"],
    )
    if successes > attempts:
        raise ValueError("inconsistent generation accounting")
    for field, expected in (
        ("generation_calls", attempts),
        ("parse_success", comparison["raw_pool_count"]),
        ("parseable_record_count", comparison["raw_pool_count"]),
        ("parse_failure_event_count", comparison["parse_failures"]),
        ("experiment_requested", comparison["requested"]),
    ):
        if field in comparison and _count(comparison[field], field) != expected:
            raise ValueError(f"inconsistent {field} accounting")
    if "generation_provider_failures" in comparison:
        failures = _count(
            comparison["generation_provider_failures"], "generation_provider_failures"
        )
        if successes + failures != attempts:
            raise ValueError("inconsistent generation failure accounting")
    if "parse_success_rate" in comparison:
        # This is returned parseable / requested, so intentional overproduction may exceed one.
        _ratio(
            comparison["parse_success_rate"],
            comparison["raw_pool_count"],
            comparison["requested"],
            "parse_success_rate",
        )
    for field in ("parse_affected_requested_record_count", "unparseable_requested_record_count"):
        if field in comparison:
            _count(comparison[field], field)
    if "unparseable_requested_record_count" in comparison and "unparseable_rate" in comparison:
        _ratio(
            comparison["unparseable_rate"],
            comparison["unparseable_requested_record_count"],
            comparison["requested"],
            "unparseable_rate",
        )
    if "generation_accounting" in comparison:
        row = _mapping(comparison["generation_accounting"], "generation_accounting")
        _required(
            row, {"requested", "returned_parseable", "status"}, "generation accounting summary"
        )
        expected = (
            "exact"
            if comparison["raw_pool_count"] == comparison["requested"]
            else "overproduction"
            if comparison["raw_pool_count"] > comparison["requested"]
            else "shortfall"
        )
        if (
            _count(row["requested"], "generation_accounting/requested") != comparison["requested"]
            or _count(row["returned_parseable"], "generation_accounting/returned_parseable")
            != comparison["raw_pool_count"]
            or row["status"] != expected
        ):
            raise ValueError("inconsistent generation accounting summary")


def _failure_tree(row: dict[str, Any], path: str) -> None:
    """Failure summaries use requested denominators, which may have ratios above one."""
    for key, value in row.items():
        location = f"{path}/{key}"
        if isinstance(value, dict):
            _failure_tree(_mapping(value, location), location)
        elif key in {"rate", "unparseable_rate"}:
            if value is not None:
                _number(value, location)
        elif isinstance(value, list):
            if any(not _reason(item) for item in value):
                raise ValueError(f"invalid failure category list at {location}")
        else:
            _count(value, location)
    if "rate" in row:
        _required(row, {"occurrences", "unique_affected_record_count", "denominator"}, path)
        _ratio(row["rate"], row["unique_affected_record_count"], row["denominator"], f"{path}/rate")
        if row["unique_affected_record_count"] > row["occurrences"]:
            raise ValueError(f"inconsistent failure occurrence accounting at {path}")
        if row.get("failed_response_count", 0) > row["occurrences"]:
            raise ValueError(f"inconsistent failed-response accounting at {path}")
    if "failures" in row and "requested_count" in row:
        for summary in row["failures"].values():
            if isinstance(summary, dict) and summary.get("denominator") != row["requested_count"]:
                raise ValueError(f"inconsistent requested denominator at {path}")


def _derived_accounting(comparison: dict[str, Any], b3: dict[str, Any]) -> None:
    if "provider_calls" in comparison:
        smoke = _mapping(comparison.get("provider_smoke", {"status": "not_run"}), "provider_smoke")
        smoke_calls = 1 if smoke.get("status") == "ok" else 0
        if (
            "call_count" in smoke
            and _count(smoke["call_count"], "provider_smoke/call_count") != smoke_calls
        ):
            raise ValueError("inconsistent provider smoke call accounting")
        expected = (
            comparison["generation_attempted_calls"] + b3["judge_attempted_calls"] + smoke_calls
        )
        if _count(comparison["provider_calls"], "provider_calls") != expected:
            raise ValueError("inconsistent provider call total accounting")
    for key, value in comparison.items():
        if key.endswith("_tokens") and value is not None:
            _count(value, key)
    if "failure_aggregation" not in comparison:
        return
    aggregation = _mapping(comparison["failure_aggregation"], "failure_aggregation")
    _failure_tree(aggregation, "failure_aggregation")
    global_summary = _mapping(aggregation.get("global"), "failure_aggregation/global")
    if global_summary.get("raw_pool_count") != comparison["raw_pool_count"]:
        raise ValueError("inconsistent failure aggregation raw pool accounting")
    for category, summary in global_summary.items():
        if (
            isinstance(summary, dict)
            and "denominator" in summary
            and summary["denominator"] != comparison["requested"]
        ):
            raise ValueError(f"inconsistent global failure denominator at {category}")
    for aliases in (aggregation, comparison):
        if "unparseable_requested_record_count" in aliases:
            unparseable = _mapping(
                global_summary.get("unparseable"), "failure_aggregation/global/unparseable"
            )
            if aliases["unparseable_requested_record_count"] != unparseable.get(
                "unique_affected_record_count"
            ):
                raise ValueError("inconsistent unparseable count accounting")
            if "unparseable_rate" in aliases:
                _ratio(
                    aliases["unparseable_rate"],
                    aliases["unparseable_requested_record_count"],
                    comparison["requested"],
                    "unparseable_rate",
                )
    if "parse_affected_requested_record_count" in comparison and comparison[
        "parse_affected_requested_record_count"
    ] != global_summary.get("PARSE", {}).get("unique_affected_record_count"):
        raise ValueError("inconsistent parse affected-record accounting")
    for groups in ("by_requested_class", "majority_vs_minority"):
        if groups in aggregation:
            groups_row = _mapping(aggregation[groups], f"failure_aggregation/{groups}")
            if (
                sum(row.get("requested_count", 0) for row in groups_row.values())
                != comparison["requested"]
            ):
                raise ValueError(f"inconsistent {groups} requested total accounting")
            if (
                groups == "by_requested_class"
                and sum(row.get("parseable_count", 0) for row in groups_row.values())
                != comparison["raw_pool_count"]
            ):
                raise ValueError("inconsistent requested-class parseable total accounting")
    breakdown = _mapping(
        aggregation.get("provider_error_breakdown"), "failure_aggregation/provider_error_breakdown"
    )
    generation = _mapping(
        breakdown.get("generation"), "failure_aggregation/provider_error_breakdown/generation"
    )
    judge = _mapping(breakdown.get("judge"), "failure_aggregation/provider_error_breakdown/judge")
    _required(
        generation,
        {"failed_response_count", "affected_requested_record_count"},
        "generation provider failures",
    )
    _required(judge, {"failed_response_count", "affected_record_count"}, "judge provider failures")
    if (
        generation["failed_response_count"]
        != comparison["generation_attempted_calls"] - comparison["generation_successful_calls"]
        or judge["failed_response_count"] != b3["judge_provider_failures"]
        or judge["affected_record_count"] != b3["judge_provider_failures"]
        or generation["affected_requested_record_count"] < generation["failed_response_count"]
    ):
        raise ValueError("inconsistent provider failure response accounting")
    parse_responses = global_summary.get("PARSE", {}).get("failed_response_count")
    if (
        parse_responses is not None
        and parse_responses + generation["failed_response_count"] != comparison["parse_failures"]
    ):
        raise ValueError("inconsistent generation parse/provider failure event accounting")
    for key, expected in (
        ("judge_malformed", b3["judge_malformed"]),
        ("parse_failure", global_summary.get("PARSE", {}).get("unique_affected_record_count")),
    ):
        if key in aggregation and aggregation[key] != expected:
            raise ValueError(f"inconsistent failure alias {key}")
    if global_summary.get("provider_error_breakdown") != breakdown:
        raise ValueError("inconsistent provider error breakdown aliases")
    for key, expected in (
        ("generation_provider_failure", generation["affected_requested_record_count"]),
        ("judge_provider_failure", judge["affected_record_count"]),
        (
            "provider_error",
            generation["affected_requested_record_count"] + judge["affected_record_count"],
        ),
    ):
        if key in aggregation and aggregation[key] != expected:
            raise ValueError(f"inconsistent provider failure alias {key}")


def require_baseline_structure(comparison: dict[str, Any]) -> None:
    _generation_accounting(comparison)
    baselines = _mapping(comparison.get("baselines"), "baselines")
    if set(baselines) != {"b1", "b2", "b3"}:
        raise ValueError("missing required baseline results")
    for name, raw in baselines.items():
        baseline = _mapping(raw, name)
        _required(
            baseline,
            {
                "requested",
                "raw_pool_count",
                "accepted",
                "accepted_record_ids",
                "acceptance_rate",
                "intrinsic",
                "intrinsic_metric_issues",
                "utility",
            },
            f"{name} result",
        )
        for key in ("requested", "raw_pool_count", "accepted"):
            _count(baseline[key], f"{name}/{key}")
        ids = baseline["accepted_record_ids"]
        if (
            baseline["requested"] != comparison["requested"]
            or baseline["raw_pool_count"] != comparison["raw_pool_count"]
            or baseline["accepted"] > baseline["raw_pool_count"]
            or not isinstance(ids, list)
            or any(not _reason(record_id) for record_id in ids)
            or len(set(ids)) != len(ids)
            or len(ids) != baseline["accepted"]
        ):
            raise ValueError(f"inconsistent {name} admission accounting")
        _ratio(
            baseline["acceptance_rate"],
            baseline["accepted"],
            baseline["raw_pool_count"],
            f"{name}/acceptance_rate",
        )
        for alias in ("accepted_generated_ratio",):
            if alias in baseline:
                _ratio(
                    baseline[alias],
                    baseline["accepted"],
                    baseline["raw_pool_count"],
                    f"{name}/{alias}",
                )
        for field in (
            "duplicates",
            "exact_duplicate_count",
            "unique_count",
            "exact_train_match_count",
            "calls",
            "deterministic_violations",
            "deterministic_rejections",
            "judge_rejections",
        ):
            if field in baseline:
                _count(baseline[field], f"{name}/{field}")
        for count, rate in (
            ("exact_duplicate_count", "exact_duplicate_rate"),
            ("exact_train_match_count", "exact_train_match_rate"),
            ("deterministic_violations", "deterministic_violation_rate"),
            ("deterministic_rejections", "deterministic_rejection_rate"),
            ("judge_rejections", "judge_rejection_rate"),
        ):
            if count in baseline:
                if baseline[count] > baseline["raw_pool_count"]:
                    raise ValueError(f"inconsistent {name}/{count} accounting")
                if rate in baseline:
                    _ratio(
                        baseline[rate],
                        baseline[count],
                        baseline["raw_pool_count"],
                        f"{name}/{rate}",
                    )
        if (
            "unique_count" in baseline
            and "exact_duplicate_count" in baseline
            and baseline["unique_count"] + baseline["exact_duplicate_count"]
            != baseline["raw_pool_count"]
        ):
            raise ValueError(f"inconsistent {name} duplicate accounting")
        if (
            "duplicates" in baseline
            and "exact_duplicate_count" in baseline
            and baseline["duplicates"] != baseline["exact_duplicate_count"]
        ):
            raise ValueError(f"inconsistent {name} duplicate aliases")
    b3 = baselines["b3"]
    judge_fields = {
        "judge_attempted_calls",
        "judge_successful_calls",
        "judge_provider_failures",
        "judge_malformed",
        "judge_calls",
    }
    _required(b3, judge_fields, "B3 judge accounting")
    for key in judge_fields:
        _count(b3[key], f"b3/{key}")
    if (
        b3["judge_successful_calls"] + b3["judge_provider_failures"] != b3["judge_attempted_calls"]
        or b3["judge_calls"] != b3["judge_attempted_calls"]
        or b3["judge_attempted_calls"] != comparison["raw_pool_count"]
        or b3["judge_malformed"] > b3["judge_successful_calls"]
    ):
        raise ValueError("inconsistent B3 judge accounting")
    for field in judge_fields - {"judge_malformed"}:
        if field in comparison and comparison[field] != b3[field]:
            raise ValueError(f"inconsistent top-level {field} accounting")
    _derived_accounting(comparison, b3)


def _diagnostic_state(
    baseline: dict[str, Any], configured: dict[str, list[str]] | None
) -> ComponentState:
    issues = dict(baseline["intrinsic_metric_issues"])
    failed = False

    def visit(value: Any, path: str = "") -> None:
        nonlocal failed
        if isinstance(value, dict):
            if "status" in value and value["status"] != "ok":
                failed |= value["status"] == "failed"
                issues[f"{path}/status"] = (
                    value.get("reason") or f"intrinsic status: {value['status']}"
                )
            for key, item in value.items():
                if key in {"metric_reasons", "reason"}:
                    continue
                if item is None:
                    # No categorical features makes combinations inapplicable, not incomplete.
                    if (
                        key == "unique_categorical_combinations"
                        and configured
                        and not configured["class_categorical_columns"]
                    ):
                        continue
                    issues.setdefault(
                        f"{path}/{key}",
                        value.get("metric_reasons", {}).get(key)
                        or value.get("reason")
                        or "unavailable intrinsic metric",
                    )
                else:
                    visit(item, f"{path}/{key}")

    intrinsic = baseline["intrinsic"]
    try:
        _validate_intrinsic(baseline, "diagnostics", configured, reasons=False)
    except ValueError as error:
        issues["/contract"] = str(error)
    visit(intrinsic)
    if configured:
        for group, names in (
            ("numeric", configured["numeric_columns"]),
            ("categorical", configured["categorical_columns"]),
            ("correlations", ["pearson", "spearman"]),
        ):
            for column in names:
                if column not in intrinsic.get(group, {}):
                    issues[f"/{group}/{column}"] = "missing configured intrinsic result"
        for label in configured["classes"]:
            row = intrinsic.get("class_conditional", {}).get("classes", {}).get(label)
            if row is None:
                issues[f"/class_conditional/classes/{label}"] = "missing configured class result"
                continue
            for group, names in (
                ("numeric", configured["numeric_columns"]),
                ("categorical", configured["class_categorical_columns"]),
            ):
                for column in names:
                    if column not in row.get(group, {}):
                        issues[f"/class_conditional/classes/{label}/{group}/{column}"] = (
                            "missing configured intrinsic result"
                        )
    return ComponentState(
        status="failed" if failed else "partial" if issues else "complete",
        reasons=[f"{path}: {reason}" for path, reason in sorted(issues.items())],
    )


def execution_outcome(comparison: dict[str, Any]) -> M1Outcome:
    require_baseline_structure(comparison)
    components = {}
    generation_failed = (
        comparison["generation_successful_calls"] != comparison["generation_attempted_calls"]
    )
    components["generation"] = ComponentState(
        status="partial" if generation_failed else "complete",
        reasons=["provider failures"] if generation_failed else [],
    )
    parse_failures = comparison["parse_failures"]
    components["parsing"] = ComponentState(
        status="partial" if parse_failures else "complete",
        reasons=[f"{parse_failures} parse/provider failure events"] if parse_failures else [],
    )
    b3 = comparison["baselines"]["b3"]
    failed = b3.get("judge_provider_failures", 0) + b3.get("judge_malformed", 0)
    components["judge"] = ComponentState(
        status="partial" if failed else "complete",
        reasons=[f"{failed} judge failures"] if failed else [],
    )
    evaluable = True
    for name, baseline in comparison["baselines"].items():
        utility = baseline["utility"]
        ok = utility_evaluable(utility, comparison.get("configured_classifiers"))
        evaluable &= ok
        reasons = [
            f"{p}/{c}: {row.get('reason') or row.get('evaluation_status')}"
            for p in ("TRTR", "TSTR")
            for c, row in utility.get(p, {}).items()
            if row.get("evaluation_status") != "evaluable"
        ]
        if utility.get("status") != "ok":
            reasons.append(
                f"utility: {utility.get('reason') or utility.get('status') or 'missing status'}"
            )
        for population in ("TRTR", "TSTR"):
            if not utility.get(population):
                reasons.append(f"{population}: missing population results")
            for classifier in comparison.get("configured_classifiers", []):
                if classifier not in utility.get(population, {}):
                    reasons.append(
                        f"{population}/{classifier}: missing configured classifier result"
                    )
        components[f"{name}.utility"] = ComponentState(
            status="complete" if ok else "unavailable", reasons=sorted(set(reasons))
        )
        components[f"{name}.diagnostics"] = _diagnostic_state(
            baseline, _configured(comparison, required=False)
        )
    success = evaluable and all(c.status == "complete" for c in components.values())
    return M1Outcome(
        lifecycle="finalized", components=components, utility_evaluable=evaluable, success=success
    )


def validate_comparison(value: dict[str, Any]) -> None:
    value = _mapping(value, "comparison")
    required = {
        "dataset_id",
        "baselines",
        "requested",
        "raw_pool_count",
        "outcome",
        "run_id",
        "specification_fingerprint",
        "schema_version",
        "configured_classifiers",
        "configured_results",
    }
    _required(value, required, "M1 comparison")
    if value["schema_version"] != "m1-comparison-v2":
        raise ValueError("invalid M1 result schema")
    configured = _configured(value, required=True)
    assert configured is not None
    classifiers = value["configured_classifiers"]
    if (
        not isinstance(classifiers, list)
        or not classifiers
        or any(not _reason(name) for name in classifiers)
        or len(set(classifiers)) != len(classifiers)
    ):
        raise ValueError("configured classifier list is required")
    require_baseline_structure(value)
    for name, baseline in value["baselines"].items():
        _validate_intrinsic(baseline, name, configured, reasons=True)
        utility = _mapping(baseline["utility"], f"{name}/utility")
        _required(utility, {"status", "TRTR", "TSTR", "evaluation_status"}, f"{name} utility")
        if not isinstance(utility["status"], str) or utility["status"] not in {
            "ok",
            "empty",
            "undefined",
            "failed",
            "unavailable",
            "partial",
        }:
            raise ValueError("invalid utility status")
        if utility["status"] != "ok" and not _reason(utility.get("reason")):
            raise ValueError("unavailable utility result requires reason")
        population_keys = set(utility) - {"status", "evaluation_status", "reason"}
        if population_keys != set(configured["populations"]):
            raise ValueError("configured population result is missing or unexpected")
        for population in configured["populations"]:
            rows = _mapping(utility[population], f"{name}/utility/{population}")
            if set(rows) != set(classifiers):
                raise ValueError("configured classifier result is missing or unexpected")
            for classifier, raw in rows.items():
                path = f"{name}/utility/{population}/{classifier}"
                row = _mapping(raw, path)
                _required(
                    row,
                    {"status", "evaluation_status", "metric_availability", *UTILITY_METRICS},
                    "utility",
                )
                if not isinstance(row["status"], str) or row["status"] not in {
                    "ok",
                    "empty",
                    "undefined",
                    "failed",
                    "unavailable",
                }:
                    raise ValueError("invalid classifier status")
                # Existing evaluability contradiction is reported before availability details.
                expected_row = "evaluable" if row_evaluable(row) else "not_fully_evaluable"
                if row["evaluation_status"] != expected_row:
                    raise ValueError("classifier evaluability contradicts metric/component results")
                if row["status"] != "ok" and not _reason(row.get("reason")):
                    raise ValueError("unavailable classifier result requires reason")
                availability = _mapping(row["metric_availability"], f"{path}/metric_availability")
                if set(availability) != set(UTILITY_METRICS):
                    raise ValueError("missing metric availability fields")
                for metric in UTILITY_METRICS:
                    metric_value = row[metric]
                    if metric_value is not None:
                        _number(metric_value, f"{path}/{metric}", -1 if metric == "mcc" else 0, 1)
                    state = _mapping(availability[metric], f"{path}/metric_availability/{metric}")
                    _required(state, {"status", "reason"}, "metric availability")
                    expected_state = "unavailable" if metric_value is None else "available"
                    if state["status"] != expected_state:
                        raise ValueError("metric availability contradicts its value")
                    if expected_state == "unavailable" and not _reason(state["reason"]):
                        raise ValueError("unavailable utility metric requires reason")
                    if expected_state == "available" and state["reason"] is not None:
                        raise ValueError("available metric cannot have unavailable reason")
        expected_global = "evaluable" if utility_evaluable(utility) else "not_fully_evaluable"
        if utility["evaluation_status"] != expected_global:
            raise ValueError("utility evaluability contradicts metric/component results")
    M1Outcome.model_validate(value["outcome"])
    if value["outcome"] != execution_outcome(value).model_dump(mode="json"):
        raise ValueError("reported outcome contradicts component results")
    import json

    json.dumps(value, allow_nan=False)
