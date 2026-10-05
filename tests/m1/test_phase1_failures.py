import json
from pathlib import Path

import pytest

from rcqasyn.config import load_experiment_config
from rcqasyn.experiments import run_experiment
from rcqasyn.generation.provider import ReplayProvider


def config_at(tmp_path):
    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    return config.model_copy(update={"artifact_root": tmp_path, "run_id": None})


def test_repeated_provider_ids_are_not_join_keys(tmp_path, monkeypatch):
    from dataclasses import replace

    original = ReplayProvider.call

    def repeated(self, **kwargs):
        return replace(original(self, **kwargs), call_id="provider-call")

    monkeypatch.setattr(ReplayProvider, "call", repeated)
    run = run_experiment(config_at(tmp_path), replay=True)
    traces = [
        json.loads(line)
        for line in (run.artifact_dir / "provider_calls.jsonl").read_text().splitlines()
    ]
    assert len({trace["call_id"] for trace in traces}) == 2
    assert {trace["metadata"]["external_provider_call_id"] for trace in traces} == {"provider-call"}
    raw = [
        json.loads(line)
        for line in (run.artifact_dir / "candidates_raw.jsonl").read_text().splitlines()
    ]
    assert len({row["record_id"] for row in raw}) == len(raw)


@pytest.mark.parametrize("stage", ["parse", "trace", "aggregation", "finalization"])
def test_call_evidence_survives_downstream_exception(tmp_path, monkeypatch, stage):
    from rcqasyn.experiments import runner

    config = config_at(tmp_path)

    def broken(*args, **kwargs):
        raise RuntimeError("injected " + stage)

    attribute = {
        "parse": "parse_generation_response",
        "trace": "_trace",
        "aggregation": "_comparison",
        "finalization": "seal_bundle",
    }[stage]
    monkeypatch.setattr(runner, attribute, broken)
    with pytest.raises(RuntimeError, match="injected"):
        run_experiment(config, replay=True)
    directory = next((tmp_path / "runs").iterdir())
    evidence = list((directory / "calls").glob("*.json"))
    assert evidence and any("response" in json.loads(path.read_text()) for path in evidence)
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["status"] == "failed"
    assert manifest["success"] is False
    assert not (directory / "FINALIZED.json").exists()


@pytest.mark.parametrize("role", ["generation", "judge"])
def test_provider_failure_is_explicit(tmp_path, monkeypatch, role):
    original = ReplayProvider.call

    def failure(self, **kwargs):
        if kwargs["role"] == role:
            raise RuntimeError("injected provider failure")
        return original(self, **kwargs)

    monkeypatch.setattr(ReplayProvider, "call", failure)
    run = run_experiment(config_at(tmp_path), replay=True)
    assert run.comparison["outcome"]["success"] is False
    assert run.comparison["outcome"]["components"][role]["status"] == "partial"


def test_classifier_failure_is_explicit(tmp_path, monkeypatch):
    from sklearn.linear_model import LogisticRegression

    def failure(*args, **kwargs):
        raise ValueError("injected classifier")

    monkeypatch.setattr(LogisticRegression, "fit", failure)
    run = run_experiment(config_at(tmp_path), replay=True)
    outcome = run.comparison["outcome"]
    assert outcome["success"] is False and outcome["utility_evaluable"] is False
    assert "injected classifier" in str(outcome["components"]["b1.utility"]["reasons"])


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), "missing", "exception"])
def test_metric_unavailability_cannot_look_successful(tmp_path, monkeypatch, bad):
    from rcqasyn.experiments import runner

    original = runner.utility_metrics

    def broken(*args, **kwargs):
        result = original(*args, **kwargs)
        row = result["TRTR"]["random_forest"]
        if bad == "missing":
            row.pop("f1")
        elif bad == "exception":
            raise RuntimeError("metric exception")
        else:
            row["f1"] = bad
        return result

    monkeypatch.setattr(runner, "utility_metrics", broken)
    if bad == "exception":
        with pytest.raises(RuntimeError, match="metric exception"):
            run_experiment(config_at(tmp_path), replay=True)
        directory = next((tmp_path / "runs").iterdir())
        assert json.loads((directory / "manifest.json").read_text())["status"] == "failed"
    else:
        run = run_experiment(config_at(tmp_path), replay=True)
        assert not run.comparison["outcome"]["success"]
        row = run.comparison["baselines"]["b1"]["utility"]["TRTR"]["random_forest"]
        assert row["f1"] is None
        assert row["metric_availability"]["f1"]["reason"] == (
            "missing" if bad == "missing" else "nonfinite"
        )
        json.loads(
            (run.artifact_dir / "comparison.json").read_text(),
            parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)),
        )


def test_evidence_write_failure_prevents_parsing_and_success(tmp_path, monkeypatch):
    from rcqasyn.experiments import call_evidence, runner

    config = config_at(tmp_path)

    def broken(*args, **kwargs):
        raise OSError("disk full")

    calls = []
    monkeypatch.setattr(call_evidence, "write_json", broken)
    monkeypatch.setattr(runner, "parse_generation_response", lambda *a, **kw: calls.append(kw))
    with pytest.raises(call_evidence.EvidenceWriteError, match="durably"):
        run_experiment(config, replay=True)
    assert calls == []
    directory = next((tmp_path / "runs").iterdir())
    assert not (directory / "FINALIZED.json").exists()
    assert json.loads((directory / "manifest.json").read_text())["status"] == "failed"


@pytest.mark.parametrize("mode", ["exception", "nonfinite"])
def test_real_metric_failure_reason_is_preserved(tmp_path, monkeypatch, mode):
    from rcqasyn.metrics import utility

    def broken(*args, **kwargs):
        if mode == "exception":
            raise ValueError("actual metric failure")
        return float("nan")

    monkeypatch.setattr(utility, "f1_score", broken)
    run = run_experiment(config_at(tmp_path), replay=True)
    row = run.comparison["baselines"]["b1"]["utility"]["TRTR"]["random_forest"]
    reason = row["metric_availability"]["f1"]["reason"]
    assert ("actual metric failure" in reason) if mode == "exception" else reason == "nonfinite"
    assert run.comparison["outcome"]["success"] is False
