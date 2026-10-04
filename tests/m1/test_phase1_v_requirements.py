"""Recorded inputs, rather than mutually agreeing copies, determine requirements."""

import copy
import json

import pytest
import yaml
from test_phase1_final_readers import bundle as _bundle_fixture
from test_phase1_final_readers import edit, refreshed_bindings, reseal
from test_phase1_final_readers import source as _source_fixture

from rcqasyn.config.experiment import ExperimentConfig
from rcqasyn.contracts.m1 import execution_outcome
from rcqasyn.datasets.profile import DatasetProfile
from rcqasyn.experiments.readers import read_bundle
from rcqasyn.experiments.recorded_requirements import validate_recorded_requirements
from rcqasyn.experiments.specification import fingerprint

bundle = _bundle_fixture
source = _source_fixture


def rewrite_science(directory, mutate):
    """Rebind a scientifically contradictory bundle without stale packaging hashes."""
    path = directory / "scientific_specification.json"
    scientific = json.loads(path.read_text())
    old_science = scientific["fingerprint"]
    old_controls = {
        name: control["fingerprint"]
        for name, control in scientific["specification"]["controls"].items()
    }
    mutate(scientific["specification"])
    replacements = {}
    for name, control in scientific["specification"]["controls"].items():
        control["fingerprint"] = fingerprint(control["descriptor"])
        replacements[old_controls[name]] = control["fingerprint"]
    scientific["fingerprint"] = fingerprint(scientific["specification"])
    replacements[old_science] = scientific["fingerprint"]
    path.write_text(json.dumps(scientific), encoding="utf-8")

    def replace(value):
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        if isinstance(value, list):
            return [replace(item) for item in value]
        if isinstance(value, str):
            return replacements.get(value, value)
        return value

    for artifact in directory.rglob("*.json"):
        if artifact.name in {"scientific_specification.json", "FINALIZED.json"}:
            continue
        original = json.loads(artifact.read_text())
        rebound = replace(original)
        if rebound != original:
            artifact.write_text(json.dumps(rebound), encoding="utf-8")
    refreshed_bindings(directory, metrics=True)
    reseal(directory)


def reject_rebound(directory):
    refreshed_bindings(directory, metrics=True)
    reseal(directory)
    with pytest.raises(ValueError, match="identity|required"):
        read_bundle(directory)


def test_rebinding_all_scientific_copies_preserves_an_unchanged_bundle(bundle):
    before = read_bundle(bundle)
    rewrite_science(bundle, lambda spec: None)
    after = read_bundle(bundle)
    assert after["baselines"] == before["baselines"]
    assert after["specification_fingerprint"] == before["specification_fingerprint"]


@pytest.mark.parametrize(
    "baseline,key,value",
    [
        ("b1", "admission", "accept_nothing"),
        ("b1", "parser_policy", "silently_truncate"),
        ("b2", "missing", "always_accept"),
        ("b2", "categories", "accept_train_unseen"),
        ("b2", "range", "ignore_ranges"),
        ("b2", "duplicates", "accept_duplicates"),
        ("b2", "schema", "allow_extra_keys"),
        ("b2", "train_domains", {"color": ["unobserved"], "label": ["no", "yes"]}),
        ("b2", "train_ranges", {"age": {"min": -100, "max": 999}}),
        ("b3", "threshold", 0.1),
        ("b3", "provider", {"kind": "foreign", "model": "foreign"}),
        ("b3", "prompt_sha256", "0" * 64),
        ("b3", "train_context_sha256", "0" * 64),
        ("b3", "verdicts", ["pass", "warn", "fail"]),
        ("b3", "context_identity", "heldout-context"),
    ],
)
def test_resealed_descriptors_must_follow_recorded_execution_inputs(bundle, baseline, key, value):
    rewrite_science(
        bundle, lambda spec: spec["controls"][baseline]["descriptor"].update({key: value})
    )
    reject_rebound(bundle)


