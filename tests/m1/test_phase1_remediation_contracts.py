"""F1 verifier regressions: operational completeness, not scientific quality."""

from copy import deepcopy

import pytest

from rcqasyn.contracts.m1 import (
    UTILITY_METRICS,
    annotate_utility,
    execution_outcome,
    validate_comparison,
)


def complete_comparison():
    numeric = {
        "status": "ok",
        "ks": 0.0,
        "ks_statistic": 0.0,
        "wasserstein": 0.0,
        "wasserstein_distance": 0.0,
    }
    categorical = {"status": "ok", "tvd": 0.0, "jsd": 0.0, "jensen_shannon_divergence": 0.0}
    intrinsic = {
        "status": "ok",
        "numeric": {"age": numeric},
        "categorical": {"color": categorical, "label": deepcopy(categorical)},
        "correlations": {
            m: {"status": "ok", "mean_abs_error": 0.0} for m in ("pearson", "spearman")
        },
        "diversity": {
            "status": "ok",
            "rows": 2,
            "unique_rows": 2,
            "exact_duplicate_count": 0,
            "exact_duplicate_rate": 0.0,
            "duplicate_rate": 0.0,
            "categorical_entropy": {"color": 1.0},
            "numeric_variance_ratio": {"age": 1.0},
            "unique_categorical_combinations": 2,
        },
        "class_conditional": {
            "status": "ok",
            "classes": {
                label: {
                    "status": "ok",
                    "real_count": 2,
                    "synthetic_count": 1,
                    "exact_duplicate_count": 0,
                    "exact_duplicate_rate": 0.0,
                    "numeric": {"age": deepcopy(numeric)},
                    "categorical": {"color": deepcopy(categorical)},
                }
                for label in ("no", "yes")
            },
        },
    }
    utility = annotate_utility(
        {
            "status": "ok",
            **{
                p: {"random_forest": {"status": "ok", **{m: 0.0 for m in UTILITY_METRICS}}}
                for p in ("TRTR", "TSTR")
            },
        },
        ("random_forest",),
    )
    baseline = {
        "requested": 2,
        "raw_pool_count": 2,
        "accepted": 2,
        "accepted_record_ids": ["a", "b"],
        "acceptance_rate": 1.0,
        "intrinsic": intrinsic,
        "intrinsic_metric_issues": {},
        "utility": utility,
    }
    value = {
        "schema_version": "m1-comparison-v2",
        "dataset_id": "fixture",
        "run_id": "fixture",
        "specification_fingerprint": "fixture",
        "configured_classifiers": ["random_forest"],
        "configured_results": {
            "numeric_columns": ["age"],
            "categorical_columns": ["color", "label"],
            "class_categorical_columns": ["color"],
            "classes": ["no", "yes"],
            "populations": ["TRTR", "TSTR"],
        },
        "requested": 2,
        "raw_pool_count": 2,
        "generation_attempted_calls": 1,
        "generation_successful_calls": 1,
        "generation_calls": 1,
        "parse_success": 2,
        "parse_success_rate": 1.0,
        "parse_failures": 0,
        "parse_failure_event_count": 0,
        "baselines": {b: deepcopy(baseline) for b in ("b1", "b2", "b3")},
    }
    value["baselines"]["b3"].update(
        judge_attempted_calls=2,
        judge_successful_calls=2,
        judge_provider_failures=0,
        judge_malformed=0,
        judge_calls=2,
    )
    value["outcome"] = execution_outcome(value).model_dump(mode="json")
    return value


def refresh(value):
    value["outcome"] = execution_outcome(value).model_dump(mode="json")
    return value


def test_low_finite_metric_values_remain_successful():
    value = complete_comparison()
    validate_comparison(value)
    assert value["outcome"]["success"] is True


def test_nested_failed_diagnostic_prevents_success():
    value = complete_comparison()
    value["baselines"]["b1"]["intrinsic"]["numeric"]["age"].update(
        status="failed", reason="injected"
    )
    refresh(value)
    validate_comparison(value)
    assert value["outcome"]["components"]["b1.diagnostics"]["status"] == "failed"
    assert value["outcome"]["success"] is False


