"""Independent verifier regressions for durable joins and review identity."""

import csv
import json
from pathlib import Path

import pytest

from rcqasyn.config import load_experiment_config
from rcqasyn.experiments import runner
from rcqasyn.experiments.call_evidence import DurableProvider
from rcqasyn.experiments.diagnostics import p1_human_review_sample
from rcqasyn.generation.provider import ProviderResponse
from rcqasyn.storage.ownership import execution_scope, own_run


def config_at(path):
    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    return config.model_copy(
        update={
            "artifact_root": path,
            "run_id": None,
            "generation": config.generation.model_copy(
                update={"prompt_version": "v2", "transport_version": "v2"}
            ),
        }
    )


class RecordingProvider:
    def __init__(self, failed_index=None, malformed_index=None):
        self.failed_index = failed_index
        self.malformed_index = malformed_index

    def call(self, **kwargs):
        if '"ok":true' in kwargs["prompt"]:
            text = '{"ok":true}'
        elif kwargs["role"] == "judge":
            text = '{"score":0.8,"verdict":"pass","rationale":"fixture"}'
        else:
            index = kwargs["request_index"]
            if index == self.failed_index:
                raise RuntimeError(f"failed batch {index}")
            text = (
                "malformed"
                if index == self.malformed_index
                else json.dumps(
                    [{"age": 30 + index, "income": 45000, "color": "red", "label": "yes"}]
                )
            )
        return ProviderResponse(
            response=text, provider="fake", model="fake", endpoint=None, call_id="provider-call"
        )


@pytest.mark.parametrize("failed_index", [0, 1])
def test_smoke_and_batch_failure_join_authoritative_attempt(tmp_path, monkeypatch, failed_index):
    monkeypatch.setattr(runner, "_require_real_provider", lambda _: None)
    monkeypatch.setattr(runner, "_provider", lambda *a: RecordingProvider(failed_index))
    config = config_at(tmp_path)
    config = config.model_copy(
        update={
            "generation": config.generation.model_copy(
                update={"requested_count": 12, "batch_size": 2}
            )
        }
    )
    run = runner.run_experiment(config, replay=False)
    events = [
        json.loads(line)
        for line in (run.artifact_dir / "generation_failures.jsonl").read_text().splitlines()
    ]
    failure = next(e for e in events if e["parser_version"] == "provider-v1")
    assert failure["call_id"] == f"generation-{failed_index + 1}"
    raw = json.loads((run.artifact_dir / "calls" / (failure["call_id"] + ".json")).read_text())
    assert raw["status"] == "failed"
    assert raw["request"]["request_index"] == failed_index
    assert (
        json.loads((run.artifact_dir / "calls/generation-0.json").read_text())["status"]
        == "returned"
    )
    assert not run.comparison["outcome"]["success"]
    later = run.artifact_dir / "calls/generation-6.json"
    assert json.loads(later.read_text())["status"] == "returned"


def test_malformed_batch_joins_returned_raw_response(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "_require_real_provider", lambda _: None)
    monkeypatch.setattr(runner, "_provider", lambda *a: RecordingProvider(malformed_index=0))
    run = runner.run_experiment(config_at(tmp_path), replay=False)
    events = [
        json.loads(line)
        for line in (run.artifact_dir / "generation_failures.jsonl").read_text().splitlines()
    ]
    malformed = next(e for e in events if e["raw_output"] == "malformed")
    assert malformed["call_id"] == "generation-1"
    raw = json.loads((run.artifact_dir / "calls/generation-1.json").read_text())
    assert raw["response"]["response"] == "malformed"


def test_durable_failure_carries_internal_identity(tmp_path):
    class Failed:
        def call(self, **kwargs):
            raise ValueError("transport rejected")

    with execution_scope():
        own_run(tmp_path)
        provider = DurableProvider(Failed(), tmp_path, "judge")
        with pytest.raises(Exception) as caught:
            provider.call(role="judge", prompt="safe")
        assert getattr(caught.value, "attempt_id", None) == "judge-0"
        assert json.loads((tmp_path / "calls/judge-0.json").read_text())["status"] == "failed"


def test_parser_exception_retains_distinct_smoke_and_batch_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "_require_real_provider", lambda _: None)
    monkeypatch.setattr(runner, "_provider", lambda *a: RecordingProvider())

    def broken(*a, **kw):
        assert kw["call_id"] == "generation-1"
        raise RuntimeError("downstream parser failure")

    monkeypatch.setattr(runner, "parse_generation_response", broken)
    with pytest.raises(RuntimeError, match="downstream parser"):
        runner.run_experiment(config_at(tmp_path), replay=False)
    directory = next((tmp_path / "runs").iterdir())
    for ordinal in (0, 1):
        assert (
            json.loads((directory / f"calls/generation-{ordinal}.json").read_text())["status"]
            == "returned"
        )
    assert json.loads((directory / "manifest.json").read_text())["success"] is False


def candidate_rows(run_id):
    return [
        {
            "run_id": run_id,
            "sampling_identity": "stable-scientific-fingerprint",
            "dataset_id": "same",
            "record_id": f"candidate-{i:03}",
            "role": "majority",
            "first_occurrence": True,
            "canonical_hash": str(i),
            "b2_status": "accepted",
            "b3_status": "accepted",
            "exact_reference_match": False,
            "exact_nonreference_train_match": False,
            "distance_band": "mid",
        }
        for i in range(100)
    ]


def test_new_review_selection_independent_of_execution_uuid(tmp_path, monkeypatch):
    from rcqasyn.experiments import diagnostics

    monkeypatch.setattr(diagnostics, "_run_candidate_table", lambda p, r: candidate_rows(p.name))

    def select(name, seed):
        output = tmp_path / f"{name}-{seed}.csv"
        p1_human_review_sample([Path(name)], Path.cwd(), output, target=10, seed=seed)
        with output.open(newline="") as stream:
            return [row["record_id"] for row in csv.DictReader(stream)]

    first = select("uuid-first", 42)
    assert first == select("uuid-second", 42)
    assert first != select("uuid-third", 43)


def test_durable_repeated_external_ids_do_not_collide(tmp_path):
    with execution_scope():
        own_run(tmp_path)
        provider = DurableProvider(RecordingProvider(), tmp_path, "generation")
        responses = [
            provider.call(role="generation", prompt="safe", request_index=i) for i in range(3)
        ]
    assert [r.call_id for r in responses] == ["generation-0", "generation-1", "generation-2"]
    assert {r.external_call_id for r in responses} == {"provider-call"}
    assert len(list((tmp_path / "calls").glob("*.json"))) == 3


def test_p1_script_consumes_existing_recorded_selection(tmp_path, monkeypatch):
    import importlib.util

    module_spec = importlib.util.spec_from_file_location(
        "p1_report_probe", Path("experiments/m1_5_p1_reports.py")
    )
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    recorded = tmp_path / "artifacts/reports/p1/p1_human_review.csv"
    recorded.parent.mkdir(parents=True)
    recorded.write_text("recorded selection", encoding="utf-8")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "OUT", tmp_path / "derived")
    received = []
    monkeypatch.setattr(
        module, "p1_human_review_sample", lambda *args, **kw: received.append((args, kw)) or {}
    )
    module._review_sample([tmp_path / "run"])
    assert received[0][1] == {"target": 120, "seed": 42, "recorded_sample": recorded}
    assert recorded.read_text() == "recorded selection"