@pytest.mark.parametrize(
    "baseline,key",
    [
        ("b1", "admission"),
        ("b1", "evaluation_schema"),
        ("b2", "missing"),
        ("b2", "validators"),
        ("b2", "dataset_validation"),
        ("b3", "threshold"),
        ("b3", "provider"),
        ("b3", "prompt_sha256"),
        ("b3", "verdicts"),
    ],
)
def test_resealed_descriptors_cannot_drop_required_semantics(bundle, baseline, key):
    rewrite_science(bundle, lambda spec: spec["controls"][baseline]["descriptor"].pop(key))
    reject_rebound(bundle)


def test_resealed_judge_descriptor_cannot_change_only_the_model(bundle):
    rewrite_science(
        bundle,
        lambda spec: spec["controls"]["b3"]["descriptor"]["provider"].update(model="foreign"),
    )
    reject_rebound(bundle)


@pytest.mark.parametrize("baseline", ["b1", "b2", "b3"])
def test_resealed_evaluation_schema_is_bound_to_recorded_definition(bundle, baseline):
    rewrite_science(
        bundle,
        lambda spec: spec["controls"][baseline]["descriptor"]["evaluation_schema"].update(
            numerical_columns=["age"]
        ),
    )
    reject_rebound(bundle)


@pytest.mark.parametrize("field", ["target_column", "feature_columns", "numerical_columns"])
def test_recorded_dataset_definition_cannot_omit_required_schema(bundle, field):
    rewrite_science(bundle, lambda spec: spec["dataset"]["definition"].pop(field))
    reject_rebound(bundle)


def test_recorded_dataset_definition_must_validate_column_partition(bundle):
    rewrite_science(
        bundle, lambda spec: spec["dataset"]["definition"].update(categorical_columns=["age"])
    )
    reject_rebound(bundle)


def drop_intrinsic_family(metric, family, removed):
    if family == "numeric_columns":
        metric["numeric"].pop(removed)
        metric["diversity"]["numeric_variance_ratio"].pop(removed, None)
        for row in metric["class_conditional"]["classes"].values():
            row["numeric"].pop(removed)
    elif family in {"categorical_columns", "class_categorical_columns"}:
        if family == "categorical_columns":
            metric["categorical"].pop(removed, None)
        metric["diversity"]["categorical_entropy"].pop(removed, None)
        for row in metric["class_conditional"]["classes"].values():
            row["categorical"].pop(removed, None)
    else:
        metric["class_conditional"]["classes"].pop(removed)


def refresh_outcome(directory):
    comparison = json.loads((directory / "comparison.json").read_text())
    comparison["outcome"] = execution_outcome(comparison).model_dump(mode="json")
    (directory / "comparison.json").write_text(json.dumps(comparison), encoding="utf-8")
    edit(
        directory,
        "manifest.json",
        lambda manifest: manifest.update(
            outcome=comparison["outcome"], success=comparison["outcome"]["success"]
        ),
    )


@pytest.mark.parametrize(
    "family,removed",
    [
        ("numeric_columns", "score"),
        ("categorical_columns", "color"),
        ("categorical_columns", "label"),
        ("class_categorical_columns", "color"),
        ("classes", "yes"),
    ],
)
def test_result_families_cannot_be_removed_from_all_agreeing_copies(bundle, family, removed):
    def shrink(spec):
        spec["evaluation"]["result_families"][family].remove(removed)
        if family == "categorical_columns" and removed == "color":
            spec["evaluation"]["result_families"]["class_categorical_columns"].remove(removed)

    rewrite_science(bundle, shrink)
    spec = json.loads((bundle / "scientific_specification.json").read_text())["specification"]
    edit(
        bundle,
        "comparison.json",
        lambda comparison: comparison.update(
            configured_results=copy.deepcopy(spec["evaluation"]["result_families"])
        ),
    )
    for baseline in ("b1", "b2", "b3"):
        edit(
            bundle,
            f"baselines/{baseline}/metrics.json",
            lambda metric: drop_intrinsic_family(metric, family, removed),
        )
        metric = json.loads((bundle / f"baselines/{baseline}/metrics.json").read_text())
        edit(
            bundle,
            "comparison.json",
            lambda comparison, baseline=baseline, metric=metric: comparison["baselines"][
                baseline
            ].update(intrinsic=metric),
        )
    refresh_outcome(bundle)
    reject_rebound(bundle)


