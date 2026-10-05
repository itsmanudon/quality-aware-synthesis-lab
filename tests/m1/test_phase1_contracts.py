import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from rcqasyn.config import load_experiment_config
from rcqasyn.contracts.m1 import M1Outcome
from rcqasyn.experiments import run_experiment
from rcqasyn.experiments.specification import scientific_specification
from rcqasyn.storage.artifacts import write_json


def config_at(tmp_path):
    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    return config.model_copy(update={"artifact_root": tmp_path, "run_id": None})


def test_scientific_identity_excludes_execution_location(tmp_path):
    config = config_at(tmp_path)
    first = scientific_specification(config, Path.cwd(), replay=True)
    other = config.model_copy(update={"run_id": "other", "artifact_root": tmp_path / "other"})
    assert first == scientific_specification(other, Path.cwd(), replay=True)
    seeded = config.model_copy(
        update={"dataset": config.dataset.model_copy(update={"root_seed": 43})}
    )
    assert (
        first["fingerprint"]
        != scientific_specification(seeded, Path.cwd(), replay=True)["fingerprint"]
    )


def test_distinct_executions_share_spec_and_are_sealed(tmp_path):
    config = config_at(tmp_path)
    first, second = [run_experiment(config, replay=True) for _ in range(2)]
    assert first.run_id != second.run_id
    manifests = [
        json.loads((run.artifact_dir / "manifest.json").read_text()) for run in (first, second)
    ]
    assert manifests[0]["specification_fingerprint"] == manifests[1]["specification_fingerprint"]
    for run, manifest in zip((first, second), manifests):
        assert manifest["status"] == "finalized"
        assert (run.artifact_dir / "FINALIZED.json").exists()
        assert manifest["seed_provenance"]["provider_reproduction_guaranteed"] is False
        with pytest.raises(FileExistsError):
            write_json(run.artifact_dir / "comparison.json", {}, overwrite=True)


def test_exclusive_json_creation_has_one_winner(tmp_path):
    def attempt(_):
        try:
            write_json(tmp_path / "one.json", {"ok": True})
            return True
        except FileExistsError:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(8))) == 1


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_json_rejects_nonfinite_values(tmp_path, bad):
    with pytest.raises(ValueError):
        write_json(tmp_path / "bad.json", {"metric": bad})
    assert not (tmp_path / "bad.json").exists()


def test_required_lifecycle_contract():
    with pytest.raises(ValueError):
        M1Outcome.model_validate({"success": True})


def test_seed_provenance_absent_seed_and_fixed_split_snapshot(tmp_path):
    from rcqasyn.datasets import DatasetRegistry, load_dataset, make_split

    registry = DatasetRegistry(project_root=Path.cwd())
    data = load_dataset(registry.get("dev-small"), registry)
    split = make_split(data, 42)
    assert split.train_indices == (1, 3, 4, 6, 7, 8, 9, 10, 11, 13, 14, 15)
    assert split.test_indices == (0, 2, 5, 12)
    assert (
        split.to_dict()["split_fingerprint"]
        == "4c4a700b8cedf75b1a55d338310449496412e6deea373a660fbe8688d073dde8"
    )
    assert (
        split.to_dict()["split_fingerprint"] != make_split(data, 43).to_dict()["split_fingerprint"]
    )
    config = config_at(tmp_path)
    config = config.model_copy(
        update={"generation": config.generation.model_copy(update={"provider_seed": None})}
    )
    run = run_experiment(config, replay=True)
    manifest = json.loads((run.artifact_dir / "manifest.json").read_text())
    provenance = manifest["seed_provenance"]
    assert provenance["root_seed"] == 42 and provenance["split_seed"] == split.split_seed
    assert provenance["judge_seed"] is None
    assert provenance["generation"]["all_seeds_unique"] is None
    assert "absent" in provenance["provider_limitation"]
    assert manifest["git_dirty"] is not None and manifest["git_commit"]
    assert manifest["environment"]["packages"]["scikit-learn"]


def test_required_metric_fields_and_status_cannot_be_forged(tmp_path):
    from copy import deepcopy

    from rcqasyn.contracts.m1 import validate_comparison

    run = run_experiment(config_at(tmp_path), replay=True)
    value = deepcopy(run.comparison)
    value["baselines"]["b1"]["utility"]["TRTR"].pop("random_forest")
    with pytest.raises(ValueError):
        validate_comparison(value)
    value = deepcopy(run.comparison)
    value["baselines"]["b1"]["utility"]["TRTR"]["random_forest"]["f1"] = None
    with pytest.raises(ValueError):
        validate_comparison(value)


def test_null_metrics_cannot_be_declared_evaluable(tmp_path):
    from copy import deepcopy

    from rcqasyn.contracts.m1 import UTILITY_METRICS, execution_outcome, validate_comparison

    run = run_experiment(config_at(tmp_path), replay=True)
    value = deepcopy(run.comparison)
    for baseline in value["baselines"].values():
        baseline["utility"]["evaluation_status"] = "evaluable"
        for population in ("TRTR", "TSTR"):
            for row in baseline["utility"][population].values():
                row["status"] = "failed"
                row["evaluation_status"] = "evaluable"
                for metric in UTILITY_METRICS:
                    row[metric] = None
                    row["metric_availability"][metric] = {
                        "status": "unavailable",
                        "reason": "failed",
                    }
    value["outcome"] = execution_outcome(value).model_dump(mode="json")
    with pytest.raises(ValueError, match="evaluab"):
        validate_comparison(value)


