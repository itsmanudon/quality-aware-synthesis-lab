# pyright: reportArgumentType=false, reportAttributeAccessIssue=false
from __future__ import annotations

import json
import platform
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from rcqasyn.baselines.judge import SingleLLMJudge
from rcqasyn.baselines.validators import ValidatorSuite, rejects
from rcqasyn.config.experiment import ExperimentConfig
from rcqasyn.contracts import (
    BaselineDecision,
    CandidateRecord,
    ClassQuota,
    GenerationPlan,
    JudgeResult,
    ParseFailureEvent,
    ProviderCallTrace,
    Verdict,
)
from rcqasyn.datasets import DatasetRegistry, build_profile, load_dataset, make_split
from rcqasyn.generation.parser import parse_generation_response
from rcqasyn.generation.prompts import load_prompt
from rcqasyn.generation.provider import (
    OpenAICompatibleGenerator,
    ProviderResponse,
    ReplayGenerator,
)
from rcqasyn.metrics import intrinsic_metrics, utility_metrics
from rcqasyn.storage.artifacts import create_run_dir, write_json
from rcqasyn.storage.jsonl import append_jsonl
from rcqasyn.utils.hashing import sha256_text


@dataclass(frozen=True)
class BaselineRunResult:
    run_id: str
    artifact_dir: Path
    comparison: dict[str, Any]


def run_experiment(config: ExperimentConfig, *, project_root: Path | None = None, replay: bool = False) -> BaselineRunResult:
    root = (project_root or Path.cwd()).resolve()
    if config.generation.objective != "data_emulation":
        raise ValueError("M1 execution supports objective=data_emulation only; minority_augmentation is planned")
    registry = DatasetRegistry(project_root=root)
    spec = registry.get(config.dataset.dataset_id)
    dataset = load_dataset(spec, registry)
    split = make_split(dataset, config.dataset.root_seed)
    profile = build_profile(
        dataset, split, reference_example_count=config.dataset.reference_example_count,
        seed=config.dataset.root_seed, enabled=config.dataset.reference_examples_enabled,
    )
    generation_prompt = load_prompt("generation", config.generation.prompt_version, root)
    judge_prompt = load_prompt("judge", config.judge.prompt_version, root)
    plan = _generation_plan(config, profile, generation_prompt.sha256)
    # Validate both independently selectable providers before reserving an artifact directory.
    generator = _provider(config.generator, root, replay)
    judge_provider = _provider(config.judge.provider, root, False)
    run_id = config.run_id or f"{config.experiment_name}-{config.canonical_hash()[:12]}"
    artifact_root = config.artifact_root
    if not artifact_root.is_absolute():
        artifact_root = root / artifact_root
    run_dir = create_run_dir(artifact_root / "runs", run_id, exist_ok=False)
    _write_json(run_dir / "manifest.json", {
        "schema_version": "m1-run-v1", "run_id": run_id, "experiment_name": config.experiment_name,
        "status": "running", "started_at": datetime.now(UTC).isoformat(), "root_seed": config.dataset.root_seed,
        "dataset_id": spec.dataset_id, "dataset_fingerprint": dataset.fingerprint, "config_hash": config.canonical_hash(),
        "replay": replay, "no_test_leakage": True, "python_version": sys.version.split()[0],
        "platform": platform.platform(), "git_commit": _git_commit(root), "git_dirty": _git_dirty(root),
    })
    _write_yaml(run_dir / "resolved_config.yaml", config.model_dump(mode="json"))
    _write_json(run_dir / "dataset" / "split_manifest.json", split.to_dict())
    _write_json(run_dir / "dataset" / "profile.json", profile.model_dump(mode="json"))
    _write_json(run_dir / "generation_plan.json", plan.model_dump(mode="json"))

    raw_candidates, traces, parse_failures, requested_calls = _generate_pool(config, run_id, plan, profile, generation_prompt.text, generator)
    _write_jsonl(run_dir / "provider_calls.jsonl", traces)
    _write_jsonl(run_dir / "generation_failures.jsonl", parse_failures)
    _write_jsonl(run_dir / "candidates_raw.jsonl", raw_candidates)

    b1 = _run_b1(raw_candidates, dataset.frame, split.train_indices, split.test_indices, spec, config, run_dir)
    b2 = _run_b2(raw_candidates, dataset.frame, split.train_indices, split.test_indices, spec, profile, config, run_dir)
    b3 = _run_b3(raw_candidates, dataset.frame, split.train_indices, split.test_indices, spec, profile, config, judge_prompt.text, judge_prompt.sha256, judge_prompt.version, run_dir, judge_provider)
    judge_calls = b3["judge_calls"]
    comparison = _comparison(config, plan, raw_candidates, parse_failures, traces, requested_calls, judge_calls, b1, b2, b3)
    comparison["completed_at"] = datetime.now(UTC).isoformat()
    _write_json(run_dir / "comparison.json", comparison)
    manifest = _read_json(run_dir / "manifest.json")
    manifest.update({"status": "completed", "completed_at": comparison["completed_at"], "provider_call_count": requested_calls + judge_calls})
    _write_json(run_dir / "manifest.json", manifest, overwrite=True)
    return BaselineRunResult(run_id, run_dir, comparison)


