import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from rcqasyn.config import load_experiment_config
from rcqasyn.contracts import ClassQuota, ParseFailureEvent
from rcqasyn.datasets import DatasetRegistry, build_profile, load_dataset, make_split
from rcqasyn.experiments.analysis import (
    HUMAN_COLUMNS,
    REVIEW_CATEGORIES,
    analyze_human_review,
    cross_dataset_comparison,
    export_disagreements,
    export_human_review,
)
from rcqasyn.experiments.runner import _aggregate_failures, _comparison
from rcqasyn.generation.parser import parse_generation_response


def test_profile_per_class_references_are_deterministic_and_train_only() -> None:
    registry = DatasetRegistry(project_root=Path.cwd())
    dataset = load_dataset(registry.get("dev-small"), registry)
    split = make_split(dataset, 42)
    profile = build_profile(dataset, split, reference_example_count=99, reference_examples_per_class=2, seed=42)
    labels = [str(profile.reference_examples[index]["label"]) for index in range(len(profile.reference_examples))]
    assert profile.reference_policy == "per_class"
    assert profile.reference_examples_per_class == 2
    assert profile.reference_example_count == 4
    assert {label: labels.count(label) for label in set(labels)} == {"no": 2, "yes": 2}
    assert set(profile.reference_indices) <= set(split.train_indices)


def _write_run_fixture(run_dir: Path) -> None:
    (run_dir / "baselines" / "b2").mkdir(parents=True)
    (run_dir / "baselines" / "b3").mkdir(parents=True)
    (run_dir / "manifest.json").write_text(json.dumps({"run_id": "fixture", "dataset_id": "dev-small"}), encoding="utf-8")
    candidates = [
        {"record_id": "r1", "version": 1, "data": {"age": 1, "score": 0.1, "color": "red", "label": "yes"}, "raw_output": "raw-1"},
        {"record_id": "r2", "version": 1, "data": {"age": 2, "score": 0.2, "label": "yes"}, "raw_output": "raw-2"},
        {"record_id": "r3", "version": 1, "data": {"age": 3, "score": 0.3, "color": "blue", "label": "no"}, "raw_output": "raw-3"},
    ]
    (run_dir / "candidates_raw.jsonl").write_text("\n".join(json.dumps(item) for item in candidates) + "\n", encoding="utf-8")
    (run_dir / "baselines" / "b2" / "decisions.jsonl").write_text(
        "\n".join(json.dumps(item) for item in [
            {"candidate_id": "r1", "accepted": True, "reason": "ok"},
            {"candidate_id": "r2", "accepted": False, "reason": "schema"},
            {"candidate_id": "r3", "accepted": True, "reason": "ok"},
        ]) + "\n", encoding="utf-8")
    (run_dir / "baselines" / "b3" / "decisions.jsonl").write_text(
        "\n".join(json.dumps(item) for item in [
            {"candidate_id": "r1", "accepted": False, "reason": "below threshold"},
            {"candidate_id": "r2", "accepted": True, "reason": "accepted"},
            {"candidate_id": "r3", "accepted": False, "reason": "below threshold"},
        ]) + "\n", encoding="utf-8")
    (run_dir / "baselines" / "b2" / "evidence.jsonl").write_text(json.dumps({
        "candidate_id": "r2", "verdict": "fail", "message": "schema mismatch",
    }) + "\n", encoding="utf-8")
    (run_dir / "baselines" / "b3" / "judge_results.jsonl").write_text(json.dumps({
        "candidate_id": "r1", "score": 0.2, "reasons": ["low fidelity"],
    }) + "\n", encoding="utf-8")


