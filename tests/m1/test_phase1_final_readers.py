"""Resealing cannot make detached results or populations authoritative."""

import hashlib
import json
import shutil
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


def edit(directory, relative, mutate, *, lines=False):
    path = directory / relative
    value = (
        [json.loads(s) for s in path.read_text().splitlines() if s.strip()]
        if lines
        else json.loads(path.read_text())
    )
    mutate(value)
    path.write_text(
        "\n".join(json.dumps(v) for v in value) + "\n" if lines else json.dumps(value),
        encoding="utf-8",
    )


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    return run_experiment(
        config.model_copy(
            update={"artifact_root": tmp_path_factory.mktemp("reader-source"), "run_id": None}
        ),
        replay=True,
    ).artifact_dir


@pytest.fixture
def bundle(source, tmp_path):
    return Path(shutil.copytree(source, tmp_path / source.name))


def refreshed_bindings(bundle, *, metrics=False):
    # Recompute packaging digests independently, leaving the scientific source authoritative.
    def digest(value):
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()

    root_path = bundle / "execution_binding.json"
    root = json.loads(root_path.read_text())
    for relative in root["source_files"]:
        root["source_files"][relative] = hashlib.sha256(
            (bundle / relative).read_bytes()
        ).hexdigest()
    root_path.write_text(json.dumps(root))
    for relative in ("manifest.json", "comparison.json"):
        edit(
            bundle,
            relative,
            lambda record: record.update(execution_binding_fingerprint=digest(root)),
        )
    for name in ("b1", "b2", "b3"):
        directory = bundle / "baselines" / name
        binding = json.loads((directory / "result_binding.json").read_text())
        for relative in binding["source_files"]:
            binding["source_files"][relative] = hashlib.sha256(
                (directory / relative).read_bytes()
            ).hexdigest()
        if metrics:
            for relative in binding["result_files"]:
                binding["result_files"][relative] = hashlib.sha256(
                    (directory / relative).read_bytes()
                ).hexdigest()
        if "accepted_population_fingerprint" in binding:
            binding["accepted_population_fingerprint"] = digest(
                [
                    json.loads(s)
                    for s in (directory / "candidates.jsonl").read_text().splitlines()
                    if s.strip()
                ]
            )
        (directory / "result_binding.json").write_text(json.dumps(binding))
        edit(
            bundle,
            "comparison.json",
            lambda record, name=name, binding=binding: record["result_binding_fingerprints"].update(
                {name: digest(binding)}
            ),
        )


def reject(bundle, *, rebind=True, metrics=False):
    if rebind:
        refreshed_bindings(bundle, metrics=metrics)
    reseal(bundle)
    with pytest.raises(
        ValueError,
        match="identity|required|binding|population|candidate|call|decision|result|accounting",
    ):
        read_bundle(bundle)


@pytest.mark.parametrize("baseline", ["b1", "b2", "b3"])
def test_accepted_population_must_be_exact_source_candidate(bundle, baseline):
    def foreign(rows):
        rows[0]["record_id"] = "foreign-item-0"
        rows[0]["metadata"]["provider_call_id"] = "foreign"

    edit(bundle, f"baselines/{baseline}/candidates.jsonl", foreign, lines=True)
    reject(bundle)


@pytest.mark.parametrize(
    "kind", ["missing", "foreign_execution", "wrong_role", "wrong_data", "wrong_item"]
)
def test_raw_candidate_requires_compatible_generation_call(bundle, kind):
    candidates = [json.loads(s) for s in (bundle / "candidates_raw.jsonl").read_text().splitlines()]
    call_id = candidates[0]["metadata"]["provider_call_id"]
    if kind == "missing":
        edit(
            bundle,
            "candidates_raw.jsonl",
            lambda rows: rows[0]["metadata"].update(provider_call_id="nonexistent"),
            lines=True,
        )
    elif kind == "foreign_execution":
        edit(bundle, f"calls/{call_id}.json", lambda call: call.update(execution_id="foreign"))
    elif kind == "wrong_role":
        edit(bundle, f"calls/{call_id}.json", lambda call: call["request"].update(role="judge"))
    elif kind == "wrong_data":
        edit(
            bundle, "candidates_raw.jsonl", lambda rows: rows[0]["data"].update(age=999), lines=True
        )
    else:
        edit(
            bundle,
            "candidates_raw.jsonl",
            lambda rows: rows[0]["metadata"].update(item_index=999),
            lines=True,
        )
    reject(bundle)