def _generation_plan(config: ExperimentConfig, profile: Any, prompt_hash: str) -> GenerationPlan:
    quotas: dict[str, int]
    known_labels = set(profile.class_counts)
    if config.generation.class_strategy == "explicit":
        raw_quotas = {str(key): int(value) for key, value in config.generation.class_quotas.items()}
        quotas = {label: count for label, count in raw_quotas.items() if count > 0}
        unknown = sorted(set(quotas) - known_labels)
        if unknown:
            raise ValueError(f"explicit class_quotas contain labels absent from TRAIN: {unknown}; known labels: {sorted(known_labels)}")
        if sum(quotas.values()) != config.generation.requested_count:
            raise ValueError("positive explicit class_quotas must sum to requested_count; zero quotas are ignored")
    else:
        quotas = _proportional_quotas(profile.class_proportions, config.generation.requested_count)
    if not quotas or sum(quotas.values()) != config.generation.requested_count:
        raise ValueError("resolved class quotas must cover requested_count")
    return GenerationPlan(
        plan_id=f"plan-{config.canonical_hash()[:16]}", requested_count=config.generation.requested_count,
        requested_class=next(iter(quotas)) if len(quotas) == 1 else None,
        dataset_id=profile.dataset_id, objective=config.generation.objective, class_strategy=config.generation.class_strategy,
        class_quotas=tuple(ClassQuota(label=label, count=count) for label, count in sorted(quotas.items())),
        reference_example_count=config.dataset.reference_example_count,
        reference_examples_enabled=config.dataset.reference_examples_enabled, source_profile_id=profile.profile_id,
        source_profile_hash=sha256_text(profile.model_dump_json()), generator_id=config.generation.generator_id,
        generator_version=config.generation.generator_version,
        generator_config={"generation": config.generation.model_dump(mode="json"), "provider": config.generator.model_dump(mode="json")},
        prompt_version=config.generation.prompt_version,
        prompt_hash=prompt_hash, batch_size=config.generation.batch_size, seed=config.dataset.root_seed,
    )


def _proportional_quotas(proportions: dict[str, float], requested: int) -> dict[str, int]:
    if not proportions:
        return {}
    raw = {label: value * requested for label, value in proportions.items()}
    result = {label: int(value) for label, value in raw.items()}
    for label in sorted(raw, key=lambda key: (-(raw[key] - result[key]), key))[: requested - sum(result.values())]:
        result[label] += 1
    return {label: count for label, count in result.items() if count > 0}


def _provider(config: Any, root: Path, replay: bool) -> Any:
    kind = config.kind.lower()
    if kind == "replay" or replay:
        if config.fixture is None:
            raise ValueError("replay provider requires fixture")
        fixture = config.fixture if config.fixture.is_absolute() else (root / config.fixture).resolve()
        return ReplayGenerator(fixture, model=config.model)
    if kind in {"openai", "openai_compatible"}:
        return OpenAICompatibleGenerator(base_url=config.base_url or "", model=config.model, api_key_env=config.api_key_env, timeout=config.timeout_seconds)
    raise ValueError(f"unsupported provider kind {config.kind!r}")