@pytest.mark.parametrize(
    "path",
    [
        ("numeric", "age"),
        ("categorical", "label"),
        ("class_conditional", "classes", "yes"),
        ("class_conditional", "classes", "no", "numeric", "age"),
        ("class_conditional", "classes", "yes", "categorical", "color"),
        ("diversity", "numeric_variance_ratio", "age"),
        ("diversity", "categorical_entropy", "color"),
    ],
)
def test_missing_configured_intrinsic_results_rejected(path):
    value = complete_comparison()
    parent = value["baselines"]["b1"]["intrinsic"]
    for key in path[:-1]:
        parent = parent[key]
    parent.pop(path[-1])
    with pytest.raises(ValueError):
        validate_comparison(value)


@pytest.mark.parametrize(
    "path,replacement",
    [
        (("numeric", "age", "status"), "unknown"),
        (("categorical", "color", "status"), "unknown"),
        (("class_conditional", "classes", "yes", "status"), "unknown"),
        (("correlations", "pearson", "status"), "unknown"),
        (("diversity", "status"), "unknown"),
        (("numeric", "age", "ks"), True),
        (("numeric", "age", "wasserstein"), -0.1),
        (("categorical", "color", "tvd"), 1.1),
        (("correlations", "pearson", "mean_abs_error"), 2.1),
        (("class_conditional", "classes", "yes", "synthetic_count"), -1),
        (("diversity", "exact_duplicate_count"), 3),
    ],
)
def test_intrinsic_nested_enum_type_and_value_validation(path, replacement):
    value = complete_comparison()
    parent = value["baselines"]["b1"]["intrinsic"]
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = replacement
    with pytest.raises(ValueError):
        validate_comparison(value)


@pytest.mark.parametrize(
    "field",
    [
        "generation_attempted_calls",
        "generation_successful_calls",
        "parse_failures",
        "requested",
        "raw_pool_count",
    ],
)
def test_negative_generation_or_parse_accounting_rejected(field):
    value = complete_comparison()
    value[field] = -1
    with pytest.raises(ValueError):
        validate_comparison(value)


@pytest.mark.parametrize(
    "field,replacement",
    [
        ("generation_successful_calls", 2),
        ("generation_calls", 2),
        ("parse_success", 1),
        ("parse_success_rate", -1.0),
        ("parse_failure_event_count", 1),
    ],
)
def test_inconsistent_generation_or_parse_accounting_rejected(field, replacement):
    value = complete_comparison()
    value[field] = replacement
    with pytest.raises(ValueError):
        validate_comparison(value)


def test_intentional_overproduction_parse_ratio_is_not_clamped():
    value = complete_comparison()
    value["requested"] = 1
    value["parse_success_rate"] = 2.0
    for baseline in value["baselines"].values():
        baseline["requested"] = 1
    refresh(value)
    validate_comparison(value)
    assert value["parse_success_rate"] == 2.0


@pytest.mark.parametrize("mutation", ["population", "classifier", "status", "reason", "metric"])
def test_nested_utility_validation(mutation):
    value = complete_comparison()
    utility = value["baselines"]["b1"]["utility"]
    row = utility["TRTR"]["random_forest"]
    if mutation == "population":
        utility["TSTT"] = utility.pop("TSTR")
    elif mutation == "classifier":
        utility["TRTR"]["wrong"] = utility["TRTR"].pop("random_forest")
    elif mutation == "status":
        row["status"] = "unknown"
    elif mutation == "metric":
        row["auroc"] = 1.1
    else:
        row["f1"] = None
        row["metric_availability"]["f1"] = {"status": "unavailable", "reason": None}
        row["evaluation_status"] = utility["evaluation_status"] = "not_fully_evaluable"
        refresh(value)
    with pytest.raises(ValueError):
        validate_comparison(value)


def test_unavailable_intrinsic_requires_explicit_reason():
    value = complete_comparison()
    row = value["baselines"]["b1"]["intrinsic"]["correlations"]["pearson"]
    row.update(status="empty", mean_abs_error=None)
    with pytest.raises(ValueError):
        validate_comparison(value)


def test_empty_configured_groups_are_rejected():
    value = complete_comparison()
    value["baselines"]["b1"]["intrinsic"]["numeric"] = {}
    value["baselines"]["b1"]["intrinsic"]["categorical"] = {}
    with pytest.raises(ValueError):
        validate_comparison(value)


