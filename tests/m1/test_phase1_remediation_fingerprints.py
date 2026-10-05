import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from rcqasyn.config import load_experiment_config
from rcqasyn.datasets import DatasetRegistry, load_dataset, make_split
from rcqasyn.experiments.specification import scientific_specification
from rcqasyn.metrics import utility
from rcqasyn.storage.ownership import file_hash


@pytest.fixture
def resolved():
    root = Path.cwd()
    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    registry = DatasetRegistry(project_root=root)
    dataset = load_dataset(registry.get(config.dataset.dataset_id), registry)
    split = make_split(dataset, config.dataset.root_seed)
    return config, root, dataset, split


def scientific(resolved, *, config=None, dataset=None, prompt_hashes=None):
    original, root, source, split = resolved
    effective_dataset = dataset or source
    train_bytes = effective_dataset.frame.loc[list(split.train_indices)].to_json(
        orient="split", date_format="iso", default_handler=str,
    ).encode()
    split = replace(split, train_fingerprint=hashlib.sha256(train_bytes).hexdigest())
    return scientific_specification(
        config or original, root, replay=True, dataset=effective_dataset, split=split,
        prompt_hashes=prompt_hashes or {"generation": "generation-bytes", "judge": "judge-bytes"},
        raw_source_sha256=file_hash(source.path),
    )


@pytest.mark.parametrize("constructor,parameter,value", [
    ("LogisticRegression", "C", 0.25),
    ("RandomForestClassifier", "max_depth", 3),
    ("RandomForestClassifier", "criterion", "entropy"),
    ("RandomForestClassifier", "max_features", None),
    ("RandomForestClassifier", "bootstrap", False),
])
def test_effective_estimator_changes_bind_scientific_and_control_identity(
    resolved, monkeypatch, constructor, parameter, value,
):
    before = scientific(resolved)
    actual_constructor = getattr(utility, constructor)

    def changed_constructor(**kwargs):
        return actual_constructor(**{**kwargs, parameter: value})

    monkeypatch.setattr(utility, constructor, changed_constructor)
    after = scientific(resolved)
    assert before["fingerprint"] != after["fingerprint"]
    for control in ("b1", "b2", "b3"):
        assert before["specification"]["controls"][control]["fingerprint"] != after["specification"]["controls"][control]["fingerprint"]


@pytest.mark.parametrize("change", ["missing_policy", "numerical_columns", "target_column"])
def test_b2_identity_binds_resolved_dataset_validation_schema(resolved, change):
    _, _, dataset, _ = resolved
    before = scientific(resolved)
    changes = {
        "missing_policy": {"missing_policy": "reject"},
        "numerical_columns": {"numerical_columns": ("age",), "categorical_columns": ("score", "color")},
        "target_column": {"target_column": "alternate-label"},
    }
    frame = dataset.frame.copy()
    if change == "target_column":
        frame["alternate-label"] = frame["label"]
    altered = replace(dataset, spec=dataset.spec.model_copy(update=changes[change]), frame=frame)
    after = scientific(resolved, dataset=altered)
    assert before["specification"]["controls"]["b2"]["fingerprint"] != after["specification"]["controls"]["b2"]["fingerprint"]


@pytest.mark.parametrize("column,value", [("age", 987654), ("color", "NEW_TRAIN_DOMAIN")])
def test_b2_identity_binds_train_ranges_and_category_domains(resolved, column, value):
    _, _, dataset, split = resolved
    before = scientific(resolved)
    frame = dataset.frame.copy()
    frame.loc[split.train_indices[0], column] = value
    after = scientific(resolved, dataset=replace(dataset, frame=frame))
    assert before["specification"]["controls"]["b2"]["fingerprint"] != after["specification"]["controls"]["b2"]["fingerprint"]


@pytest.mark.parametrize("change", ["provider_kind", "model", "prompt_bytes", "train_context"])
def test_b3_identity_binds_provider_model_prompt_bytes_and_train_context(resolved, change):
    config, _, dataset, split = resolved
    before = scientific(resolved)
    changes = {}
    if change in {"provider_kind", "model"}:
        update = {"kind": "fixture"} if change == "provider_kind" else {"model": "another-judge"}
        changes["config"] = config.model_copy(update={
            "judge": config.judge.model_copy(update={"provider": config.judge.provider.model_copy(update=update)})
        })
    elif change == "prompt_bytes":
        changes["prompt_hashes"] = {"generation": "generation-bytes", "judge": "new-bytes-same-version"}
    else:
        frame = dataset.frame.copy()
        frame.loc[split.train_indices[0], "age"] = 987654
        changes["dataset"] = replace(dataset, frame=frame)
    after = scientific(resolved, **changes)
    assert before["specification"]["controls"]["b3"]["fingerprint"] != after["specification"]["controls"]["b3"]["fingerprint"]


def test_controls_do_not_bind_held_out_values_or_execution_metadata(resolved):
    config, _, dataset, split = resolved
    before = scientific(resolved)
    frame = dataset.frame.copy()
    frame.loc[list(split.test_indices), "age"] = 987654
    frame.loc[list(split.test_indices), "color"] = "TEST_ONLY_DOMAIN"
    frame.loc[list(split.test_indices), "label"] = "TEST_ONLY_LABEL"
    after = scientific(
        resolved, dataset=replace(dataset, frame=frame),
        config=config.model_copy(update={"run_id": "unrelated-execution", "artifact_root": Path("unrelated-artifacts")}),
    )
    assert before["specification"]["controls"] == after["specification"]["controls"]


def test_effective_estimators_preserve_frozen_constructor_policy(resolved):
    config, _, _, _ = resolved
    specification = scientific(resolved)["specification"]
    parameters = specification["evaluation"]["estimator_parameters"]
    assert parameters["logistic_regression"]["C"] == 1.0
    assert parameters["logistic_regression"]["max_iter"] == 300
    assert parameters["logistic_regression"]["solver"] == "liblinear"
    assert parameters["random_forest"]["n_estimators"] == 50
    assert parameters["random_forest"]["max_depth"] is None
    assert parameters["random_forest"]["criterion"] == "gini"
    assert parameters["random_forest"]["max_features"] == "sqrt"
    assert parameters["random_forest"]["bootstrap"] is True
    assert all(model["random_state"] == config.dataset.root_seed for model in parameters.values())