def _generate_pool(config: ExperimentConfig, run_id: str, plan: GenerationPlan, profile: Any, prompt_text: str, provider: Any) -> tuple[list[CandidateRecord], list[ProviderCallTrace], list[ParseFailureEvent], int]:
    candidates: list[CandidateRecord] = []
    traces: list[ProviderCallTrace] = []
    failures: list[ParseFailureEvent] = []
    requests: list[tuple[str, int]] = []
    for quota in plan.class_quotas:
        remaining = quota.count
        while remaining > 0:
            count = min(plan.batch_size, remaining)
            requests.append((quota.label, count))
            remaining -= count
    requested_calls = len(requests)
    for call_index, (requested_class, count) in enumerate(requests):
        prompt = prompt_text.format(profile_json=json.dumps(profile.model_dump(mode="json"), sort_keys=True), class_condition=requested_class, requested_count=count, reference_examples=json.dumps(profile.reference_examples, sort_keys=True))
        call_id = f"generation-{call_index}"
        try:
            response = provider.call(role="generation", prompt=prompt, request_index=call_index, temperature=config.generation.temperature, seed=config.generation.provider_seed, max_tokens=config.generation.max_tokens)
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            failures.append(ParseFailureEvent(
                event_id=f"provider-generation-{call_index}", run_id=run_id, call_id=call_id,
                parser_version="provider-v1", error=f"provider failure: {error}", recoverable=False,
                created_at=datetime.now(UTC), metadata={"requested_class": requested_class, "requested_count": count,
                                                       "temperature": config.generation.temperature, "max_tokens": config.generation.max_tokens},
            ))
            continue
        call_id = response.call_id or call_id
        traces.append(_trace(
            run_id, "generation", response, config.generation.prompt_version, plan.prompt_hash, count,
            config.generation.provider_seed, requested_class, prompt=prompt,
            temperature=config.generation.temperature, max_tokens=config.generation.max_tokens,
        ))
        parsed = parse_generation_response(response.response, run_id=run_id, call_id=call_id, generator_id=plan.generator_id, generator_version=plan.generator_version, prompt_version=plan.prompt_version, seed=config.generation.provider_seed, requested_class=requested_class)
        candidates.extend(parsed.candidates)
        failures.extend(parsed.failures)
    return candidates, traces, failures, requested_calls


def _trace(run_id: str, role: str, response: ProviderResponse, prompt_version: str | None, prompt_hash: str | None, requested_count: int | None, seed: int | None, requested_class: str | None = None, *, prompt: str | None = None, temperature: float | None = None, max_tokens: int | None = None) -> ProviderCallTrace:
    return ProviderCallTrace(
        call_id=response.call_id or f"call-{sha256_text(response.response)[:12]}", run_id=run_id, role=role,
        provider=response.provider, model=response.model, endpoint=response.endpoint, prompt_version=prompt_version,
        prompt_hash=prompt_hash, prompt=prompt, raw_response=response.response,
        requested_class=requested_class, requested_count=requested_count, max_tokens=max_tokens,
        temperature=temperature, seed=seed, input_tokens=response.input_tokens,
        output_tokens=response.output_tokens, total_tokens=response.total_tokens, cost_usd=response.cost_usd,
        latency_ms=response.latency_ms, created_at=response.created_at, replay_source_id=response.replay_source_id,
    )


def _run_b1(candidates: list[CandidateRecord], frame: pd.DataFrame, train_idx: tuple[int, ...], test_idx: tuple[int, ...], spec: Any, config: ExperimentConfig, run_dir: Path) -> dict[str, Any]:
    accepted = list(candidates)
    result = _persist_baseline("b1", accepted, candidates, frame, train_idx, test_idx, spec, config, run_dir, decisions=[BaselineDecision(candidate_id=c.record_id, baseline="b1", accepted=True, reason="all parseable candidates accepted", created_at=datetime.now(UTC)) for c in candidates])
    result["failure_counts"] = {"duplicate": _duplicate_count(candidates)}
    return result