def fully_evaluable_config(tmp_path, monkeypatch):
    """Use the established dev-small TRAIN fixture to isolate diagnostic failures."""
    from dataclasses import replace
    from pathlib import Path

    from rcqasyn.config import load_experiment_config
    from rcqasyn.datasets import DatasetRegistry, load_dataset, make_split
    from rcqasyn.generation.provider import ProviderResponse, ReplayProvider

    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    registry = DatasetRegistry(project_root=Path.cwd())
    dataset = load_dataset(registry.get("dev-small"), registry)
    train = dataset.frame.loc[list(make_split(dataset, 42).train_indices)]
    original = ReplayProvider.call

    def valid(self, **kwargs):
        if kwargs["role"] == "judge":
            return ProviderResponse(
                response='{"score":1,"verdict":"pass"}',
                provider="fixture",
                model="fixture",
                endpoint=None,
            )
        response = original(self, **kwargs)
        label = "no" if kwargs["request_index"] == 0 else "yes"
        return replace(
            response, response=train[train["label"] == label].iloc[:3].to_json(orient="records")
        )

    monkeypatch.setattr(ReplayProvider, "call", valid)
    return config.model_copy(update={"artifact_root": tmp_path, "run_id": None})


@pytest.mark.parametrize("status", ["failed", "empty", "degenerate"])
def test_actual_run_nested_intrinsic_status_propagates(tmp_path, monkeypatch, status):
    from rcqasyn.experiments import run_experiment, runner
    from rcqasyn.experiments.readers import read_bundle

    config = fully_evaluable_config(tmp_path, monkeypatch)
    original = runner.intrinsic_metrics

    def injected(*args, **kwargs):
        result = original(*args, **kwargs)
        result["numeric"]["age"]["status"] = status
        return result

    monkeypatch.setattr(runner, "intrinsic_metrics", injected)
    run = run_experiment(config, replay=True)
    value = read_bundle(run.artifact_dir)
    assert value["outcome"]["success"] is False
    for baseline in ("b1", "b2", "b3"):
        state = value["outcome"]["components"][f"{baseline}.diagnostics"]
        assert state["status"] == ("failed" if status == "failed" else "partial")
        assert any("/numeric/age/status" in reason for reason in state["reasons"])
        assert value["baselines"][baseline]["intrinsic"]["numeric"]["age"]["reason"]
        assert value["outcome"]["components"][f"{baseline}.utility"]["status"] == "complete"


@pytest.mark.parametrize("missing", ["age", "numeric", "categorical", "class"])
def test_actual_run_missing_configured_diagnostics_cannot_finalize(tmp_path, monkeypatch, missing):
    import json

    from rcqasyn.experiments import run_experiment, runner
    from rcqasyn.experiments.readers import read_bundle

    config = fully_evaluable_config(tmp_path, monkeypatch)
    original = runner.intrinsic_metrics

    def injected(*args, **kwargs):
        result = original(*args, **kwargs)
        if missing == "age":
            result["numeric"].pop("age")
        elif missing == "class":
            result["class_conditional"]["classes"].pop("yes")
        else:
            result[missing] = {}
        return result

    monkeypatch.setattr(runner, "intrinsic_metrics", injected)
    with pytest.raises(ValueError, match="required"):
        run_experiment(config, replay=True)
    directory = next((tmp_path / "runs").iterdir())
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["status"] == "failed" and manifest["success"] is False
    assert not (directory / "FINALIZED.json").exists()
    with pytest.raises(ValueError, match="incomplete"):
        read_bundle(directory)


def test_successful_run_reader_rejects_forged_nested_status(tmp_path, monkeypatch):
    from rcqasyn.experiments import readers, run_experiment

    run = run_experiment(fully_evaluable_config(tmp_path, monkeypatch), replay=True)
    assert readers.read_bundle(run.artifact_dir)["outcome"]["success"] is True
    forged = deepcopy(run.comparison)
    forged["baselines"]["b1"]["intrinsic"]["numeric"]["age"]["status"] = "unknown"
    original = readers.read_json

    def injected(path):
        if path.name == "comparison.json":
            return forged
        if path.name == "metrics.json" and path.parent.name == "b1":
            return forged["baselines"]["b1"]["intrinsic"]
        return original(path)

    monkeypatch.setattr(readers, "read_json", injected)
    with pytest.raises(ValueError, match="intrinsic status"):
        readers.read_bundle(run.artifact_dir)


@pytest.mark.parametrize(
    "field",
    [
        "configured_results",
        "configured_classifiers",
        "generation_attempted_calls",
        "parse_failures",
    ],
)
def test_required_configured_and_generation_fields(field):
    value = complete_comparison()
    value.pop(field)
    with pytest.raises(ValueError, match="required"):
        validate_comparison(value)


def test_missing_configured_result_diagnostics_is_partial_before_validation():
    value = complete_comparison()
    value["baselines"]["b1"]["intrinsic"]["numeric"].pop("age")
    outcome = execution_outcome(value)
    assert outcome.success is False
    assert outcome.components["b1.diagnostics"].status == "partial"
    assert "age" in str(outcome.components["b1.diagnostics"].reasons)


