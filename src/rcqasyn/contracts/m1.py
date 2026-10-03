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
    for population in ("TRTR", "TSTR"):
        entries = result.setdefault(population, {})
        for classifier in classifiers:
            entry = entries.setdefault(
                classifier, {"status": "failed", "reason": "missing classifier result"}
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
        if all(
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


def utility_evaluable(utility: dict[str, Any]) -> bool:
    return all(
        utility.get(p) and all(row_evaluable(row) for row in utility[p].values())
        for p in ("TRTR", "TSTR")
    )


def require_baseline_structure(comparison: dict[str, Any]) -> None:
    required = {
        "requested",
        "raw_pool_count",
        "accepted",
        "accepted_record_ids",
        "acceptance_rate",
        "intrinsic",
        "intrinsic_metric_issues",
        "utility",
    }
    for name, baseline in comparison["baselines"].items():
        missing = required - baseline.keys()
        if missing:
            raise ValueError(f"missing required {name} result fields: {sorted(missing)}")
        expected_intrinsic = {
            "status",
            "numeric",
            "categorical",
            "correlations",
            "diversity",
            "class_conditional",
        }
        if expected_intrinsic - baseline["intrinsic"].keys():
            raise ValueError(f"missing required {name} intrinsic metric groups")
        intrinsic = baseline["intrinsic"]
        shapes = {
            "correlations": {"pearson", "spearman"},
            "diversity": {
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
            "class_conditional": {"status", "classes"},
        }
        for group, fields in shapes.items():
            if not isinstance(intrinsic[group], dict) or fields - intrinsic[group].keys():
                raise ValueError(f"missing required {name} intrinsic {group} fields")
        numeric_fields = {"status", "ks", "ks_statistic", "wasserstein", "wasserstein_distance"}
        categorical_fields = {"status", "tvd", "jsd", "jensen_shannon_divergence"}
        for group, fields in (("numeric", numeric_fields), ("categorical", categorical_fields)):
            for row in intrinsic[group].values():
                if not isinstance(row, dict) or fields - row.keys():
                    raise ValueError(f"missing required {name} intrinsic {group} metrics")
        for row in intrinsic["correlations"].values():
            if not isinstance(row, dict) or {"status", "mean_abs_error"} - row.keys():
                raise ValueError(f"missing required {name} correlation metrics")
        class_fields = {
            "status",
            "real_count",
            "synthetic_count",
            "exact_duplicate_count",
            "exact_duplicate_rate",
            "numeric",
            "categorical",
        }
        for row in intrinsic["class_conditional"]["classes"].values():
            if not isinstance(row, dict) or class_fields - row.keys():
                raise ValueError(f"missing required {name} class-conditional metrics")
        if (
            not 0 <= baseline["accepted"] <= baseline["raw_pool_count"]
            or len(baseline["accepted_record_ids"]) != baseline["accepted"]
        ):
            raise ValueError(f"inconsistent {name} admission accounting")
    b3 = comparison["baselines"]["b3"]
    judge_fields = {
        "judge_attempted_calls",
        "judge_successful_calls",
        "judge_provider_failures",
        "judge_malformed",
        "judge_calls",
    }
    if judge_fields - b3.keys():
        raise ValueError("missing required B3 judge accounting")
    if any(
        not isinstance(b3[key], int) or isinstance(b3[key], bool) or b3[key] < 0
        for key in judge_fields
    ):
        raise ValueError("invalid B3 judge accounting")
    if (
        b3["judge_successful_calls"] + b3["judge_provider_failures"] != b3["judge_attempted_calls"]
        or b3["judge_calls"] != b3["judge_attempted_calls"]
        or b3["judge_attempted_calls"] != comparison["raw_pool_count"]
        or b3["judge_malformed"] > b3["judge_successful_calls"]
    ):
        raise ValueError("inconsistent B3 judge accounting")


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
        ok = utility_evaluable(utility)
        evaluable &= ok
        reasons = [
            f"{p}/{c}: {row.get('reason') or row.get('evaluation_status')}"
            for p in ("TRTR", "TSTR")
            for c, row in utility.get(p, {}).items()
            if row.get("evaluation_status") != "evaluable"
        ]
        components[f"{name}.utility"] = ComponentState(
            status="complete" if ok else "unavailable", reasons=reasons
        )
        issues = baseline.get("intrinsic_metric_issues", {})
        intrinsic_status = baseline["intrinsic"]["status"]
        if intrinsic_status != "ok":
            issues = {**issues, "/status": f"intrinsic status: {intrinsic_status}"}
        components[f"{name}.diagnostics"] = ComponentState(
            status="failed"
            if intrinsic_status == "failed"
            else "partial"
            if issues
            else "complete",
            reasons=[f"{k}: {v}" for k, v in issues.items()],
        )
    success = evaluable and all(c.status == "complete" for c in components.values())
    return M1Outcome(
        lifecycle="finalized", components=components, utility_evaluable=evaluable, success=success
    )


def validate_comparison(value: dict[str, Any]) -> None:
    required = {
        "dataset_id",
        "baselines",
        "requested",
        "raw_pool_count",
        "outcome",
        "run_id",
        "specification_fingerprint",
        "schema_version",
    }
    if required - value.keys():
        raise ValueError(f"missing M1 comparison fields: {sorted(required - value.keys())}")
    if value["schema_version"] != "m1-comparison-v2" or set(value["baselines"]) != {
        "b1",
        "b2",
        "b3",
    }:
        raise ValueError("invalid M1 result schema")
    M1Outcome.model_validate(value["outcome"])
    if value["outcome"] != execution_outcome(value).model_dump(mode="json"):
        raise ValueError("reported outcome contradicts component results")
    classifiers = value.get("configured_classifiers")
    if not classifiers:
        raise ValueError("configured classifier list is required")
    for baseline in value["baselines"].values():
        if any(set(baseline["utility"][p]) != set(classifiers) for p in ("TRTR", "TSTR")):
            raise ValueError("configured classifier result is missing")
        expected_global = (
            "evaluable" if utility_evaluable(baseline["utility"]) else "not_fully_evaluable"
        )
        if baseline["utility"].get("evaluation_status") != expected_global:
            raise ValueError("utility evaluability contradicts metric/component results")
        for population in ("TRTR", "TSTR"):
            for row in baseline["utility"][population].values():
                expected_row = "evaluable" if row_evaluable(row) else "not_fully_evaluable"
                if row.get("evaluation_status") != expected_row:
                    raise ValueError("classifier evaluability contradicts metric/component results")
                for metric in UTILITY_METRICS:
                    metric_value = row.get(metric)
                    if metric_value is not None and (
                        isinstance(metric_value, bool)
                        or not isinstance(metric_value, (int, float))
                        or not math.isfinite(metric_value)
                    ):
                        raise ValueError("invalid metric value")
                availability = row.get("metric_availability", {})
                if set(availability) != set(UTILITY_METRICS):
                    raise ValueError("missing metric availability fields")
                for metric, state in availability.items():
                    if state.get("status") != (
                        "unavailable" if row.get(metric) is None else "available"
                    ):
                        raise ValueError("metric availability contradicts its value")
                if set(UTILITY_METRICS) - row.keys() or "metric_availability" not in row:
                    raise ValueError("missing required utility fields")
    import json

    json.dumps(value, allow_nan=False)
