"""Resealed byte-valid bundles still require coherent semantic identities."""

import hashlib
import json
from pathlib import Path

import pytest

from rcqasyn.config import load_experiment_config
from rcqasyn.experiments import run_experiment
from rcqasyn.experiments.readers import read_bundle


def reseal(directory):
    seal_path = directory / "FINALIZED.json"
    seal = json.loads(seal_path.read_text())
    seal["files"] = {
        p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in directory.rglob("*")
        if p.is_file() and p != seal_path
    }
    seal_path.write_text(json.dumps(seal), encoding="utf-8")


def change(directory, relative, key, value):
    path = directory / relative
    record = json.loads(path.read_text())
    if value is None:
        record.pop(key, None)
    else:
        record[key] = value
    path.write_text(json.dumps(record), encoding="utf-8")
    reseal(directory)


@pytest.fixture
def run_directory(tmp_path):
    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    return run_experiment(
        config.model_copy(update={"artifact_root": tmp_path, "run_id": None}), replay=True
    ).artifact_dir


@pytest.mark.parametrize(
    "artifact,key,value",
    [
        ("comparison.json", "dataset_id", "foreign"),
        ("manifest.json", "dataset_id", "foreign"),
        ("comparison.json", "execution_id", "foreign"),
        ("comparison.json", "specification_fingerprint", "foreign"),
        ("comparison.json", "split_fingerprint", "foreign"),
        ("manifest.json", "split_fingerprint", "foreign"),
        ("comparison.json", "dataset_fingerprint", "foreign"),
        ("comparison.json", "execution_id", None),
        ("manifest.json", "dataset_id", None),
        ("manifest.json", "split_fingerprint", None),
    ],
)
def test_resealed_identity_contradiction_rejected(run_directory, artifact, key, value):
    change(run_directory, artifact, key, value)
    with pytest.raises(ValueError, match="identity|required"):
        read_bundle(run_directory)


@pytest.mark.parametrize("version", [None, "future-seal-v99", ""])
def test_unknown_seal_schema_rejected(run_directory, version):
    path = run_directory / "FINALIZED.json"
    seal = json.loads(path.read_text())
    if version is None:
        seal.pop("schema_version")
    else:
        seal["schema_version"] = version
    path.write_text(json.dumps(seal), encoding="utf-8")
    with pytest.raises(ValueError, match="seal.*schema|schema.*seal"):
        read_bundle(run_directory)


def test_resealed_split_content_cannot_keep_stale_identity(run_directory):
    path = run_directory / "dataset/split_manifest.json"
    split = json.loads(path.read_text())
    split["split_seed"] += 1
    path.write_text(json.dumps(split), encoding="utf-8")
    reseal(run_directory)
    with pytest.raises(ValueError, match="split.*identity|identity.*split"):
        read_bundle(run_directory)


def test_resealed_configured_family_cannot_hide_required_columns(run_directory):
    path = run_directory / "comparison.json"
    comparison = json.loads(path.read_text())
    comparison["configured_results"]["numeric_columns"] = []
    for baseline in comparison["baselines"].values():
        baseline["intrinsic"]["numeric"] = {}
        baseline["intrinsic"]["diversity"]["numeric_variance_ratio"] = {}
        for row in baseline["intrinsic"]["class_conditional"]["classes"].values():
            row["numeric"] = {}
    # The result's own expected-family declaration is insufficient source binding.
    path.write_text(json.dumps(comparison), encoding="utf-8")
    reseal(run_directory)
    with pytest.raises(ValueError, match="configured.*identity|identity.*configured"):
        read_bundle(run_directory)


def test_resealed_baseline_metric_copy_cannot_contradict_comparison(run_directory):
    path = run_directory / "baselines/b1/metrics.json"
    metric = json.loads(path.read_text())
    metric["numeric"]["age"]["ks"] = 0.99
    path.write_text(json.dumps(metric), encoding="utf-8")
    reseal(run_directory)
    with pytest.raises(ValueError, match="result.*identity|identity.*result"):
        read_bundle(run_directory)
