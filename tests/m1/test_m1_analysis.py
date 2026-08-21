import csv
import json
from pathlib import Path

from rcqasyn.config import load_experiment_config
from rcqasyn.datasets import DatasetRegistry, build_profile, load_dataset, make_split
from rcqasyn.experiments.analysis import (
    HUMAN_COLUMNS,
    REVIEW_CATEGORIES,
    analyze_human_review,
    cross_dataset_comparison,
    export_human_review,
)
from rcqasyn.experiments.runner import _comparison


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
    with output.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert {row["category"] for row in rows} == set(REVIEW_CATEGORIES)
    assert all(row[column] == "" for row in rows for column in HUMAN_COLUMNS)
    assert all(column in rows[0] for column in ("record_id", "candidate_version", "target_class", "b2_reasons", "b3_score", "b3_reasons"))
    assert len({(row["record_id"], row["category"]) for row in rows}) == len(rows)
    assert analyze_human_review(output)["status"] == "not_evaluable"
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
