"""Recorded split validation rejects resealed but scientifically wrong partitions."""

import hashlib
import importlib
import json
import shutil
from pathlib import Path

import pytest

from rcqasyn.config import load_experiment_config
from rcqasyn.experiments import run_experiment
from rcqasyn.experiments.readers import read_bundle


def digest(value, *, compact=False):
    options = {"sort_keys": True}
    if compact:
        options.update(separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(json.dumps(value, **options).encode()).hexdigest()


def refresh_split(split, profile):
    split["split_fingerprint"] = digest(
        {key: value for key, value in split.items() if key != "split_fingerprint"}
    )
    profile["split_fingerprint"] = split["split_fingerprint"]
    profile["train_indices"] = list(split["train_indices"])
    profile["train_row_count"] = len(split["train_indices"])


@pytest.fixture
def records():
    population = {
        "columns": ["value", "label"],
        "index": list(range(7)),
        "data": [[0, "a"], [1, "a"], [2, "a"], [3, "a"], [4, "b"], [5, "b"], [6, "singleton"]],
    }
    specification = {
        "dataset": {
            "definition": {
                "dataset_id": "fixture",
                "feature_columns": ["value"],
                "target_column": "label",
                "split": {"test_size": 0.5, "seed_offset": 3, "stratify": True},
            },
            "normalized_fingerprint": "d" * 64,
        },
        "dataset_run": {"dataset_id": "fixture", "root_seed": 42},
        "split_protocol": "stratified_hash_order_v1",
        "split_seed": 3943249802026279297,
    }
    split = {
        "dataset_id": "fixture",
        "dataset_fingerprint": "d" * 64,
        "root_seed": 42,
        "split_seed": 3943249802026279297,
        "train_indices": [2, 3, 5, 6],
        "test_indices": [0, 1, 4],
        "train_fingerprint": "96e27f783fe6773bc358bbcaefc4eec666c3afc72b8396aee4fbc48039f2d682",
        "test_fingerprint": "2a94e64a7080e66438a811d004cae36f239187615bfe3ffd45c4df8a3dd1b4e5",
    }
    profile = {
        "dataset_id": "fixture",
        "dataset_fingerprint": "d" * 64,
        "class_counts": {"a": 2, "b": 1, "singleton": 1},
        "class_proportions": {"a": 0.5, "b": 0.25, "singleton": 0.25},
        "domains": {"label": ["a", "b", "singleton"]},
    }
    refresh_split(split, profile)
    return specification, split, profile, population


def validate(records):
    # Import inside each test so the missing implementation produces test failures.
    module = importlib.import_module("rcqasyn.experiments.recorded_split")
    module.validate_recorded_split(*records)


def test_approved_split_with_singleton_train_support_is_accepted(records):
    validate(records)


@pytest.mark.parametrize(
    "train,test",
    [
        ([2, 2, 3, 5, 6], [0, 1, 4]),
        ([2, 3, 5, 6], [0, 1, 4, 4]),
        ([2, 3, 5, 6], [0, 1, 2, 4]),
        ([2, 3, 5], [0, 1, 4]),
        ([2, 3, 5, 6, 7], [0, 1, 4]),
        ([], list(range(7))),
        (list(range(7)), []),
        ([2.0, 3, 5, 6], [0, 1, 4]),
        ([2, 3, 5, 6], [False, 1, 4]),
        (["2", 3, 5, 6], [0, 1, 4]),
        ([2, 3, 5, 6], [-1, 1, 4]),
    ],
)
def test_refreshed_hash_cannot_approve_invalid_partition(records, train, test):
    _, split, profile, _ = records
    split.update(train_indices=train, test_indices=test)
    refresh_split(split, profile)
    with pytest.raises(ValueError, match="split|partition|indices"):
        validate(records)


@pytest.mark.parametrize("seed", [0, 43, True, 42.0, "42"])
def test_split_root_seed_requires_exact_configured_integer(records, seed):
    _, split, profile, _ = records
    split["root_seed"] = seed
    refresh_split(split, profile)
    with pytest.raises(ValueError, match="seed"):
        validate(records)


def test_matching_forged_split_seed_is_not_derived_seed(records):
    specification, split, profile, _ = records
    specification["split_seed"] += 1
    split["split_seed"] += 1
    refresh_split(split, profile)
    with pytest.raises(ValueError, match="seed"):
        validate(records)


def test_same_class_membership_swap_is_rejected_after_all_split_hashes_refresh(records):
    _, split, profile, _ = records
    split["train_indices"] = [0, 3, 5, 6]
    split["test_indices"] = [1, 2, 4]
    refresh_split(split, profile)
    with pytest.raises(ValueError, match="membership|partition"):
        validate(records)


def test_singleton_cannot_move_to_test_after_hash_refresh(records):
    _, split, profile, _ = records
    split["train_indices"] = [2, 3, 5]
    split["test_indices"] = [0, 1, 4, 6]
    profile["class_counts"] = {"a": 2, "b": 1}
    refresh_split(split, profile)
    with pytest.raises(ValueError, match="membership|partition|support"):
        validate(records)


@pytest.mark.parametrize("field", ["train_fingerprint", "test_fingerprint", "split_fingerprint"])
@pytest.mark.parametrize("value", [None, "", "wrong"])
def test_required_split_fingerprint_is_well_formed(records, field, value):
    _, split, profile, _ = records
    split[field] = value
    if field != "split_fingerprint":
        refresh_split(split, profile)
    with pytest.raises(ValueError, match="fingerprint|identity"):
        validate(records)


@pytest.mark.parametrize("count", [3, True, 4.0])
def test_profile_train_count_cannot_disagree_with_indices(records, count):
    records[2]["train_row_count"] = count
    with pytest.raises(ValueError, match="count"):
        validate(records)


@pytest.mark.parametrize("field,count", [
    ("train_row_count", 999), ("test_row_count", 999), ("row_count", 999),
    ("train_count", True), ("test_count", 3.0),
])
def test_explicit_split_size_metadata_requires_partition_counts(records, field, count):
    records[1][field] = count
    refresh_split(records[1], records[2])
    with pytest.raises(ValueError, match="count|integer|identity"):
        validate(records)


def test_profile_class_counts_require_approved_partition_counts(records):
    records[2]["class_counts"] = {"a": 1, "b": 2, "singleton": 1}
    with pytest.raises(ValueError, match="class.*count|count"):
        validate(records)


def test_profile_class_support_requires_singleton_class(records):
    records[2]["class_counts"] = {"a": 2, "b": 2}
    with pytest.raises(ValueError, match="class.*count|support"):
        validate(records)


@pytest.mark.parametrize("record_index", [1, 2])
@pytest.mark.parametrize("field", ["dataset_id", "dataset_fingerprint"])
def test_local_records_must_bind_same_dataset_source(records, record_index, field):
    records[record_index][field] = "foreign"
    with pytest.raises(ValueError, match="identity|dataset|source"):
        validate(records)


@pytest.mark.parametrize("indices", [[0, 1, 2, 3, 4, 5], [0, 1, 2, 3, 4, 5, 7], [0, 1, 2, 3, 4, 5, 5]])
def test_evaluation_population_requires_exact_unique_integer_row_identities(records, indices):
    records[3]["index"] = indices
    with pytest.raises(ValueError, match="population|partition|indices"):
        validate(records)


def test_profile_class_count_boolean_is_not_integer(records):
    records[2]["class_counts"]["b"] = True
    with pytest.raises(ValueError, match="count"):
        validate(records)


@pytest.mark.parametrize("field", ["root_seed", "split_seed"])
def test_scientific_seed_boolean_is_not_integer(records, field):
    if field == "root_seed":
        records[0]["dataset_run"][field] = True
    else:
        records[0][field] = True
    with pytest.raises(ValueError, match="seed"):
        validate(records)


@pytest.mark.parametrize("protocol", ["other", None])
def test_unsupported_split_protocol_rejected(records, protocol):
    records[0]["split_protocol"] = protocol
    with pytest.raises(ValueError, match="protocol"):
        validate(records)


@pytest.mark.parametrize("fraction", [0, 1, True, "0.5"])
def test_split_test_fraction_must_be_valid_number(records, fraction):
    records[0]["dataset"]["definition"]["split"]["test_size"] = fraction
    with pytest.raises(ValueError, match="split|fraction"):
        validate(records)


def test_profile_partition_identity_must_equal_recorded_train(records):
    records[2]["train_indices"] = [0, 1, 5, 6]
    with pytest.raises(ValueError, match="TRAIN|partition"):
        validate(records)


def test_profile_split_fingerprint_must_equal_recorded_split(records):
    records[2]["split_fingerprint"] = "f" * 64
    with pytest.raises(ValueError, match="fingerprint|identity"):
        validate(records)


@pytest.mark.parametrize("field", ["train_fingerprint", "test_fingerprint"])
def test_refreshed_split_hash_does_not_approve_wrong_subset_fingerprint(records, field):
    _, split, profile, _ = records
    split[field] = "f" * 64
    refresh_split(split, profile)
    with pytest.raises(ValueError, match="fingerprint"):
        validate(records)


@pytest.fixture(scope="module")
def reader_source(tmp_path_factory):
    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    return run_experiment(
        config.model_copy(update={"artifact_root": tmp_path_factory.mktemp("v-split"), "run_id": None}),
        replay=True,
    ).artifact_dir


@pytest.fixture
def reader_bundle(reader_source, tmp_path):
    return Path(shutil.copytree(reader_source, tmp_path / reader_source.name))


def load_record(bundle, relative):
    return json.loads((bundle / relative).read_text(encoding="utf-8"))


def save_record(bundle, relative, value):
    (bundle / relative).write_text(json.dumps(value), encoding="utf-8")


def replace_identities(bundle, replacements):
    def replace(value):
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        if isinstance(value, list):
            return [replace(item) for item in value]
        return replacements.get(value, value) if isinstance(value, str) else value

    for path in bundle.rglob("*"):
        if path.suffix == ".json" and path.name != "evaluation_population.json":
            save_record(bundle, path.relative_to(bundle), replace(json.loads(path.read_text())))
        elif path.suffix == ".jsonl":
            rows = [replace(json.loads(line)) for line in path.read_text().splitlines() if line.strip()]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def refresh_reader_bindings(bundle):
    from rcqasyn.datasets.profile import DatasetProfile

    plan = load_record(bundle, "generation_plan.json")
    profile = DatasetProfile.model_validate_json(
        (bundle / "dataset/profile_source.json").read_text(encoding="utf-8")
    )
    profile_hash = hashlib.sha256(profile.model_dump_json().encode()).hexdigest()
    replace_identities(bundle, {plan["source_profile_hash"]: profile_hash})
    binding = load_record(bundle, "execution_binding.json")
    for relative in binding["source_files"]:
        binding["source_files"][relative] = hashlib.sha256((bundle / relative).read_bytes()).hexdigest()
    save_record(bundle, "execution_binding.json", binding)
    for relative in ("manifest.json", "comparison.json"):
        record = load_record(bundle, relative)
        record["execution_binding_fingerprint"] = digest(binding, compact=True)
        save_record(bundle, relative, record)
    comparison = load_record(bundle, "comparison.json")
    for name in ("b1", "b2", "b3"):
        relative = f"baselines/{name}/result_binding.json"
        binding = load_record(bundle, relative)
        for section in ("source_files", "result_files"):
            for file in binding[section]:
                binding[section][file] = hashlib.sha256(
                    (bundle / "baselines" / name / file).read_bytes()
                ).hexdigest()
        rows = [
            json.loads(line)
            for line in (bundle / "baselines" / name / "candidates.jsonl").read_text().splitlines()
            if line.strip()
        ]
        binding["accepted_population_fingerprint"] = digest(rows, compact=True)
        save_record(bundle, relative, binding)
        comparison["result_binding_fingerprints"][name] = digest(binding, compact=True)
    save_record(bundle, "comparison.json", comparison)
    seal = load_record(bundle, "FINALIZED.json")
    seal["files"] = {
        path.relative_to(bundle).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in bundle.rglob("*")
        if path.is_file() and path.name != "FINALIZED.json"
    }
    save_record(bundle, "FINALIZED.json", seal)


def refresh_reader_split(bundle, split):
    old = load_record(bundle, "dataset/split_manifest.json")["split_fingerprint"]
    split["split_fingerprint"] = digest(
        {key: value for key, value in split.items() if key != "split_fingerprint"}
    )
    save_record(bundle, "dataset/split_manifest.json", split)
    for relative in ("dataset/profile.json", "dataset/profile_source.json"):
        profile = load_record(bundle, relative)
        profile["train_indices"] = split["train_indices"]
        profile["train_row_count"] = len(split["train_indices"])
        save_record(bundle, relative, profile)
    replace_identities(bundle, {old: split["split_fingerprint"]})


def test_public_reader_accepts_untouched_local_snapshot(reader_source):
    comparison = load_record(reader_source, "comparison.json")
    assert read_bundle(reader_source) == comparison


def test_public_reader_rejects_same_class_membership_after_rebinding(reader_bundle, monkeypatch):
    split = load_record(reader_bundle, "dataset/split_manifest.json")
    population = load_record(reader_bundle, "dataset/evaluation_population.json")
    target_index = population["columns"].index("label")
    labels = {index: row[target_index] for index, row in zip(population["index"], population["data"])}
    train_index, test_index = next(
        (train, test)
        for train in split["train_indices"]
        for test in split["test_indices"]
        if labels[train] == labels[test]
    )
    split["train_indices"] = sorted(
        test_index if index == train_index else index for index in split["train_indices"]
    )
    split["test_indices"] = sorted(
        train_index if index == test_index else index for index in split["test_indices"]
    )
    # Refresh even the data-subset fingerprints, so only approved membership exposes the forgery.
    import pandas as pd

    frame = pd.DataFrame(population["data"], columns=population["columns"], index=population["index"], dtype=object)
    for name in ("train", "test"):
        split[f"{name}_fingerprint"] = hashlib.sha256(
            frame.loc[split[f"{name}_indices"]].to_json(
                orient="split", date_format="iso", default_handler=str
            ).encode()
        ).hexdigest()
    refresh_reader_split(reader_bundle, split)
    refresh_reader_bindings(reader_bundle)
    with monkeypatch.context() as old_reader:
        old_reader.setattr("rcqasyn.experiments.recorded_split.validate_recorded_split", lambda *args: None)
        assert read_bundle(reader_bundle)["dataset_id"] == "dev-small"
    with pytest.raises(ValueError, match="approved.*membership"):
        read_bundle(reader_bundle)


def test_public_reader_rejects_derived_seed_forgery_after_rebinding(reader_bundle, monkeypatch):
    split = load_record(reader_bundle, "dataset/split_manifest.json")
    split["split_seed"] += 1
    refresh_reader_split(reader_bundle, split)
    scientific = load_record(reader_bundle, "scientific_specification.json")
    old = scientific["fingerprint"]
    scientific["specification"]["split_seed"] = split["split_seed"]
    scientific["fingerprint"] = digest(scientific["specification"], compact=True)
    save_record(reader_bundle, "scientific_specification.json", scientific)
    replace_identities(reader_bundle, {old: scientific["fingerprint"]})
    manifest = load_record(reader_bundle, "manifest.json")
    manifest["seed_provenance"]["split_seed"] = split["split_seed"]
    save_record(reader_bundle, "manifest.json", manifest)
    refresh_reader_bindings(reader_bundle)
    with monkeypatch.context() as old_reader:
        old_reader.setattr("rcqasyn.experiments.recorded_split.validate_recorded_split", lambda *args: None)
        assert read_bundle(reader_bundle)["dataset_id"] == "dev-small"
    with pytest.raises(ValueError, match="derived seed"):
        read_bundle(reader_bundle)


def test_public_reader_cannot_refresh_packaging_to_change_normalized_population(reader_bundle):
    population = load_record(reader_bundle, "dataset/evaluation_population.json")
    population["data"][0][0] = 999
    save_record(reader_bundle, "dataset/evaluation_population.json", population)
    refresh_reader_bindings(reader_bundle)
    with pytest.raises(ValueError, match="normalized population source"):
        read_bundle(reader_bundle)
