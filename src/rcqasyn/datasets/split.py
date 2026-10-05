# pyright: reportArgumentType=false, reportAttributeAccessIssue=false
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import pandas as pd

from rcqasyn.utils.seeds import derive_seed

from .loader import LoadedDataset


@dataclass(frozen=True)
class SplitManifest:
    dataset_id: str
    dataset_fingerprint: str
    root_seed: int
    split_seed: int
    train_indices: tuple[int, ...]
    test_indices: tuple[int, ...]
    train_fingerprint: str
    test_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        base = self.to_dict_without_self()
        base["split_fingerprint"] = hashlib.sha256(json.dumps(base, sort_keys=True).encode()).hexdigest()
        return base

    def to_dict_without_self(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "dataset_fingerprint": self.dataset_fingerprint,
            "root_seed": self.root_seed,
            "split_seed": self.split_seed,
            "train_indices": list(self.train_indices),
            "test_indices": list(self.test_indices),
            "train_fingerprint": self.train_fingerprint,
            "test_fingerprint": self.test_fingerprint,
        }


def make_split(dataset: LoadedDataset, root_seed: int) -> SplitManifest:
    if not dataset.spec.split.stratify:
        raise ValueError("M1 supports stratify=true only")
    frame = dataset.frame
    labels = frame[dataset.spec.target_column].astype("string").fillna("<MISSING>")
    split_seed = derive_seed(root_seed, f"dataset-split:{dataset.spec.dataset_id}", dataset.spec.split.seed_offset)
    train: list[int] = []
    test: list[int] = []
    test_fraction = dataset.spec.split.test_size
    for label in sorted(labels.unique().tolist()):
        group = [int(i) for i in labels.index[labels == label].tolist()]
        group.sort(key=lambda i: hashlib.sha256(f"{split_seed}:{label}:{i}".encode()).hexdigest())
        n_test = max(1, round(len(group) * test_fraction)) if len(group) > 1 else 0
        if n_test >= len(group):
            n_test = len(group) - 1
        test.extend(group[:n_test])
        train.extend(group[n_test:])
    train = sorted(train)
    test = sorted(test)
    if not train or not test:
        raise ValueError("stratified split needs at least one train and one test row")
    if set(train) & set(test) or len(set(train) | set(test)) != len(frame):
        raise AssertionError("split indices overlap or do not cover dataset")
    return SplitManifest(
        dataset_id=dataset.spec.dataset_id,
        dataset_fingerprint=dataset.fingerprint,
        root_seed=root_seed,
        split_seed=split_seed,
        train_indices=tuple(train),
        test_indices=tuple(test),
        train_fingerprint=_subset_fingerprint(frame, train),
        test_fingerprint=_subset_fingerprint(frame, test),
    )


def _subset_fingerprint(frame: pd.DataFrame, indices: list[int]) -> str:
    payload = frame.loc[indices].to_json(orient="split", date_format="iso", default_handler=str).encode()
    return hashlib.sha256(payload).hexdigest()



def validate_partition(dataset: LoadedDataset, split: SplitManifest) -> None:
    """Validate row identities without consulting held-out values or labels."""
    if split.dataset_id != dataset.spec.dataset_id:
        raise ValueError("partition dataset identity does not match")
    train, test = split.train_indices, split.test_indices
    population = tuple(dataset.frame.index)
    if len(set(population)) != len(population):
        raise ValueError("dataset row identity is not unique")
    if not train or not test or len(set(train)) != len(train) or len(set(test)) != len(test):
        raise ValueError("partition is empty or contains duplicate identities")
    if set(train) & set(test) or set(train) | set(test) != set(population):
        raise ValueError("partition overlaps or does not cover dataset identities")

    if split.dataset_fingerprint != dataset.fingerprint:
        raise ValueError("partition dataset fingerprint does not match")
    if split.train_fingerprint != _subset_fingerprint(dataset.frame, list(train)):
        raise ValueError("partition TRAIN fingerprint does not match")
