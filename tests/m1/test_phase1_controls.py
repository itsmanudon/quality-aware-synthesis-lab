import json
from pathlib import Path

import pytest

from rcqasyn.config import load_experiment_config
from rcqasyn.datasets import DatasetRegistry, build_profile, load_dataset, make_split
from rcqasyn.experiments.human_audit import classify_b2_evidence
from rcqasyn.experiments.runner import _run_b2
from rcqasyn.experiments.specification import control_policies
from rcqasyn.generation.parser import parse_generation_response


def test_b2_ordered_duplicates_keep_decisions_but_add_faithful_evidence(tmp_path):
    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    registry = DatasetRegistry(project_root=Path.cwd())
    data = load_dataset(registry.get("dev-small"), registry)
    split = make_split(data, 42)
    profile = build_profile(data, split)
    example = data.frame.loc[split.train_indices[0]].to_dict()
    parsed = parse_generation_response(
        json.dumps([example, example]),
        run_id="fixture",
        call_id="call",
        generator_id="fixture",
        generator_version="1",
        prompt_version="v1",
        seed=42,
    )
    result = _run_b2(
        list(parsed.candidates),
        data.frame.loc[list(split.train_indices)],
        data.spec,
        profile,
        config,
        tmp_path,
        lambda synthetic: ({}, {"TRTR": {}, "TSTR": {}}),
    )
    assert result["accepted"] == 1 and result["deterministic_violations"] == 0
    decisions = [
        json.loads(x) for x in (tmp_path / "baselines/b2/decisions.jsonl").read_text().splitlines()
    ]
    assert [row["accepted"] for row in decisions] == [True, False]
    evidence = [
        json.loads(x) for x in (tmp_path / "baselines/b2/evidence.jsonl").read_text().splitlines()
    ]
    duplicate = [row for row in evidence if row["candidate_id"] == decisions[1]["candidate_id"]]
    assert classify_b2_evidence(duplicate) == "redundancy_only"
    assert duplicate[-1]["metadata"]["first_seen_candidate_id"] == decisions[0]["candidate_id"]
    # Rejected first occurrences still consume equality/order state.
    invalid = {**example, "color": "TRAIN_UNSEEN"}
    parsed = parse_generation_response(
        json.dumps([invalid, invalid]),
        run_id="fixture",
        call_id="invalid",
        generator_id="fixture",
        generator_version="1",
        prompt_version="v1",
        seed=42,
    )
    result = _run_b2(
        list(parsed.candidates),
        data.frame.loc[list(split.train_indices)],
        data.spec,
        profile,
        config,
        tmp_path / "invalid",
        lambda synthetic: ({}, {"TRTR": {}, "TSTR": {}}),
    )
    assert result["accepted"] == 0
    decisions = [
        json.loads(x)
        for x in (tmp_path / "invalid/baselines/b2/decisions.jsonl").read_text().splitlines()
    ]
    assert decisions[1]["reason"] == "duplicate"


def test_policy_fingerprints_lock_frozen_control_configuration():
    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    policies = control_policies(config)
    assert policies["b1"]["descriptor"]["admission"] == "all_parseable"
    assert (
        policies["b2"]["descriptor"]["duplicates"]
        == "exact_canonical_json_all_keys_first_seen_even_if_rejected"
    )
    assert policies["b3"]["descriptor"]["threshold"] == 0.7
    assert len({p["fingerprint"] for p in policies.values()}) == 3


def test_frozen_descriptor_fingerprints():
    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    assert {k: v["fingerprint"] for k, v in control_policies(config).items()} == {
        "b1": "a403e29a8703c7e2df1e4727351d3a123e91dc54a574f684581ff8342984e137",
        "b2": "f98d52627d410617243a8852569b0f84691b98e612345cb9639aec1d48c4c62b",
        "b3": "91e863c783939e4c334683aeb4e9f0f58f63f370450cf07b2664dd4c3b9bef9a",
    }


@pytest.mark.parametrize(
    "score,verdict,accepted",
    [
        (0.7, "pass", True),
        (0.7, "warn", True),
        (0.699, "pass", False),
        (1.0, "fail", False),
        (1.0, "unknown", False),
    ],
)
def test_b3_static_threshold_and_verdict_regression(score, verdict, accepted):
    from rcqasyn.baselines.judge import SingleLLMJudge
    from rcqasyn.generation.provider import ProviderResponse

    class Provider:
        def call(self, **kwargs):
            return ProviderResponse(
                response=json.dumps({"score": score, "verdict": verdict}),
                provider="fixture",
                model="fixture",
                endpoint=None,
            )

    judge = SingleLLMJudge(Provider(), threshold=0.7)
    result = judge.evaluate(
        prompt="TRAIN fixture",
        run_id="run",
        candidate_id="c",
        request_index=0,
        seed=42,
        max_tokens=2048,
    )
    assert result.result is not None and judge.accepts(result.result) == accepted


def test_b1_keeps_parseable_malformed_targets_and_b3_rejects_malformed_judgment(
    tmp_path, monkeypatch
):
    from dataclasses import replace

    from rcqasyn.experiments import runner
    from rcqasyn.generation.provider import ReplayProvider

    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    original = ReplayProvider.call

    def response(self, **kwargs):
        returned = original(self, **kwargs)
        if kwargs["role"] == "generation":
            return replace(returned, response='[{"age":3,"score":0.2,"color":"red","label":null}]')
        return replace(returned, response="malformed")

    monkeypatch.setattr(ReplayProvider, "call", response)
    run = runner.run_experiment(config.model_copy(update={"artifact_root": tmp_path}), replay=True)
    b1, b3 = run.comparison["baselines"]["b1"], run.comparison["baselines"]["b3"]
    assert b1["accepted"] == 2 and b3["accepted"] == 0 and b3["judge_malformed"] == 2
    candidates = [
        json.loads(x)
        for x in (run.artifact_dir / "baselines/b1/candidates.jsonl").read_text().splitlines()
    ]
    assert all(row["data"]["label"] is None for row in candidates)
    assert run.comparison["outcome"]["success"] is False