def _run_b2(candidates: list[CandidateRecord], frame: pd.DataFrame, train_idx: tuple[int, ...], test_idx: tuple[int, ...], spec: Any, profile: Any, config: ExperimentConfig, run_dir: Path) -> dict[str, Any]:
    suite = ValidatorSuite(spec, profile, range_severity=config.baselines.range_severity)
    accepted: list[CandidateRecord] = []
    all_evidence: list[Any] = []
    decisions: list[BaselineDecision] = []
    seen: set[str] = set()
    for candidate in candidates:
        requested_class = candidate.metadata.get("requested_class")
        expected_class = requested_class if isinstance(requested_class, str) else None
        evidence = suite.validate(candidate, expected_class=expected_class)
        all_evidence.extend(evidence)
        duplicate = _canonical_hash(candidate) in seen
        seen.add(_canonical_hash(candidate))
        reject = rejects(evidence, frozenset(config.baselines.reject_severities)) or duplicate
        if not reject:
            accepted.append(candidate)
        reason = "duplicate" if duplicate else "configured deterministic severity rejection" if reject else "all configured deterministic checks passed"
        decisions.append(BaselineDecision(candidate_id=candidate.record_id, baseline="b2", accepted=not reject, reason=reason, evidence_ids=tuple(item.evidence_id for item in evidence), created_at=datetime.now(UTC)))
    result = _persist_baseline("b2", accepted, candidates, frame, train_idx, test_idx, spec, config, run_dir, decisions=decisions, evidence=all_evidence)
    result["deterministic_rejections"] = sum(not decision.accepted for decision in decisions)
    missing_candidates = {item.candidate_id for item in all_evidence if item.metadata.get("missing_fields")}
    category_candidates = {item.candidate_id for item in all_evidence if item.validator_id == "categorical-domain" and item.verdict == Verdict.FAIL}
    target_candidates = {item.candidate_id for item in all_evidence if item.validator_id == "target-condition" and item.verdict == Verdict.FAIL}
    result["failure_counts"] = {
        "missing_field": len(missing_candidates),
        "category_invalid": len(category_candidates),
        "target_wrong": len(target_candidates),
        "duplicate": _duplicate_count(candidates),
        "deterministic_structural_rejection": result["deterministic_rejections"],
    }
    result["deterministic_violations"] = len({item.candidate_id for item in all_evidence if item.verdict == Verdict.FAIL})
    result["deterministic_rejection_rate"] = result["deterministic_rejections"] / len(candidates) if candidates else None
    result["deterministic_violation_rate"] = result["deterministic_violations"] / len(candidates) if candidates else None
    return result


