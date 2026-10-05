"""Adversarial tests of executable M1 partition and provider boundaries."""

from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from rcqasyn.config import load_experiment_config
from rcqasyn.datasets import DatasetRegistry, build_profile, load_dataset, make_split
from rcqasyn.experiments import run_experiment
from rcqasyn.metrics import utility_metrics


def fixture_data():
    registry = DatasetRegistry(project_root=Path.cwd())
    dataset = load_dataset(registry.get("dev-small"), registry)
    return dataset, make_split(dataset, 42)


@pytest.mark.parametrize("fault", ["overlap", "missing", "duplicate", "foreign"])
def test_profile_rejects_invalid_partition(fault):
    dataset, split = fixture_data()
    changes = {
        "overlap": {"test_indices": (*split.test_indices, split.train_indices[0])},
        "missing": {"train_indices": split.train_indices[1:]},
        "duplicate": {"train_indices": (*split.train_indices, split.train_indices[0])},
        "foreign": {"dataset_id": "another-dataset"},
    }
    with pytest.raises(ValueError, match="partition|dataset"):
        build_profile(dataset, replace(split, **changes[fault]))


def test_unsupported_non_stratified_split_fails():
    dataset, _ = fixture_data()
    spec = dataset.spec.model_copy(
        update={"split": dataset.spec.split.model_copy(update={"stratify": False})}
    )
    with pytest.raises(ValueError, match="stratif"):
        make_split(replace(dataset, spec=spec), 42)


def test_safe_context_is_independent_of_test_features_and_labels():
    dataset, split = fixture_data()
    before = build_profile(dataset, split, seed=42)
    changed = dataset.frame.copy()
    changed.loc[list(split.test_indices), "age"] = 999999
    changed.loc[list(split.test_indices), "color"] = "TEST_ONLY"
    changed.loc[list(split.test_indices), "label"] = "TEST_LABEL"
    after = build_profile(replace(dataset, frame=changed), split, seed=42)
    assert before.numeric_summary == after.numeric_summary
    assert before.domains == after.domains
    assert before.reference_examples == after.reference_examples
    assert before.to_generation_context() == after.to_generation_context()


def test_unsafe_fresh_context_fails_before_provider_construction(tmp_path, monkeypatch):
    from rcqasyn.experiments import runner

    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    config = config.model_copy(update={"artifact_root": tmp_path})
    contacts = []
    monkeypatch.setattr(runner, "_require_real_provider", lambda config: None)
    monkeypatch.setattr(runner, "_provider", lambda *args: contacts.append(args))
    with pytest.raises(ValueError, match="TRAIN|context"):
        run_experiment(config, project_root=Path.cwd(), replay=False)
    assert contacts == []
    assert not (tmp_path / "runs").exists()


def test_recorded_replay_does_not_render_test_lineage(tmp_path):
    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    result = run_experiment(config.model_copy(update={"artifact_root": tmp_path}), replay=True)
    import json

    profile = json.loads((result.artifact_dir / "dataset/profile.json").read_text())
    for path in [
        result.artifact_dir / "provider_calls.jsonl",
        result.artifact_dir / "baselines/b3/provider_calls.jsonl",
    ]:
        for line in path.read_text().splitlines():
            trace = json.loads(line)
            assert profile["dataset_fingerprint"] not in trace["prompt"]
            assert profile["split_fingerprint"] not in trace["prompt"]


def test_preprocessing_fits_only_training_population(monkeypatch):
    dataset, split = fixture_data()
    train = dataset.frame.loc[list(split.train_indices)].copy()
    test = dataset.frame.loc[list(split.test_indices)].copy()
    test.loc[:, "age"] = 999999
    test.loc[:, "color"] = "TEST_ONLY"
    fits = []
    for cls in (SimpleImputer, StandardScaler, OneHotEncoder):
        original = cls.fit

        def spy(self, values, *args, _original=original, **kwargs):
            snapshot = pd.DataFrame(values).astype(str)
            assert not snapshot.isin(["999999", "999999.0", "TEST_ONLY"]).any().any()
            fits.append(type(self).__name__)
            return _original(self, values, *args, **kwargs)

        monkeypatch.setattr(cls, "fit", spy)
    result = utility_metrics(train, test, train.copy(), dataset.spec, seed=42)
    assert result["TRTR"]["random_forest"]["status"] == "ok"
    assert {"SimpleImputer", "StandardScaler", "OneHotEncoder"} <= set(fits)


def test_fresh_provider_and_judge_inputs_ignore_test_only_changes(tmp_path, monkeypatch):
    from dataclasses import replace

    from rcqasyn.experiments import runner
    from rcqasyn.generation.provider import ProviderResponse, ReplayProvider

    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    config = config.model_copy(
        update={
            "run_id": None,
            "generation": config.generation.model_copy(
                update={"transport_version": "v2", "prompt_version": "v2"}
            ),
        }
    )
    provider_inputs = []

    class RecordingProvider:
        def __init__(self, fixture):
            self.recorded = ReplayProvider(fixture)

        def call(self, **kwargs):
            provider_inputs.append(kwargs.copy())
            if '"ok":true' in kwargs["prompt"]:
                return ProviderResponse(
                    response='{"ok":true}', provider="fixture", model="fixture", endpoint=None
                )
            return self.recorded.call(**kwargs)

    monkeypatch.setattr(runner, "_require_real_provider", lambda config: None)
    monkeypatch.setattr(
        runner, "_provider", lambda provider, root, replay: RecordingProvider(provider.fixture)
    )
    first = run_experiment(
        config.model_copy(update={"artifact_root": tmp_path / "one"}), replay=False
    )
    before = provider_inputs.copy()
    provider_inputs.clear()
    original_load = runner.load_dataset

    def perturbed(*args):
        dataset = original_load(*args)
        split = make_split(dataset, 42)
        frame = dataset.frame.copy()
        frame.loc[list(split.test_indices), "age"] = 999999
        frame.loc[list(split.test_indices), "color"] = "TEST_ONLY"
        frame.loc[list(split.test_indices), "label"] = "TEST_LABEL"
        # Preserve the approved partition membership for a counterfactual test;
        # modifying labels before the split would deliberately change stratification.
        return replace(dataset, frame=frame)

    original_split = runner.make_split
    saved_dataset = original_load(
        DatasetRegistry(project_root=Path.cwd()).get("dev-small"),
        DatasetRegistry(project_root=Path.cwd()),
    )
    monkeypatch.setattr(runner, "load_dataset", perturbed)
    monkeypatch.setattr(
        runner, "make_split", lambda dataset, seed: original_split(saved_dataset, seed)
    )
    second = run_experiment(
        config.model_copy(update={"artifact_root": tmp_path / "two"}), replay=False
    )
    assert before == provider_inputs
    for name in ("b1", "b2", "b3"):
        a, b = first.comparison["baselines"][name], second.comparison["baselines"][name]
        assert a["accepted"] == b["accepted"]
        assert a["failure_counts"] == b["failure_counts"]
    assert all(
        "TEST_ONLY" not in call["prompt"] and "TEST_LABEL" not in call["prompt"]
        for call in provider_inputs
    )