@pytest.mark.parametrize("key", ["version", "pr_auc", "positive_label", "preprocessing"])
def test_resealed_evaluation_cannot_drop_metric_semantics(bundle, key):
    rewrite_science(bundle, lambda spec: spec["evaluation"].pop(key))
    reject_rebound(bundle)


@pytest.mark.parametrize("baseline", ["b1", "b2", "b3"])
def test_resealed_control_cannot_be_removed_from_all_agreeing_copies(bundle, baseline):
    rewrite_science(bundle, lambda spec: spec["controls"].pop(baseline))
    edit(bundle, "comparison.json", lambda comparison: comparison["baselines"].pop(baseline))
    refreshed_bindings(bundle, metrics=True)
    reseal(bundle)
    with pytest.raises(ValueError, match="identity|required|baseline"):
        read_bundle(bundle)


def test_resealed_control_estimator_parameters_follow_recorded_evaluation(bundle):
    rewrite_science(
        bundle,
        lambda spec: spec["controls"]["b1"]["descriptor"]["estimator_parameters"][
            "logistic_regression"
        ].update(max_iter=1),
    )
    reject_rebound(bundle)


def test_classifier_family_cannot_be_removed_from_all_agreeing_result_copies(bundle):
    removed = "random_forest"

    def shrink(spec):
        spec["evaluation"]["classifiers"].remove(removed)
        spec["evaluation"]["estimator_parameters"].pop(removed)
        for control in spec["controls"].values():
            control["descriptor"]["classifiers"].remove(removed)
            control["descriptor"]["estimator_parameters"].pop(removed)

    rewrite_science(bundle, shrink)
    edit(
        bundle,
        "comparison.json",
        lambda comparison: comparison["configured_classifiers"].remove(removed),
    )
    for baseline in ("b1", "b2", "b3"):
        def shrink_utility(metric):
            for population in ("TRTR", "TSTR"):
                metric[population].pop(removed)

        edit(bundle, f"baselines/{baseline}/classifier_metrics.json", shrink_utility)
        metric = json.loads((bundle / f"baselines/{baseline}/classifier_metrics.json").read_text())
        edit(
            bundle,
            "comparison.json",
            lambda comparison, baseline=baseline, metric=metric: comparison["baselines"][
                baseline
            ].update(utility=metric),
        )
    refresh_outcome(bundle)
    reject_rebound(bundle)


def recorded_inputs(directory):
    spec = json.loads((directory / "scientific_specification.json").read_text())["specification"]
    config = ExperimentConfig.model_validate(
        yaml.safe_load((directory / "resolved_config.yaml").read_text())
    )
    profile = DatasetProfile.model_validate_json((directory / "dataset/profile_source.json").read_text())
    return spec, config, profile


def test_requirements_use_recorded_estimator_parameters_without_current_defaults(bundle, monkeypatch):
    from rcqasyn.experiments import specification

    spec, config, profile = recorded_inputs(bundle)

    def unavailable_defaults(*args):
        raise AssertionError("historical requirements must not consult current estimator defaults")

    monkeypatch.setattr(specification, "_estimator_parameters", unavailable_defaults)
    validate_recorded_requirements(spec, config, profile)


def test_normalized_train_labels_preserve_a_literal_missing_sentinel(bundle):
    spec, config, profile = recorded_inputs(bundle)
    profile = profile.model_copy(update={"class_counts": {**profile.class_counts, "<MISSING>": 1}})
    control = spec["controls"]["b3"]
    control["descriptor"]["train_context_sha256"] = fingerprint(profile.to_generation_context())
    control["fingerprint"] = fingerprint(control["descriptor"])
    spec["evaluation"]["result_families"]["classes"] = ["<MISSING>", "no", "yes"]
    validate_recorded_requirements(
        spec, config, profile, train_classes=["<MISSING>", "no", "yes"]
    )