def _run_b3(candidates: list[CandidateRecord], frame: pd.DataFrame, train_idx: tuple[int, ...], test_idx: tuple[int, ...], spec: Any, profile: Any, config: ExperimentConfig, judge_text: str, judge_hash: str, judge_version: str, run_dir: Path, provider: Any) -> dict[str, Any]:
    judge = SingleLLMJudge(provider, threshold=config.judge.threshold, malformed_policy=config.judge.malformed_policy)
    accepted: list[CandidateRecord] = []
    decisions: list[BaselineDecision] = []
    results: list[JudgeResult] = []
    failures: list[ParseFailureEvent] = []
    traces: list[ProviderCallTrace] = []
    provider_failures = 0
    for index, candidate in enumerate(candidates):
        prompt = judge_text.format(profile_json=json.dumps(profile.model_dump(mode="json"), sort_keys=True), candidate_json=json.dumps(candidate.data, sort_keys=True))
        try:
            evaluation = judge.evaluate(
                prompt=prompt, run_id=run_dir.name, candidate_id=candidate.record_id,
                request_index=index, seed=config.generation.provider_seed, max_tokens=config.generation.max_tokens,
            )
            response = evaluation.response
            call_id = response.call_id or f"judge-{index}"
            traces.append(_trace(
                run_dir.name, "judge", response, f"judge-{judge_version}", judge_hash, None,
                config.generation.provider_seed, prompt=prompt, temperature=0.0, max_tokens=config.generation.max_tokens,
            ))
            if evaluation.error is not None:
                failures.append(ParseFailureEvent(event_id=f"judge-parse-{candidate.record_id}", run_id=run_dir.name, call_id=call_id, parser_version="judge-json-v1", raw_output=response.response, error=evaluation.error, recoverable=False, created_at=datetime.now(UTC)))
                decisions.append(BaselineDecision(candidate_id=candidate.record_id, baseline="b3", accepted=False, reason="malformed judge output; configured reject policy", created_at=datetime.now(UTC)))
                continue
            result = evaluation.result
            if result is None:
                raise RuntimeError("judge returned neither a result nor a parse error")
            results.append(result)
            accept = judge.accepts(result)
            if accept:
                accepted.append(candidate)
            decisions.append(BaselineDecision(candidate_id=candidate.record_id, baseline="b3", accepted=accept, reason="single judge score meets static threshold" if accept else "single judge rejected below static threshold", judge_result_id=result.result_id, created_at=datetime.now(UTC)))
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            provider_failures += 1
            failures.append(ParseFailureEvent(event_id=f"judge-provider-{candidate.record_id}", run_id=run_dir.name, call_id=f"judge-{index}", parser_version="provider-v1", error=f"judge provider failure: {error}", recoverable=False, created_at=datetime.now(UTC)))
            decisions.append(BaselineDecision(candidate_id=candidate.record_id, baseline="b3", accepted=False, reason="judge provider failure", created_at=datetime.now(UTC)))
    result = _persist_baseline("b3", accepted, candidates, frame, train_idx, test_idx, spec, config, run_dir, decisions=decisions, judge_results=results)
    _write_jsonl(run_dir / "baselines" / "b3" / "judge_failures.jsonl", failures)
    _write_jsonl(run_dir / "baselines" / "b3" / "provider_calls.jsonl", traces)
    result["judge_attempted_calls"] = len(candidates)
    result["judge_successful_calls"] = len(traces)
    result["judge_calls"] = len(candidates)
    result["judge_rejections"] = sum(not decision.accepted for decision in decisions if decision.reason != "malformed judge output; configured reject policy")
    result["judge_malformed"] = sum(1 for failure in failures if failure.parser_version == "judge-json-v1")
    result["judge_provider_failures"] = provider_failures
    result["judge_rejection_rate"] = result["judge_rejections"] / len(candidates) if candidates else None
    result["judge_input_tokens"] = _sum_nullable([trace.input_tokens for trace in traces])
    result["judge_output_tokens"] = _sum_nullable([trace.output_tokens for trace in traces])
    result["judge_total_tokens"] = _sum_nullable([trace.total_tokens for trace in traces])
    result["judge_cost_usd"] = _sum_cost_nullable([trace.cost_usd for trace in traces])
    if provider_failures:
        result["judge_input_tokens"] = None
        result["judge_output_tokens"] = None
        result["judge_total_tokens"] = None
        result["judge_cost_usd"] = None
    result["judge_latency_ms"] = None if provider_failures or any(trace.latency_ms is None for trace in traces) else sum(trace.latency_ms or 0.0 for trace in traces)
    result["failure_counts"] = {"judge_rejection": result["judge_rejections"], "judge_malformed": result["judge_malformed"], "duplicate": _duplicate_count(candidates)}
    return result


