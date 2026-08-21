"""Configuration-driven local tabular dataset registry and profiling."""

from .acquisition import (
    AcquisitionRecord,
    assert_no_test_leakage,
    build_dataset_report,
    inspect_dataset_schema,
    reconcile_schema,
    record_acquisition,
    sha256_file,
    write_acquisition,
)
from .loader import KeelAttribute, KeelSchema, LoadedDataset, inspect_keel, load_dataset
from .profile import DatasetProfile, build_profile
from .registry import DatasetDefinition, DatasetRegistry
from .split import SplitManifest, make_split

__all__ = [
    "AcquisitionRecord",
    "DatasetDefinition",
    "DatasetProfile",
    "DatasetRegistry",
    "KeelAttribute",
    "KeelSchema",
    "LoadedDataset",
    "SplitManifest",
    "assert_no_test_leakage",
    "build_dataset_report",
    "build_profile",
    "inspect_dataset_schema",
    "inspect_keel",
    "load_dataset",
    "make_split",
    "reconcile_schema",
    "record_acquisition",
    "sha256_file",
    "write_acquisition",
]