def test_empty_and_degenerate_availability_preserves_original_numbers():
    from rcqasyn.contracts.m1 import annotate_intrinsic

    intrinsic = complete_comparison()["baselines"]["b1"]["intrinsic"]
    intrinsic["numeric"]["age"]["status"] = "degenerate"
    intrinsic["correlations"]["pearson"].update(status="empty", mean_abs_error=None)
    original = deepcopy(intrinsic)
    result = annotate_intrinsic(intrinsic)
    for key in NUMERIC_VALUE_FIELDS:
        assert result["numeric"]["age"][key] == original["numeric"]["age"][key]
    assert result["correlations"]["pearson"]["mean_abs_error"] is None
    assert result["numeric"]["age"]["reason"]
    assert result["correlations"]["pearson"]["metric_reasons"]["mean_abs_error"]
    assert annotate_intrinsic({}) == {}


NUMERIC_VALUE_FIELDS = ("ks", "ks_statistic", "wasserstein", "wasserstein_distance")


def test_diagnostic_reason_order_survives_sorted_json_roundtrip():
    import json

    value = complete_comparison()
    intrinsic = value["baselines"]["b1"]["intrinsic"]
    intrinsic["numeric"]["age"].update(status="failed", reason="injected failure")
    intrinsic["categorical"]["color"].update(status="degenerate", reason="injected degeneracy")
    refresh(value)
    restored = json.loads(json.dumps(value, sort_keys=True))
    validate_comparison(restored)
    assert execution_outcome(restored).model_dump(mode="json") == value["outcome"]


@pytest.mark.parametrize("group", ["correlations", "diversity", "class_conditional"])
def test_missing_family_diagnostics_is_partial_before_validation(group):
    value = complete_comparison()
    value["baselines"]["b1"]["intrinsic"][group] = {}
    outcome = execution_outcome(value)
    assert outcome.success is False
    assert outcome.components["b1.diagnostics"].status == "partial"
    assert outcome.components["b1.diagnostics"].reasons


@pytest.mark.parametrize(
    "field,value",
    [("parse_affected_requested_record_count", -1), ("unparseable_requested_record_count", -1)],
)
def test_invalid_requested_record_accounting_rejected(field, value):
    comparison = complete_comparison()
    comparison[field] = value
    with pytest.raises(ValueError):
        validate_comparison(comparison)


def test_wrong_configured_classifier_outcome_is_unavailable_with_reason():
    comparison = complete_comparison()
    utility = comparison["baselines"]["b1"]["utility"]
    utility["TRTR"]["wrong"] = utility["TRTR"].pop("random_forest")
    outcome = execution_outcome(comparison)
    assert outcome.success is False
    assert outcome.components["b1.utility"].status == "unavailable"
    assert "missing configured classifier" in str(outcome.components["b1.utility"].reasons)


def test_failed_classifier_requires_explicit_reason():
    value = complete_comparison()
    row = value["baselines"]["b1"]["utility"]["TRTR"]["random_forest"]
    row["status"] = "failed"
    row["evaluation_status"] = value["baselines"]["b1"]["utility"]["evaluation_status"] = (
        "not_fully_evaluable"
    )
    refresh(value)
    with pytest.raises(ValueError, match="reason"):
        validate_comparison(value)


def test_global_utility_failure_propagates_with_finite_classifiers():
    value = complete_comparison()
    utility = value["baselines"]["b1"]["utility"]
    utility.update(
        status="failed", reason="injected family failure", evaluation_status="not_fully_evaluable"
    )
    refresh(value)
    validate_comparison(value)
    assert value["outcome"]["success"] is False
    assert value["outcome"]["components"]["b1.utility"]["status"] == "unavailable"
    assert "injected family failure" in str(value["outcome"]["components"]["b1.utility"]["reasons"])