def _persist_baseline(name: str, accepted: list[CandidateRecord], all_candidates: list[CandidateRecord], frame: pd.DataFrame, train_idx: tuple[int, ...], test_idx: tuple[int, ...], spec: Any, config: ExperimentConfig, run_dir: Path, *, decisions: list[BaselineDecision], evidence: list[Any] | None = None, judge_results: list[JudgeResult] | None = None) -> dict[str, Any]:
    directory = run_dir / "baselines" / name
    _write_jsonl(directory / "candidates.jsonl", accepted)
    _write_jsonl(directory / "decisions.jsonl", decisions)
    if evidence is not None:
        _write_jsonl(directory / "evidence.jsonl", evidence)
    if judge_results is not None:
        _write_jsonl(directory / "judge_results.jsonl", judge_results)
    train = frame.loc[list(train_idx)]
    test = frame.loc[list(test_idx)]
    synthetic = pd.DataFrame([candidate.data for candidate in accepted], columns=[*spec.feature_columns, spec.target_column])
    intrinsic = intrinsic_metrics(train, synthetic, spec)
    utility = utility_metrics(train, test, synthetic, spec, seed=config.dataset.root_seed, classifiers=config.metrics.classifiers)
    _write_json(directory / "metrics.json", intrinsic)
    _write_json(directory / "classifier_metrics.json", utility)
    duplicate_hashes = [_canonical_hash(candidate) for candidate in all_candidates]
    duplicates = len(duplicate_hashes) - len(set(duplicate_hashes))
    raw_pool_count = len(all_candidates)
    accepted_generated_ratio = len(accepted) / raw_pool_count if raw_pool_count else None
    return {
        "requested": config.generation.requested_count,
        "raw_pool_count": raw_pool_count,
        "accepted": len(accepted),
        "acceptance_rate": accepted_generated_ratio,
        "accepted_generated_ratio": accepted_generated_ratio,
        "duplicates": duplicates,
        "exact_duplicate_count": duplicates,
        "exact_duplicate_rate": duplicates / raw_pool_count if raw_pool_count else None,
        "unique_count": len(set(duplicate_hashes)),
        "calls": 0,
        "cost_usd": None,
        "intrinsic": intrinsic,
        "utility": utility,
    }


def _comparison(config: ExperimentConfig, plan: GenerationPlan, candidates: list[CandidateRecord], failures: list[ParseFailureEvent], traces: list[ProviderCallTrace], requested_calls: int, judge_calls: int, b1: dict[str, Any], b2: dict[str, Any], b3: dict[str, Any]) -> dict[str, Any]:
    generation_input_tokens = _sum_nullable([trace.input_tokens for trace in traces]) if requested_calls == len(traces) else None
    generation_output_tokens = _sum_nullable([trace.output_tokens for trace in traces]) if requested_calls == len(traces) else None
    generation_total_tokens = _sum_nullable([trace.total_tokens for trace in traces]) if requested_calls == len(traces) else None
    judge_input_tokens = b3.get("judge_input_tokens")
    judge_output_tokens = b3.get("judge_output_tokens")
    judge_total_tokens = b3.get("judge_total_tokens")
    input_tokens = _sum_nullable([generation_input_tokens], judge_input_tokens)
    output_tokens = _sum_nullable([generation_output_tokens], judge_output_tokens)
    total_tokens = _sum_nullable([generation_total_tokens], judge_total_tokens)
    generation_latency = None if requested_calls != len(traces) or any(trace.latency_ms is None for trace in traces) else sum(trace.latency_ms or 0.0 for trace in traces)
    judge_latency = b3.get("judge_latency_ms")
    latency_ms = None if generation_latency is None or judge_latency is None else generation_latency + float(judge_latency)
    generation_cost = _sum_cost_nullable([trace.cost_usd for trace in traces]) if requested_calls == len(traces) else None
    judge_cost = b3.get("judge_cost_usd")
    cost_usd = _sum_cost_nullable([generation_cost], judge_cost)
    return {
        "schema_version": "m1-comparison-v1", "requested": plan.requested_count, "experiment_requested": plan.requested_count,
        "generation_attempted_calls": requested_calls, "generation_successful_calls": len(traces),
        "generation_calls": requested_calls, "judge_attempted_calls": int(b3.get("judge_attempted_calls", judge_calls)),
        "judge_successful_calls": int(b3.get("judge_successful_calls", judge_calls)), "judge_calls": judge_calls,
        "judge_provider_failures": int(b3.get("judge_provider_failures", 0)),
        "provider_calls": requested_calls + int(b3.get("judge_attempted_calls", judge_calls)),
        "raw_pool_count": len(candidates), "parseable_record_count": len(candidates),
        "parse_success": len(candidates), "parse_success_rate": len(candidates) / plan.requested_count if plan.requested_count else None,
        "parse_failures": len(failures), "failure_aggregation": _aggregate_failures(failures, b1, b2, b3), "baselines": {"b1": b1, "b2": b2, "b3": b3},
        "deterministic_violation_rate": b2.get("deterministic_violation_rate"),
        "deterministic_rejection_rate": b2.get("deterministic_rejection_rate"),
        "judge_rejection_rate": b3.get("judge_rejection_rate"),
        "generation_input_tokens": generation_input_tokens, "generation_output_tokens": generation_output_tokens,
        "generation_total_tokens": generation_total_tokens, "judge_input_tokens": judge_input_tokens,
        "judge_output_tokens": judge_output_tokens, "judge_total_tokens": judge_total_tokens,
        "generation_latency_ms": generation_latency, "judge_latency_ms": judge_latency,
        "generation_cost_usd": generation_cost, "judge_cost_usd": judge_cost,
        "input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": total_tokens,
        "latency_ms": latency_ms, "cost_usd": cost_usd,
        "no_significance_claim": True, "policy": {"b1": "accept all parseable", "b2": "configured deterministic severity filtering", "b3": "one judge + static threshold + no calibration"},
    }