def test_runner_binds_spec_to_already_resolved_population(tmp_path, monkeypatch):
    from rcqasyn.experiments import specification

    def forbidden_reload(*args, **kwargs):
        raise AssertionError("specification must not reload execution data")

    monkeypatch.setattr(specification, "load_dataset", forbidden_reload)
    run = run_experiment(config_at(tmp_path), replay=True)
    saved = json.loads((run.artifact_dir / "scientific_specification.json").read_text())
    manifest = json.loads((run.artifact_dir / "manifest.json").read_text())
    assert (
        saved["specification"]["dataset"]["normalized_fingerprint"]
        == manifest["dataset_fingerprint"]
    )


def test_same_spec_rerun_keeps_sampling_inputs_stable_above_cap(tmp_path, monkeypatch):
    import csv
    from dataclasses import replace

    from rcqasyn.generation.provider import ProviderResponse, ReplayProvider

    original = ReplayProvider.call

    def expanded(self, **kwargs):
        if kwargs["role"] == "judge":
            return ProviderResponse(
                response='{"score":1,"verdict":"pass"}',
                provider="fixture",
                model="fixture",
                endpoint=None,
                call_id="provider-call",
            )
        response = original(self, **kwargs)
        records = [
            {
                "age": i + 2,
                "score": 0.1,
                "color": "red",
                "label": "no" if kwargs["request_index"] == 0 else "yes",
            }
            for i in range(12)
        ]
        return replace(response, response=json.dumps(records), call_id="provider-call")

    monkeypatch.setattr(ReplayProvider, "call", expanded)
    config = config_at(tmp_path)
    first, second = [run_experiment(config, replay=True) for _ in range(2)]
    selections = []
    for run in (first, second):
        with (run.artifact_dir / "human_review.csv").open(encoding="utf-8", newline="") as stream:
            selections.append([(r["category"], r["record_id"]) for r in csv.DictReader(stream)])
    assert first.comparison["raw_pool_count"] == 24
    assert selections[0] == selections[1]
    assert first.comparison["generation_accounting"]["status"] == "overproduction"


def test_replay_fixture_change_during_resolution_fails_before_execution(tmp_path, monkeypatch):
    from rcqasyn.experiments import runner

    config = config_at(tmp_path)
    fixture = tmp_path / "fixture.json"
    fixture.write_bytes(config.generator.fixture.read_bytes())
    config = config.model_copy(
        update={"generator": config.generator.model_copy(update={"fixture": fixture})}
    )
    original = runner._provider

    def changed(provider, root, replay):
        resolved = original(provider, root, replay)
        if provider.fixture == fixture:
            fixture.write_bytes(fixture.read_bytes() + b" ")
        return resolved

    monkeypatch.setattr(runner, "_provider", changed)
    with pytest.raises(ValueError, match="provenance"):
        run_experiment(config, replay=True)
    assert not (tmp_path / "runs").exists()


def test_missing_baseline_diagnostics_and_accounting_are_not_success(tmp_path):
    from copy import deepcopy

    from rcqasyn.contracts.m1 import validate_comparison

    run = run_experiment(config_at(tmp_path), replay=True)
    for key in ("intrinsic", "accepted", "judge_successful_calls"):
        value = deepcopy(run.comparison)
        value["baselines"]["b3"].pop(key)
        with pytest.raises(ValueError, match="required"):
            validate_comparison(value)


def test_fully_evaluable_offline_execution_can_report_success(tmp_path, monkeypatch):
    from dataclasses import replace

    from rcqasyn.datasets import DatasetRegistry, load_dataset, make_split
    from rcqasyn.generation.provider import ProviderResponse, ReplayProvider

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
        records = train[train["label"] == label].iloc[:3].to_json(orient="records")
        return replace(response, response=records)

    monkeypatch.setattr(ReplayProvider, "call", valid)
    run = run_experiment(config_at(tmp_path), replay=True)
    assert run.comparison["outcome"]["success"] is True
    assert run.comparison["outcome"]["utility_evaluable"] is True


def test_contradictory_judge_or_failed_diagnostics_cannot_claim_success(tmp_path):
    from copy import deepcopy

    from rcqasyn.contracts.m1 import execution_outcome, validate_comparison

    run = run_experiment(config_at(tmp_path), replay=True)
    value = deepcopy(run.comparison)
    judge = value["baselines"]["b3"]
    judge.update(
        judge_attempted_calls=1,
        judge_successful_calls=0,
        judge_provider_failures=0,
        judge_malformed=0,
        judge_calls=1,
    )
    with pytest.raises(ValueError, match="accounting"):
        validate_comparison(value)
    value = deepcopy(run.comparison)
    value["baselines"]["b3"]["intrinsic"]["status"] = "failed"
    state = execution_outcome(value).components["b3.diagnostics"]
    assert state.status == "failed"


def test_missing_nested_intrinsic_fields_are_invalid(tmp_path):
    from copy import deepcopy

    from rcqasyn.contracts.m1 import validate_comparison

    run = run_experiment(config_at(tmp_path), replay=True)
    for group in ("correlations", "diversity", "class_conditional"):
        value = deepcopy(run.comparison)
        value["baselines"]["b1"]["intrinsic"][group] = {}
        with pytest.raises(ValueError, match="required"):
            validate_comparison(value)