def derived_accounting_comparison():
    value = complete_comparison()
    summary = {
        "occurrences": 0,
        "unique_affected_record_count": 0,
        "failed_response_count": 0,
        "denominator": 2,
        "rate": 0.0,
    }
    breakdown = {
        "generation": {"failed_response_count": 0, "affected_requested_record_count": 0},
        "judge": {"failed_response_count": 0, "affected_record_count": 0},
    }
    value.update(
        provider_calls=3,
        provider_smoke={"status": "not_run"},
        unparseable_requested_record_count=0,
        unparseable_rate=0.0,
        parse_affected_requested_record_count=0,
    )
    value["failure_aggregation"] = {
        "generation_provider_failure": 0,
        "judge_provider_failure": 0,
        "provider_error": 0,
        "unparseable_requested_record_count": 0,
        "unparseable_rate": 0.0,
        "provider_error_breakdown": breakdown,
        "global": {
            "PARSE": deepcopy(summary),
            "B2_REJECTED": deepcopy(summary),
            "unparseable": {
                "occurrences": 0,
                "unique_affected_record_count": 0,
                "denominator": 2,
                "rate": 0.0,
            },
            "raw_pool_count": 2,
            "provider_error_breakdown": deepcopy(breakdown),
        },
    }
    return value


@pytest.mark.parametrize(
    "path,replacement",
    [
        (("provider_calls",), -1),
        (("provider_calls",), 4),
        (("failure_aggregation", "provider_error"), -1),
        (("failure_aggregation", "global", "B2_REJECTED", "failed_response_count"), -1),
        (("failure_aggregation", "global", "B2_REJECTED", "unique_affected_record_count"), -1),
        (("failure_aggregation", "global", "B2_REJECTED", "occurrences"), -1),
        (("failure_aggregation", "global", "B2_REJECTED", "denominator"), -1),
        (("failure_aggregation", "global", "B2_REJECTED", "rate"), -0.1),
        (("failure_aggregation", "global", "B2_REJECTED", "rate"), 0.5),
        (
            (
                "failure_aggregation",
                "provider_error_breakdown",
                "generation",
                "failed_response_count",
            ),
            1,
        ),
        (("failure_aggregation", "provider_error_breakdown", "judge", "affected_record_count"), -1),
        (("failure_aggregation", "global", "raw_pool_count"), 1),
        (("failure_aggregation", "unparseable_requested_record_count"), -1),
        (("failure_aggregation", "unparseable_rate"), -1.0),
    ],
)
def test_derived_accounting_invalid_counts_rates_and_totals_rejected(path, replacement):
    value = derived_accounting_comparison()
    parent = value
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = replacement
    with pytest.raises(ValueError):
        validate_comparison(value)


def test_failure_summary_ratio_preserves_defined_overproduction():
    value = derived_accounting_comparison()
    value["requested"] = 1
    value["parse_success_rate"] = 2.0
    for baseline in value["baselines"].values():
        baseline["requested"] = 1
    aggregation = value["failure_aggregation"]
    aggregation["global"]["B2_REJECTED"].update(
        occurrences=2,
        unique_affected_record_count=2,
        failed_response_count=2,
        denominator=1,
        rate=2.0,
    )
    for group in ("PARSE", "unparseable"):
        aggregation["global"][group]["denominator"] = 1
    refresh(value)
    validate_comparison(value)
    assert aggregation["global"]["B2_REJECTED"]["rate"] == 2.0


def test_failure_summary_events_cannot_contradict_generation_parsing_component():
    value = derived_accounting_comparison()
    value["failure_aggregation"]["global"]["PARSE"].update(
        occurrences=1, unique_affected_record_count=1, failed_response_count=1, rate=0.5
    )
    value["parse_affected_requested_record_count"] = 1
    with pytest.raises(ValueError, match="failure event"):
        validate_comparison(value)


def test_unparseable_requested_denominator_ratio_preserves_frozen_event_accounting():
    # The frozen parser retains batch requested_count on every malformed array-item event.
    value = derived_accounting_comparison()
    value.update(
        parse_failures=2,
        parse_failure_event_count=2,
        parse_affected_requested_record_count=4,
        unparseable_requested_record_count=4,
        unparseable_rate=2.0,
    )
    aggregation = value["failure_aggregation"]
    aggregation.update(unparseable_requested_record_count=4, unparseable_rate=2.0)
    aggregation["global"]["PARSE"].update(
        occurrences=4, unique_affected_record_count=4, failed_response_count=2, rate=2.0
    )
    aggregation["global"]["unparseable"].update(
        occurrences=4, unique_affected_record_count=4, rate=2.0
    )
    refresh(value)
    validate_comparison(value)
    assert value["outcome"]["components"]["parsing"]["status"] == "partial"
    assert value["unparseable_rate"] == 2.0


def test_negative_derived_provider_token_count_rejected():
    value = derived_accounting_comparison()
    value["generation_total_tokens"] = -1
    with pytest.raises(ValueError, match="accounting"):
        validate_comparison(value)