def test_human_review_is_bounded_deterministic_and_machine_only(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_run_fixture(run_dir)
    output = export_human_review(run_dir, cap_per_category=1)
    disagreement = export_disagreements(run_dir)
    with output.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert {row["category"] for row in rows} == set(REVIEW_CATEGORIES)
    assert all(row[column] == "" for row in rows for column in HUMAN_COLUMNS)
    assert all(column in rows[0] for column in ("record_id", "candidate_version", "target_class", "b2_reasons", "b3_score", "b3_reasons"))
    assert len({(row["record_id"], row["category"]) for row in rows}) == len(rows)
    assert analyze_human_review(output)["status"] == "not_evaluable"
    with disagreement.open(newline="", encoding="utf-8") as stream:
        disagreement_rows = list(csv.DictReader(stream))
    assert {row["record_id"] for row in disagreement_rows} == {"r1", "r2", "r3"}
    assert all(row["b2_status"] != row["b3_status"] for row in disagreement_rows)
    assert all(row["candidate_json"] and "raw_output" in row for row in disagreement_rows)
    rows[0]["human_notes"] = "reviewed but not adjudicated"
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    assert analyze_human_review(output)["status"] == "partial"


def test_cross_dataset_exposes_failure_matrix_and_both_tstr_classifiers() -> None:
    comparison = {
        "dataset_id": "dev-small",
        "requested": 2,
        "raw_pool_count": 2,
        "parse_success_rate": 1.0,
        "failure_aggregation": {"schema_failure": 1},
        "minority_analysis": {"requested_minority_label": "yes"},
        "baselines": {
            name: {"accepted": 1, "acceptance_rate": 0.5, "utility": {"TSTR": {
                "logistic_regression": {"pr_auc": 0.4, "status": "ok"},
                "random_forest": {"pr_auc": 0.3, "status": "ok"},
            }}}
            for name in ("b1", "b2", "b3")
        },
    }
    report = cross_dataset_comparison([comparison])
    row = report["datasets"][0]
    assert row["failure_matrix"]["schema_failure"] == 1
    assert row["tstr_pr_auc"]["b2"]["logistic_regression"]["pr_auc"] == 0.4
    assert row["tstr_pr_auc"]["b3"]["random_forest"]["pr_auc"] == 0.3
    assert row["minority_analysis"]["requested_minority_label"] == "yes"
    assert report["no_significance_claim"] is True
    assert report["failure_matrix"]["SCHEMA"]["dev-small"]["occurrences"] == 1


def test_smoke_usage_is_included_in_comparison_totals() -> None:
    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    plan = type("Plan", (), {"dataset_id": "dev-small", "requested_count": 1})()
    b = {"accepted": 0, "acceptance_rate": 0.0, "failure_counts": {}, "utility": {"TSTR": {}}}
    result = _comparison(
        config, plan, [], [], [], 0, 0, b, b, {**b, "judge_attempted_calls": 0, "judge_successful_calls": 0, "judge_input_tokens": 3, "judge_output_tokens": 4, "judge_total_tokens": 7, "judge_latency_ms": 2.0, "judge_cost_usd": 0.2},
        smoke_report={"status": "ok", "input_tokens": 5, "output_tokens": 6, "total_tokens": 11, "latency_ms": 1.5, "cost_usd": 0.1},
    )
    assert result["smoke_total_tokens"] == 11
    assert result["total_tokens"] == 18
    assert result["latency_ms"] == 3.5
    assert result["cost_usd"] == 0.30000000000000004


def test_real_pilot_persists_same_model_bias_metadata() -> None:
    config, _ = load_experiment_config(Path("configs/experiments/pilot/page-blocks0.yaml"))
    assert config.generator_judge_same_model is True
    assert config.generator.model == config.judge.provider.model == "gemma4:e4b"
    assert config.generator.api_key_env == config.judge.provider.api_key_env == "OLLAMA_API_KEY"


def _failure(event_id: str, parser_version: str, requested_class: str | None = None, requested_count: int | None = None) -> ParseFailureEvent:
    metadata = {
        key: value for key, value in (
            ("requested_class", requested_class), ("requested_count", requested_count)
        ) if value is not None
    }
    return ParseFailureEvent(
        event_id=event_id, run_id="run", call_id=event_id, parser_version=parser_version,
        error="test failure", recoverable=False, created_at=datetime.now(UTC), metadata=metadata,
    )


def test_generation_parse_failure_persists_requested_batch_metadata() -> None:
    parsed = parse_generation_response(
        "not-json", run_id="run", call_id="generation-0", generator_id="generator",
        generator_version="v1", prompt_version="v1", seed=42,
        requested_class="negative", requested_count=5,
    )
    assert parsed.failures[0].metadata == {"requested_class": "negative", "requested_count": 5}


def test_failure_aggregation_expands_generation_batch_slots_and_separates_judge() -> None:
    plan = SimpleNamespace(
        requested_count=40,
        class_quotas=(ClassQuota(label="negative", count=20), ClassQuota(label="positive", count=20)),
    )
    spec = SimpleNamespace(minority_label="positive")
    failures = [
        _failure("parse-negative", "json-array-v1", "negative", 5),
        _failure("provider-negative", "provider-v1", "negative", 5),
        *[_failure(f"parse-positive-{index}", "json-array-v1", "positive", 5) for index in range(4)],
        _failure("judge-provider-candidate", "provider-v1"),
    ]
    result = _aggregate_failures(failures, {}, {}, {}, plan=plan, spec=spec)
    assert result["global"]["PARSE"] == {
        "occurrences": 25, "unique_affected_record_count": 25,
        "failed_response_count": 5, "denominator": 40, "rate": 25 / 40,
    }
    assert result["by_requested_class"]["negative"]["failures"]["PARSE"]["unique_affected_record_count"] == 5
    assert result["by_requested_class"]["positive"]["failures"]["PARSE"]["unique_affected_record_count"] == 20
    assert result["majority_vs_minority"]["majority"]["failures"]["PROVIDER_ERROR"]["unique_affected_record_count"] == 5
    assert result["majority_vs_minority"]["minority"]["failures"]["PARSE"]["unique_affected_record_count"] == 20
    assert result["provider_error_breakdown"] == {
        "generation": {"failed_response_count": 1, "affected_requested_record_count": 5},
        "judge": {"failed_response_count": 1, "affected_record_count": 1},
    }


def test_baseline_comparison_exposes_not_evaluable_metrics_and_partial_usage() -> None:
    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    plan = type("Plan", (), {"dataset_id": "dev-small", "requested_count": 1})()
    empty = {"requested": 1, "raw_pool_count": 0, "accepted": 0, "acceptance_rate": None, "intrinsic": {}, "utility": {}}
    result = _comparison(
        config, plan, [], [], [], 1, 0, empty, empty, {**empty, "judge_attempted_calls": 0, "judge_successful_calls": 0},
        smoke_report={"status": "ok", "call_count": 1, "input_tokens": 3, "output_tokens": 2, "total_tokens": 5, "latency_ms": 1.0},
    )
    rows = {row["baseline"]: row for row in result["baseline_comparison"]}
    assert rows["b1"]["parse_validity"]["status"] == "not_evaluable"
    assert rows["b1"]["average_wasserstein"]["status"] == "not_evaluable"
    assert rows["b1"]["correlation_error"]["status"] == "not_evaluable"
    assert rows["b1"]["calls"]["generation"]["shared_generation_pool"] is True
    assert rows["b1"]["tokens"]["generation_usage_complete"] is False
    assert rows["b1"]["smoke"]["total_tokens"] == 5