@pytest.mark.parametrize(
    "artifact,key,value",
    [
        ("manifest.json", "root_seed", 999),
        ("manifest.json", "generator_model", "foreign"),
        ("generation_plan.json", "requested_count", 999),
        ("generation_plan.json", "seed", 999),
        ("generation_plan.json", "source_profile_id", "foreign"),
        ("generation_plan.json", "class_quotas", [{"label": "1", "count": 999}]),
        ("generation_seed_plan.json", "base_provider_seed", 999),
    ],
)
def test_recorded_plan_and_seed_settings_bind_scientific_source(bundle, artifact, key, value):
    edit(bundle, artifact, lambda record: record.update({key: value}))
    reject(bundle)


@pytest.mark.parametrize(
    "key",
    [
        "dataset_id",
        "execution_id",
        "specification_fingerprint",
        "split_fingerprint",
        "control_fingerprint",
    ],
)
@pytest.mark.parametrize(
    "filename, family", [("metrics.json", "intrinsic"), ("classifier_metrics.json", "utility")]
)
def test_explicit_metric_identity_must_match_source_even_when_copies_agree(
    bundle, key, filename, family
):
    edit(bundle, f"baselines/b1/{filename}", lambda record: record.update({key: "foreign"}))
    edit(
        bundle,
        "comparison.json",
        lambda record: record["baselines"]["b1"][family].update({key: "foreign"}),
    )
    reject(bundle, metrics=True)


def test_matching_altered_metric_copies_require_original_result_binding(bundle):
    edit(
        bundle, "baselines/b1/metrics.json", lambda record: record["numeric"]["age"].update(ks=0.99)
    )
    edit(
        bundle,
        "comparison.json",
        lambda record: record["baselines"]["b1"]["intrinsic"]["numeric"]["age"].update(ks=0.99),
    )
    reject(bundle)


@pytest.mark.parametrize("mutation", ["count", "order", "missing_candidate", "foreign_decision"])
def test_comparison_population_agrees_with_decisions_and_exact_subset(bundle, mutation):
    if mutation == "count":
        edit(
            bundle, "comparison.json", lambda record: record["baselines"]["b1"].update(accepted=999)
        )
    elif mutation == "order":
        edit(
            bundle,
            "comparison.json",
            lambda record: record["baselines"]["b1"]["accepted_record_ids"].reverse(),
        )
    elif mutation == "missing_candidate":
        edit(bundle, "baselines/b1/candidates.jsonl", lambda rows: rows.pop(), lines=True)
    else:
        edit(
            bundle,
            "baselines/b1/decisions.jsonl",
            lambda rows: rows[0].update(candidate_id="foreign"),
            lines=True,
        )
    reject(bundle)


@pytest.mark.parametrize(
    "key", ["execution_id", "dataset_id", "control_fingerprint", "accepted_population_fingerprint"]
)
def test_new_results_require_binding_identity(bundle, key):
    path = bundle / "baselines/b1/result_binding.json"
    if not path.exists():
        pytest.fail("new-format result requires authoritative binding sidecar")
    edit(bundle, "baselines/b1/result_binding.json", lambda record: record.pop(key))
    reject(bundle)


def test_valid_new_bundle_preserves_direct_metrics_and_population(source):
    comparison = read_bundle(source)
    for name, baseline in comparison["baselines"].items():
        assert baseline["intrinsic"] == json.loads(
            (source / f"baselines/{name}/metrics.json").read_text()
        )
        assert baseline["utility"] == json.loads(
            (source / f"baselines/{name}/classifier_metrics.json").read_text()
        )
        rows = [
            json.loads(s)
            for s in (source / f"baselines/{name}/candidates.jsonl").read_text().splitlines()
        ]
        assert baseline["accepted_record_ids"] == [r["record_id"] for r in rows]
        assert baseline["accepted"] == len(rows)
        assert (source / f"baselines/{name}/result_binding.json").is_file()