_MISSING = object()


def _sum_nullable(values: list[object], extra: object = _MISSING) -> int | None:
    all_values = [*values] if extra is _MISSING else [*values, extra]
    if any(value is not None and not isinstance(value, (int, float)) for value in all_values):
        return None
    if any(value is None for value in all_values):
        return None
    return int(sum(float(value) for value in all_values))


def _sum_cost_nullable(values: list[object], extra: object = _MISSING) -> float | None:
    all_values = [*values] if extra is _MISSING else [*values, extra]
    if any(value is not None and not isinstance(value, (int, float)) for value in all_values):
        return None
    if any(value is None for value in all_values):
        return None
    return float(sum(float(value) for value in all_values))


def _canonical_hash(candidate: CandidateRecord) -> str:
    return sha256_text(json.dumps(candidate.data, sort_keys=True, separators=(",", ":")))


def _duplicate_count(candidates: list[CandidateRecord]) -> int:
    hashes = [_canonical_hash(candidate) for candidate in candidates]
    return len(hashes) - len(set(hashes))


def _aggregate_failures(failures: list[ParseFailureEvent], b1: dict[str, Any], b2: dict[str, Any], b3: dict[str, Any]) -> dict[str, int]:
    result = {"parse_failure": len(failures), "missing_field": 0, "category_invalid": 0, "target_wrong": 0, "duplicate": 0, "deterministic_structural_rejection": 0, "judge_rejection": 0, "judge_malformed": 0, "judge_provider_failure": int(b3.get("judge_provider_failures", 0))}
    for summary in (b1, b2, b3):
        for key, value in summary.get("failure_counts", {}).items():
            result[key] = max(result.get(key, 0), int(value))
    result["deterministic_structural_rejection"] = b2.get("failure_counts", {}).get("deterministic_structural_rejection", 0)
    result["judge_rejection"] = b3.get("failure_counts", {}).get("judge_rejection", 0)
    result["judge_malformed"] = b3.get("failure_counts", {}).get("judge_malformed", 0)
    return result


def _write_json(path: Path, value: Any, *, overwrite: bool = False) -> None:
    write_json(path, value, overwrite=overwrite)


def _write_jsonl(path: Path, values: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if values:
        append_jsonl(path, values)
    else:
        path.touch(exist_ok=False)


def _write_yaml(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=True), encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _git_commit(root: Path) -> str | None:
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False)
        return result.stdout.strip() or None if result.returncode == 0 else None
    except OSError:
        return None


def _git_dirty(root: Path) -> bool | None:
    try:
        result = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=False)
        return bool(result.stdout.strip()) if result.returncode == 0 else None
    except OSError:
        return None
