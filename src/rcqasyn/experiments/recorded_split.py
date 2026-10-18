"""Read-only validation of the recorded stratified split and local population.

The caller must bind the original population JSON bytes to the normalized
dataset fingerprint before calling this helper. Population values remain local
evaluation provenance and must never enter TRAIN profiles or provider contexts.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, cast

import pandas as pd

from rcqasyn.utils.seeds import derive_seed


def _integer(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"split {label} must be a non-negative integer")
    return value


def _same(expected: Any, actual: Any, label: str) -> None:
    if expected != actual:
        raise ValueError(f"split {label} identity mismatch")


def _indices(value: Any, label: str, *, nonempty: bool = True) -> list[int]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(f"split {label} indices must be a non-empty array")
    for index in value:
        _integer(index, f"{label} index")
    if len(value) != len(set(value)):
        raise ValueError(f"split {label} indices contain duplicates")
    return value


def _fingerprint(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"split {label} fingerprint is missing or invalid")
    return value


def validate_recorded_split(
    specification: dict[str, Any],
    split: dict[str, Any],
    profile: dict[str, Any],
    population: dict[str, Any],
) -> None:
    """Check approved membership without rereading a mutable dataset source.

    The population is the parsed, hash-bound pandas ``orient='split'`` snapshot.
    This function checks recorded protocol semantics; it does not call the split
    writer, generate a replacement partition, or recompute evaluation metrics.
    """
    try:
        _validate(specification, split, profile, population)
    except (KeyError, TypeError, AttributeError, IndexError) as error:
        raise ValueError("required split population or protocol metadata is invalid") from error


def _validate(
    specification: dict[str, Any],
    split: dict[str, Any],
    profile: dict[str, Any],
    population: dict[str, Any],
) -> None:
    definition = specification["dataset"]["definition"]
    dataset_id = definition["dataset_id"]
    source = specification["dataset"]["normalized_fingerprint"]
    _same(dataset_id, specification["dataset_run"]["dataset_id"], "configured dataset")
    for name, record in (("manifest", split), ("profile", profile)):
        _same(dataset_id, record["dataset_id"], f"{name} dataset")
        _same(source, record["dataset_fingerprint"], f"{name} dataset/source")
    _same("stratified_hash_order_v1", specification["split_protocol"], "protocol")
    policy = definition["split"]
    if policy["stratify"] is not True:
        raise ValueError("split protocol requires stratify=true")
    fraction = policy["test_size"]
    if (
        type(fraction) not in (int, float)
        or not math.isfinite(fraction)
        or not 0 < fraction < 1
    ):
        raise ValueError("split test fraction must be a finite number between zero and one")
    root_seed = _integer(specification["dataset_run"]["root_seed"], "configured root seed")
    offset = _integer(policy["seed_offset"], "seed offset")
    expected_seed = derive_seed(root_seed, f"dataset-split:{dataset_id}", offset)
    _same(root_seed, _integer(split["root_seed"], "root seed"), "root seed")
    _same(expected_seed, _integer(split["split_seed"], "seed"), "derived seed")
    _same(expected_seed, _integer(specification["split_seed"], "scientific seed"), "scientific seed")

    columns = population["columns"]
    expected_columns = [*definition["feature_columns"], definition["target_column"]]
    _same(expected_columns, columns, "evaluation population columns")
    if not isinstance(columns, list) or len(columns) != len(set(columns)):
        raise ValueError("split evaluation population columns must be unique")
    indices = _indices(population["index"], "evaluation population")
    data = population["data"]
    if not isinstance(data, list) or len(data) != len(indices):
        raise ValueError("split evaluation population shape does not match row indices")
    if any(not isinstance(row, list) or len(row) != len(columns) for row in data):
        raise ValueError("split evaluation population shape does not match columns")
    # Preserve JSON numeric primitives independently of inferred column dtypes.
    # The axes were shape-checked above; cast only bridges current pandas stub signatures.
    frame = pd.DataFrame(data, columns=cast(Any, columns), index=cast(Any, indices), dtype=object)
    train = _indices(split["train_indices"], "TRAIN")
    test = _indices(split["test_indices"], "TEST")
    if set(train) & set(test) or set(train) | set(test) != set(indices):
        raise ValueError("split partition overlaps or does not cover evaluation population")
    for record in (split, profile, population):
        for key, count in {
            "train_row_count": len(train), "test_row_count": len(test),
            "train_count": len(train), "test_count": len(test), "row_count": len(indices),
        }.items():
            if key in record:
                _same(count, _integer(record[key], key), f"recorded {key}")

    target = cast(pd.Series, frame[definition["target_column"]]).astype("string").fillna("<MISSING>")
    approved_train: list[int] = []
    approved_test: list[int] = []
    class_counts: dict[str, int] = {}
    for label in sorted(target.unique().tolist()):
        group = [index for index, value in zip(indices, target.tolist()) if value == label]
        group.sort(
            key=lambda index: hashlib.sha256(f"{expected_seed}:{label}:{index}".encode()).hexdigest()
        )
        count = max(1, round(len(group) * fraction)) if len(group) > 1 else 0
        if count >= len(group):
            count = len(group) - 1
        approved_test.extend(group[:count])
        approved_train.extend(group[count:])
        class_counts[str(label)] = len(group) - count
    _same(sorted(approved_train), train, "approved TRAIN membership partition")
    _same(sorted(approved_test), test, "approved TEST membership partition")

    for name, partition in (("train", train), ("test", test)):
        expected = hashlib.sha256(
            frame.loc[partition].to_json(
                orient="split", date_format="iso", default_handler=str
            ).encode()
        ).hexdigest()
        _same(expected, _fingerprint(split[f"{name}_fingerprint"], name), f"{name} fingerprint")
    split_hash = hashlib.sha256(
        json.dumps(
            {key: value for key, value in split.items() if key != "split_fingerprint"},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    _same(split_hash, _fingerprint(split["split_fingerprint"], "manifest"), "fingerprint")
    _same(split_hash, profile["split_fingerprint"], "profile fingerprint")
    _same(train, _indices(profile["train_indices"], "profile TRAIN"), "profile TRAIN partition")
    _same(len(train), _integer(profile["train_row_count"], "profile TRAIN count"), "TRAIN count")
    recorded_counts = profile["class_counts"]
    if not isinstance(recorded_counts, dict):
        raise TypeError("split profile class counts must be an object")
    for count in recorded_counts.values():
        _integer(count, "profile class count")
    _same(class_counts, recorded_counts, "profile class counts/support")