@pytest.mark.parametrize(
    "field,value", [("seed", 999), ("prompt", "foreign prompt"), ("max_tokens", 999)]
)
def test_judge_request_binds_recorded_config_and_candidate(bundle, field, value):
    result = json.loads((bundle / "baselines/b3/judge_results.jsonl").read_text().splitlines()[0])
    call_id = result["judge_call_id"]
    edit(bundle, f"calls/{call_id}.json", lambda call: call["request"].update({field: value}))
    edit(
        bundle,
        "baselines/b3/provider_calls.jsonl",
        lambda rows: next(row for row in rows if row["call_id"] == call_id).update({field: value}),
        lines=True,
    )
    reject(bundle)


@pytest.mark.parametrize(
    "relative,key",
    [
        ("manifest.json", "artifact_binding_version"),
        ("comparison.json", "execution_binding_fingerprint"),
        ("baselines/b1/result_binding.json", "result_files"),
    ],
)
def test_new_format_cannot_drop_required_binding(bundle, relative, key):
    edit(bundle, relative, lambda record: record.pop(key))
    reject(bundle, rebind=False)


def test_rehashed_split_seed_is_bound_to_scientific_seed(bundle):
    def mutate(split):
        split["split_seed"] = 999
        split["split_fingerprint"] = hashlib.sha256(
            json.dumps(
                {k: v for k, v in split.items() if k != "split_fingerprint"}, sort_keys=True
            ).encode()
        ).hexdigest()

    edit(bundle, "dataset/split_manifest.json", mutate)
    split = json.loads((bundle / "dataset/split_manifest.json").read_text())
    for relative in ("manifest.json", "comparison.json"):
        edit(
            bundle,
            relative,
            lambda record: record.update(split_fingerprint=split["split_fingerprint"]),
        )
    edit(
        bundle,
        "comparison.json",
        lambda record: record["metadata"].update(split_fingerprint=split["split_fingerprint"]),
    )
    reject(bundle)


def test_wrong_generation_provider_model_is_bound_to_config(bundle):
    edit(
        bundle,
        "generation_plan.json",
        lambda record: record["generator_config"]["provider"].update(model="foreign"),
    )
    reject(bundle)


@pytest.mark.parametrize("key", ["dataset_id", "execution_id"])
def test_legacy_available_identities_cannot_contradict_manifest(tmp_path, key):
    (tmp_path / "manifest.json").write_text(
        json.dumps({"schema_version": "m1-run-v1", "status": "completed", key: "source"})
    )
    (tmp_path / "comparison.json").write_text(json.dumps({"baselines": {}, key: "foreign"}))
    with pytest.raises(ValueError, match="identity"):
        read_bundle(tmp_path)


def test_legacy_missing_new_bindings_remains_explicitly_limited(tmp_path):
    (tmp_path / "manifest.json").write_text(
        json.dumps({"schema_version": "m1-run-v1", "status": "completed", "dataset_id": "source"})
    )
    (tmp_path / "comparison.json").write_text(json.dumps({"baselines": {}, "dataset_id": "source"}))
    assert read_bundle(tmp_path)["legacy_compatibility"]["success_verified"] is False


def test_unknown_judge_durable_call_status_rejected(bundle):
    edit(bundle, "calls/judge-0.json", lambda call: call.update(status="unknown"))
    reject(bundle)


def test_generation_failure_requires_existing_compatible_call(bundle):
    run_id = json.loads((bundle / "manifest.json").read_text())["run_id"]
    edit(
        bundle,
        "generation_failures.jsonl",
        lambda rows: rows.append(
            {"run_id": run_id, "call_id": "foreign", "parser_version": "provider-v1"}
        ),
        lines=True,
    )
    reject(bundle)


