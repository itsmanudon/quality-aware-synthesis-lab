"""Rebound copies cannot invent attempts, call roles or metadata identities."""

import json
import shutil
from pathlib import Path

import pytest
from test_phase1_final_readers import edit, refreshed_bindings, reseal

from rcqasyn.config import load_experiment_config
from rcqasyn.experiments import run_experiment
from rcqasyn.experiments.readers import read_bundle


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    return run_experiment(
        config.model_copy(
            update={
                "artifact_root": tmp_path_factory.mktemp("durable-authority"),
                "run_id": None,
            }
        ),
        replay=True,
    ).artifact_dir


@pytest.fixture
def bundle(source, tmp_path):
    return Path(shutil.copytree(source, tmp_path / source.name))


def reject(bundle):
    refreshed_bindings(bundle, metrics=True)
    reseal(bundle)
    with pytest.raises(ValueError, match="accounting|identity|purpose|required|call|role"):
        read_bundle(bundle)


@pytest.mark.parametrize("delta", [-1, 17])
def test_self_consistent_generation_counts_require_actual_durable_attempts(bundle, delta):
    def forge(record):
        for field in (
            "generation_attempted_calls",
            "generation_successful_calls",
            "generation_calls",
        ):
            record[field] += delta
        record["provider_calls"] += delta

    edit(bundle, "comparison.json", forge)
    edit(
        bundle,
        "manifest.json",
        lambda record: record.update(provider_call_count=record["provider_call_count"] + delta),
    )
    reject(bundle)


@pytest.mark.parametrize("purpose,role", [("generation", "judge"), ("judge", "generation")])
def test_request_role_provider_cannot_disagree_with_durable_purpose(bundle, purpose, role):
    spec = json.loads((bundle / "scientific_specification.json").read_text())["specification"]
    call_path = next(
        p
        for p in sorted((bundle / "calls").glob("*.json"))
        if json.loads(p.read_text())["purpose"] == purpose
    )
    edit(
        bundle,
        call_path.relative_to(bundle),
        lambda call: call.update(
            request={**call["request"], "role": role},
            provider_identity=spec["providers"]["judge" if role == "judge" else "generator"],
        ),
    )
    reject(bundle)


@pytest.mark.parametrize(
    "field",
    [
        "execution_id",
        "run_id",
        "dataset_id",
        "dataset_fingerprint",
        "split_fingerprint",
        "specification_fingerprint",
        "scientific_fingerprint",
        "science_fingerprint",
        "control_id",
        "baseline_id",
        "control_fingerprint",
    ],
)
def test_comparison_metadata_explicit_identity_is_source_bound(bundle, field):
    edit(bundle, "comparison.json", lambda record: record["metadata"].update({field: "foreign"}))
    reject(bundle)


def test_repeated_external_provider_ids_and_valid_roles_remain_readable(source):
    assert read_bundle(source)["generation_attempted_calls"] == 2


@pytest.mark.parametrize("case", [
    "empty", "duplicate", "missing_smoke", "missing_smoke_count", "forged_smoke",
])
def test_comparison_requires_each_baseline_row_and_its_source_smoke_count(bundle, case):
    def mutate(record):
        rows = record["baseline_comparison"]
        if case == "empty":
            rows.clear()
        elif case == "duplicate":
            rows.append(rows[0].copy())
        elif case == "missing_smoke":
            rows[0].pop("smoke")
        elif case == "missing_smoke_count":
            rows[0]["smoke"].pop("call_count")
        else:
            rows[0]["smoke"]["call_count"] = 999

    edit(bundle, "comparison.json", mutate)
    reject(bundle)
