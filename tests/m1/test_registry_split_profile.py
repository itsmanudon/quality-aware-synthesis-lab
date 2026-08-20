from pathlib import Path

import pytest

from rcqasyn.datasets import DatasetRegistry, build_profile, load_dataset, make_split
from rcqasyn.generation.prompts import load_prompt


def test_registry_invalid_spec_and_missing_local_placement(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(
        "dataset_id: broken\n"
        "display_name: Broken\n"
        "raw_path: data/broken.dat\n"
        "target_column: label\n"
        "feature_columns: [x]\n"
        "categorical_columns: []\n"
        "numerical_columns: []\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid dataset spec"):
        DatasetRegistry(specs_dir=tmp_path, project_root=tmp_path).list()

    registry = DatasetRegistry(project_root=Path.cwd())
    with pytest.raises(FileNotFoundError, match="does not download KEEL"):
        load_dataset(registry.get("page-blocks0"), registry)


def test_split_is_stratified_covering_and_fingerprint_stable() -> None:
    registry = DatasetRegistry(project_root=Path.cwd())
    dataset = load_dataset(registry.get("dev-small"), registry)
    first = make_split(dataset, 123)
    second = make_split(dataset, 123)
    assert first.to_dict() == second.to_dict()
    assert set(first.train_indices).isdisjoint(first.test_indices)
    assert set(first.train_indices) | set(first.test_indices) == set(range(len(dataset.frame)))
    for label in dataset.frame["label"].unique():
        train_count = int((dataset.frame.loc[list(first.train_indices), "label"] == label).sum())
        test_count = int((dataset.frame.loc[list(first.test_indices), "label"] == label).sum())
        assert train_count > 0 and test_count > 0


def test_profile_uses_train_only_numeric_and_categorical_values_and_refs_switch() -> None:
    registry = DatasetRegistry(project_root=Path.cwd())
    dataset = load_dataset(registry.get("dev-small"), registry)
    split = make_split(dataset, 42)
    test_index = split.test_indices[0]
    dataset.frame.loc[test_index, "color"] = "TEST_ONLY_CATEGORY"
    dataset.frame.loc[test_index, "age"] = 999999
    profile = build_profile(dataset, split, reference_example_count=3, seed=42)
    assert "TEST_ONLY_CATEGORY" not in profile.domains["color"]
    assert profile.numeric_summary["age"]["max"] < 999999
    assert set(profile.reference_indices).issubset(split.train_indices)
    assert profile.reference_enabled is True
    disabled = build_profile(dataset, split, reference_example_count=3, seed=42, enabled=False)
    assert disabled.reference_indices == ()
    assert disabled.reference_examples == ()


def test_generation_prompt_is_versioned_and_contains_concrete_class_without_test_sentinel() -> None:
    prompt = load_prompt("generation", "v1", Path.cwd())
    rendered = prompt.render(
        profile_json='{"domains": {"color": ["red"]}}',
        class_condition="yes",
        requested_count=2,
        reference_examples="[]",
    )
    assert prompt.sha256
    assert prompt.version == "generation-v1"
    assert "CLASS CONDITION: yes" in rendered
    assert "TEST_ONLY_CATEGORY" not in rendered