@pytest.mark.parametrize("key", ["control_id", "baseline_id", "science_fingerprint", "baseline"])
def test_explicit_result_control_and_science_ids_are_authoritative(bundle, key):
    edit(bundle, "baselines/b1/metrics.json", lambda record: record.update({key: "foreign"}))
    edit(
        bundle,
        "comparison.json",
        lambda record: record["baselines"]["b1"]["intrinsic"].update({key: "foreign"}),
    )
    reject(bundle, metrics=True)


def test_judge_failure_cannot_reference_foreign_call(bundle):
    run_id = json.loads((bundle / "manifest.json").read_text())["run_id"]
    edit(
        bundle,
        "baselines/b3/judge_failures.jsonl",
        lambda rows: rows.append(
            {
                "run_id": run_id,
                "event_id": "judge-provider-foreign",
                "call_id": "foreign",
                "parser_version": "provider-v1",
            }
        ),
        lines=True,
    )
    reject(bundle)


def test_rejected_judge_decision_still_requires_its_recorded_result(bundle):
    def mutate(rows):
        row = next(row for row in rows if not row["accepted"] and row.get("judge_result_id"))
        row["judge_result_id"] = None

    edit(bundle, "baselines/b3/decisions.jsonl", mutate, lines=True)
    reject(bundle)


@pytest.mark.parametrize("mode", ["normal", "failed_first", "malformed_first"])
def test_fresh_fake_transport_reads_with_smoke_and_recorded_failures(tmp_path, monkeypatch, mode):
    from rcqasyn.experiments import runner
    from rcqasyn.generation.provider import ProviderResponse

    class FreshProvider:
        def call(self, **kwargs):
            if '"ok":true' in kwargs["prompt"]:
                text = '{"ok":true}'
            elif kwargs["role"] == "judge":
                text = '{"score":0.8,"verdict":"pass"}'
            elif kwargs["request_index"] == 0 and mode == "failed_first":
                raise RuntimeError("recorded first-batch failure")
            elif kwargs["request_index"] == 0 and mode == "malformed_first":
                text = "malformed"
            else:
                text = '[{"age":30,"score":1.0,"color":"red","label":"no"}]'
            return ProviderResponse(
                response=text,
                provider="fresh-fake",
                model="fresh-fake",
                endpoint=None,
                call_id="repeated-provider-id",
            )

    monkeypatch.setattr(runner, "_require_real_provider", lambda _: None)
    monkeypatch.setattr(runner, "_provider", lambda *args: FreshProvider())
    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    config = config.model_copy(
        update={
            "artifact_root": tmp_path,
            "run_id": None,
            "generation": config.generation.model_copy(
                update={"prompt_version": "v2", "transport_version": "v2"}
            ),
        }
    )
    run = run_experiment(config, replay=False)
    assert read_bundle(run.artifact_dir) == run.comparison
    smoke = json.loads((run.artifact_dir / "calls/generation-0.json").read_text())
    assert smoke["purpose"] == "generation_smoke"
    assert smoke["recorded_response_only"] is False


def test_legacy_available_baseline_identity_matches_authoritative_baseline(tmp_path):
    (tmp_path / "manifest.json").write_text(
        json.dumps({"schema_version": "m1-run-v1", "status": "completed", "dataset_id": "source"})
    )
    metric = {"baseline": "foreign"}
    (tmp_path / "comparison.json").write_text(
        json.dumps({"dataset_id": "source", "baselines": {"b1": {"intrinsic": metric}}})
    )
    directory = tmp_path / "baselines/b1"
    directory.mkdir(parents=True)
    (directory / "metrics.json").write_text(json.dumps(metric))
    with pytest.raises(ValueError, match="identity"):
        read_bundle(tmp_path)


@pytest.mark.parametrize("key", ["science_fingerprint", "scientific_fingerprint"])
def test_legacy_available_science_alias_matches_recorded_manifest(tmp_path, key):
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "m1-run-v1",
                "status": "completed",
                "specification_fingerprint": "source-science",
            }
        )
    )
    (tmp_path / "comparison.json").write_text(json.dumps({"baselines": {}, key: "foreign"}))
    with pytest.raises(ValueError, match="identity"):
        read_bundle(tmp_path)
