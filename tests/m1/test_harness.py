import json
from pathlib import Path

import pytest

from rcqasyn.config import load_experiment_config
from rcqasyn.datasets import DatasetRegistry, build_profile, load_dataset, make_split
from rcqasyn.experiments import run_experiment
from rcqasyn.generation.parser import parse_generation_response


def test_registry_and_missing_keel_paths_are_explicit() -> None:
    registry = DatasetRegistry(project_root=Path.cwd())
    assert {spec.dataset_id for spec in registry.list()} >= {"page-blocks0", "Ecoli4", "Abalone19", "dev-small"}
    assert registry.get("page-blocks0").accepted_filenames == ("page-blocks0.dat",)
    with pytest.raises(KeyError, match="available"):
        registry.get("not-registered")


def test_split_and_train_only_profile_are_repeatable() -> None:
    registry = DatasetRegistry(project_root=Path.cwd())
    dataset = load_dataset(registry.get("dev-small"), registry)
    first = make_split(dataset, 42)
    second = make_split(dataset, 42)
    assert first == second
    assert not set(first.train_indices) & set(first.test_indices)
    profile = build_profile(dataset, first, reference_example_count=3, seed=42)
    assert set(profile.train_indices) == set(first.train_indices)
    assert set(profile.reference_indices) <= set(first.train_indices)
    assert "label" in profile.domains

    test_only = first.test_indices[0]
    dataset.frame.loc[test_only, "color"] = "TEST_ONLY_SENTINEL"
    leaked_check = build_profile(dataset, first, reference_example_count=3, seed=42)
    assert "TEST_ONLY_SENTINEL" not in leaked_check.domains["color"]


def test_parser_retains_raw_response_and_partial_failure() -> None:
    parsed = parse_generation_response(
        '[{"x": 1}, 4]', run_id="run", call_id="call", generator_id="g", generator_version="1", prompt_version="p", seed=1
    )
    assert len(parsed.candidates) == 1
    assert parsed.candidates[0].raw_output == '[{"x": 1}, 4]'
    assert len(parsed.failures) == 1
    assert parsed.failures[0].recoverable is True


def test_offline_replay_uses_shared_pool_and_refuses_overwrite(tmp_path: Path) -> None:
    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    config = config.model_copy(update={"artifact_root": tmp_path, "run_id": "smoke"})
    result = run_experiment(config, project_root=Path.cwd(), replay=True)
    raw = [json.loads(line) for line in (result.artifact_dir / "candidates_raw.jsonl").read_text().splitlines()]
    b1 = [json.loads(line) for line in (result.artifact_dir / "baselines/b1/candidates.jsonl").read_text().splitlines()]
    b2 = [json.loads(line) for line in (result.artifact_dir / "baselines/b2/candidates.jsonl").read_text().splitlines()]
    b3 = [json.loads(line) for line in (result.artifact_dir / "baselines/b3/candidates.jsonl").read_text().splitlines()]
    assert [item["record_id"] for item in raw] == [item["record_id"] for item in b1]
    raw_ids = {item["record_id"] for item in raw}
    assert {item["record_id"] for item in b2} <= raw_ids
    assert {item["record_id"] for item in b3} <= raw_ids
    assert result.comparison["baselines"]["b1"]["accepted"] == 5
    assert result.comparison["baselines"]["b2"]["accepted"] == 1
    assert result.comparison["baselines"]["b3"]["accepted"] == 2
    assert result.comparison["requested"] == 6
    assert result.comparison["raw_pool_count"] == 5
    assert result.comparison["generation_attempted_calls"] == 2
    assert result.comparison["generation_successful_calls"] == 2
    assert result.comparison["generation_input_tokens"] == 120
    assert result.comparison["generation_output_tokens"] == 84
    assert result.comparison["generation_total_tokens"] == 204
    assert result.comparison["judge_input_tokens"] is None
    assert result.comparison["judge_output_tokens"] is None
    assert result.comparison["judge_total_tokens"] is None
    assert result.comparison["input_tokens"] is None
    assert result.comparison["output_tokens"] is None
    assert result.comparison["total_tokens"] is None
    assert result.comparison["generation_latency_ms"] == 0.0
    assert result.comparison["judge_latency_ms"] == 0.0
    assert result.comparison["generation_cost_usd"] is None
    assert result.comparison["judge_cost_usd"] is None
    assert result.comparison["failure_aggregation"]["target_wrong"] == 2
    traces = [json.loads(line) for line in (result.artifact_dir / "provider_calls.jsonl").read_text().splitlines()]
    assert {trace["requested_class"] for trace in traces if trace["role"] == "generation"} == {"no", "yes"}
    assert all(trace["prompt"] and trace["raw_response"] is not None for trace in traces)
    candidates = [json.loads(line) for line in (result.artifact_dir / "candidates_raw.jsonl").read_text().splitlines()]
    assert all("provider_call_id" in candidate["metadata"] for candidate in candidates)
    assert all("requested_class" in candidate["metadata"] for candidate in candidates)
    with pytest.raises(FileExistsError):
        run_experiment(config, project_root=Path.cwd(), replay=True)


def test_explicit_quotas_validate_against_train_labels(tmp_path: Path) -> None:
    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    generation = config.generation.model_copy(update={"class_strategy": "explicit", "class_quotas": {"not-in-train": 6}})
    invalid = config.model_copy(update={"generation": generation, "artifact_root": tmp_path, "run_id": "invalid-labels"})
    with pytest.raises(ValueError, match="absent from TRAIN"):
        run_experiment(invalid, project_root=Path.cwd(), replay=True)
