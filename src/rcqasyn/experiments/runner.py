# pyright: reportArgumentType=false, reportAttributeAccessIssue=false
from __future__ import annotations

import json
import platform
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from string import Formatter
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import pandas as pd
import yaml

from rcqasyn.baselines.judge import SingleLLMJudge
from rcqasyn.baselines.validators import ValidatorSuite, rejects
from rcqasyn.config.experiment import ExperimentConfig
from rcqasyn.contracts import (
    BaselineDecision,
    CandidateRecord,
    ClassQuota,
    Evidence,
    GenerationPlan,
    JudgeResult,
    ParseFailureEvent,
    ProviderCallTrace,
    QualityDimension,
    Severity,
    Verdict,
)
from rcqasyn.contracts.m1 import (
    annotate_intrinsic,
    annotate_utility,
    execution_outcome,
    finite_tree,
    validate_comparison,
)
from rcqasyn.datasets import DatasetRegistry, build_profile, load_dataset, make_split
from rcqasyn.datasets.training import TrainingContext
from rcqasyn.experiments.analysis import (
    export_disagreements,
    export_human_review,
    machine_failure_report,
)
from rcqasyn.generation.parser import parse_generation_response
from rcqasyn.generation.prompts import load_prompt
from rcqasyn.generation.provider import (
    OpenAICompatibleGenerator,
    ProviderResponse,
    ReplayGenerator,
    ReplayProvider,
    provider_readiness,
)
from rcqasyn.metrics import intrinsic_metrics, utility_metrics
from rcqasyn.storage.artifacts import create_run_dir, write_json, write_text
from rcqasyn.storage.jsonl import append_jsonl
from rcqasyn.storage.ownership import (
    assert_writable,
    execution_scope,
    file_hash,
    own_run,
    seal_bundle,
)
from rcqasyn.utils.hashing import sha256_text
from rcqasyn.utils.seeds import generation_provider_seed

from .artifact_identity import BINDING_VERSION, write_execution_bindings
from .call_evidence import DurableCallFailure, DurableProvider
from .specification import environment_snapshot, scientific_specification, seed_provenance


@dataclass(frozen=True)
class BaselineRunResult:
    run_id: str
    artifact_dir: Path
    comparison: dict[str, Any]



def run_experiment(config: ExperimentConfig, *, project_root: Path | None = None, replay: bool = False) -> BaselineRunResult:
    with execution_scope() as paths:
        try:
            return _execute_experiment(config, project_root=project_root, replay=replay)
        except Exception as error:
            for directory in paths:
                try:
                    manifest = _read_json(directory / "manifest.json") if (directory / "manifest.json").exists() else {}
                    manifest.update({"status": "failed", "success": False,
                                     "failure": {"type": type(error).__name__, "reason": str(error)}})
                    _write_json(directory / "manifest.json", manifest, overwrite=True)
                except Exception as persistence_error:  # noqa: BLE001 - preserve the original failure
                    error.add_note(f"failure manifest could not be persisted: {persistence_error}")
                    # A missing final seal is deliberately never accepted by new readers.
                    try:
                        write_json(directory / "EXECUTION_FAILED.json",
                                   {"status": "failed", "type": type(error).__name__, "reason": str(error)})
                    except Exception as marker_error:  # noqa: BLE001 - preserve the original failure
                        error.add_note(f"failure marker could not be persisted: {marker_error}")
            raise


def _execute_experiment(config: ExperimentConfig, *, project_root: Path | None = None, replay: bool = False) -> BaselineRunResult:
    started_perf = time.perf_counter()
    root = (project_root or Path.cwd()).resolve()
    if config.generation.objective != "data_emulation":
        raise ValueError("M1 execution supports objective=data_emulation only; minority_augmentation is planned")
    registry = DatasetRegistry(project_root=root)
    spec = registry.get(config.dataset.dataset_id)
    raw_source_sha256 = file_hash(registry.resolve_path(spec))
    dataset = load_dataset(spec, registry)
    if raw_source_sha256 != file_hash(dataset.path):
        raise ValueError("dataset source provenance changed during load")
    split = make_split(dataset, config.dataset.root_seed)
    profile = build_profile(
        dataset, split, reference_example_count=config.dataset.reference_example_count,
        reference_examples_per_class=config.dataset.reference_examples_per_class,
        seed=config.dataset.root_seed, enabled=config.dataset.reference_examples_enabled,
    )
    generation_prompt = load_prompt("generation", config.generation.prompt_version, root)
    judge_prompt = load_prompt("judge", config.judge.prompt_version, root)
    plan = _generation_plan(config, profile, generation_prompt.sha256)
    _validate_upstream_context(config, generation_prompt.text, judge_prompt.text, replay=replay)
    if not replay:
        _require_real_provider(config)
    run_id = config.run_id or f"{config.experiment_name}-{uuid4().hex}"
    artifact_root = config.artifact_root
    if not artifact_root.is_absolute():
        artifact_root = (project_root or Path.cwd()).absolute() / artifact_root
    # Reject protected outputs before provider construction, without creating parents.
    # Reservation rechecks under the storage lock before any directory is installed.
    assert_writable(artifact_root / "runs" / run_id / "manifest.json")
    # Validate both independently selectable providers before reserving an artifact directory.
    generator = _provider(config.generator, root, replay)
    judge_provider = _provider(config.judge.provider, root, False)
    scientific = scientific_specification(config, root, replay=replay, dataset=dataset, split=split, profile=profile,
                                          prompt_hashes={"generation": generation_prompt.sha256, "judge": judge_prompt.sha256},
                                          raw_source_sha256=raw_source_sha256,
                                          provider_sources={name: provider.fixture_sha256 for name, provider in
                                              (("generator", generator), ("judge", judge_provider))
                                              if isinstance(provider, ReplayProvider)})
    run_dir = create_run_dir(artifact_root / "runs", run_id, exist_ok=False).resolve()
    own_run(run_dir)
    generator = DurableProvider(generator, run_dir, "generation", provider_identity=scientific["specification"]["providers"]["generator"], specification_fingerprint=scientific["fingerprint"])
    judge_provider = DurableProvider(judge_provider, run_dir, "judge", provider_identity=scientific["specification"]["providers"]["judge"], specification_fingerprint=scientific["fingerprint"])
    _write_json(run_dir / "scientific_specification.json", scientific)
    write_text(run_dir / "prompts/generation.txt", generation_prompt.text)
    write_text(run_dir / "prompts/judge.txt", judge_prompt.text)
    _write_json(run_dir / "manifest.json", {
        "schema_version": "m1-run-v2", "execution_id": run_id, "artifact_binding_version": BINDING_VERSION,
        "specification_fingerprint": scientific["fingerprint"], "boundary_version": "m1-train-boundary-v1",
        "environment": environment_snapshot(), "run_id": run_id, "experiment_name": config.experiment_name,
        "status": "running", "started_at": datetime.now(UTC).isoformat(), "root_seed": config.dataset.root_seed,
        "dataset_id": spec.dataset_id, "dataset_fingerprint": dataset.fingerprint, "config_hash": config.canonical_hash(),
        "split_fingerprint": split.to_dict()["split_fingerprint"],
        "generator_model": config.generator.model,
        "judge_model": config.judge.provider.model,
        "generator_endpoint": _sanitized_endpoint(config.generator.base_url),
        "judge_endpoint": _sanitized_endpoint(config.judge.provider.base_url),
        "generator_judge_same_model": config.generator_judge_same_model,
        "generation_transport_version": config.generation.transport_version,
        "generation_response_format": config.generation.response_format,
        "generation_reasoning_effort": config.generation.reasoning_effort,
        "generation_max_tokens": config.generation.max_tokens,
        "generation_timeout_seconds": config.generator.timeout_seconds,
        "correlated_error_self_evaluation_bias": (
            "generator and judge share one model; scores may inherit correlated errors and self-evaluation bias"
            if config.generator_judge_same_model else None
        ),
        "class_quotas": {quota.label: quota.count for quota in plan.class_quotas},
        "replay": replay, "no_test_leakage": True, "python_version": sys.version.split()[0],
        "platform": platform.platform(), "git_commit": _git_commit(root), "git_dirty": _git_dirty(root),
    })
    _write_yaml(run_dir / "resolved_config.yaml", config.model_dump(mode="json"))
    _write_json(run_dir / "dataset" / "split_manifest.json", split.to_dict())
    # Local evaluation provenance only: never part of TRAIN context or provider requests.
    # Preserve the exact normalization serialization used by the dataset fingerprint.
    write_text(run_dir / "dataset/evaluation_population.json", dataset.frame.to_json(
        orient="split", date_format="iso", default_handler=str,
    ))
    _write_json(run_dir / "dataset" / "profile.json", profile.model_dump(mode="json"))
    write_text(run_dir / "dataset/profile_source.json", profile.model_dump_json())
    _write_json(run_dir / "generation_plan.json", plan.model_dump(mode="json"))
    # Resolve + assert the deterministic unique per-batch provider seeds before
    # any provider call (M1.4 seed-confound guard, M1.5 §5).
    seed_plan = _generation_seed_plan(config, plan)
    _write_json(run_dir / "generation_seed_plan.json", seed_plan)
    manifest = _read_json(run_dir / "manifest.json")
    manifest["seed_provenance"] = seed_provenance(config, split, seed_plan)
    _write_json(run_dir / "manifest.json", manifest, overwrite=True)

    smoke_trace: ProviderCallTrace | None = None
    smoke_report: dict[str, Any] = {"status": "not_run", "reason": "offline replay" if replay else None}
    if not replay:
        try:
            generator.evidence_purpose = "generation_smoke"
            smoke_trace, smoke_report = _provider_smoke(generator, run_dir.name, config, plan)
            generator.evidence_purpose = "generation"
            _write_jsonl(run_dir / "provider_calls.jsonl", [smoke_trace])
            _write_json(run_dir / "provider_smoke.json", smoke_report)
            if smoke_report.get("status") != "ok":
                raise RuntimeError(str(smoke_report.get("error", "smoke response failed validation")))
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            smoke_report = {**smoke_report, "status": "failed", "error": str(error), "call_count": 1}
            _write_json(run_dir / "provider_smoke.json", smoke_report, overwrite=True)
            manifest = _read_json(run_dir / "manifest.json")
            manifest.update({"status": "failed", "failure": "provider_smoke", "provider_call_count": 1})
            _write_json(run_dir / "manifest.json", manifest, overwrite=True)
            raise RuntimeError(f"Provider smoke call failed; no pilot generation was attempted: {error}") from error

    upstream = TrainingContext.from_profile(profile)
    raw_candidates, traces, parse_failures, requested_calls = _generate_pool(config, run_id, plan, upstream, generation_prompt.text, generator, seed_plan)
    _write_jsonl(run_dir / "provider_calls.jsonl", traces)
    _write_jsonl(run_dir / "generation_failures.jsonl", parse_failures)
    _write_jsonl(run_dir / "candidates_raw.jsonl", raw_candidates)

    train = dataset.frame.loc[list(split.train_indices)].copy()

    def evaluate(synthetic: pd.DataFrame) -> tuple[dict[str, Any], dict[str, Any]]:
        real_test = dataset.frame.loc[list(split.test_indices)]
        return (intrinsic_metrics(train, synthetic, spec),
                utility_metrics(train, real_test, synthetic, spec, seed=config.dataset.root_seed, classifiers=config.metrics.classifiers))

    b1 = _run_b1(raw_candidates, train, spec, config, run_dir, evaluate)
    b2 = _run_b2(raw_candidates, train, spec, upstream, config, run_dir, evaluate)
    b3 = _run_b3(raw_candidates, train, spec, upstream, config, judge_prompt.text, judge_prompt.sha256, judge_prompt.version, run_dir, judge_provider, evaluate)
    judge_calls = b3["judge_calls"]
    comparison = _comparison(
        config, plan, raw_candidates, parse_failures, traces, requested_calls, judge_calls, b1, b2, b3,
        spec=spec, smoke_report=smoke_report, split_fingerprint=split.to_dict()["split_fingerprint"],
        wall_time_ms=(time.perf_counter() - started_perf) * 1000,
    )
    comparison["schema_version"] = "m1-comparison-v2"
    comparison["run_id"] = run_id
    comparison["execution_id"] = run_id
    comparison["dataset_fingerprint"] = dataset.fingerprint
    comparison["split_fingerprint"] = split.to_dict()["split_fingerprint"]
    comparison["configured_classifiers"] = list(config.metrics.classifiers)
    comparison["configured_results"] = scientific["specification"]["evaluation"]["result_families"]
    comparison["specification_fingerprint"] = scientific["fingerprint"]
    comparison["generation_accounting"] = {
        "requested": plan.requested_count, "returned_parseable": len(raw_candidates),
        "status": "exact" if len(raw_candidates) == plan.requested_count else "overproduction" if len(raw_candidates) > plan.requested_count else "shortfall"}
    comparison["outcome"] = execution_outcome(comparison).model_dump(mode="json")
    comparison["completed_at"] = datetime.now(UTC).isoformat()
    validate_comparison(comparison)
    binding_fingerprint = write_execution_bindings(run_dir, comparison, scientific)
    manifest = _read_json(run_dir / "manifest.json")
    manifest["execution_binding_fingerprint"] = binding_fingerprint
    _write_json(run_dir / "manifest.json", manifest, overwrite=True)
    _write_json(run_dir / "comparison.json", comparison)
    export_human_review(run_dir)
    export_disagreements(run_dir)
    _write_json(run_dir / "machine_failure_report.json", machine_failure_report(comparison))
    manifest = _read_json(run_dir / "manifest.json")
    manifest.update({"status": "finalized", "success": comparison["outcome"]["success"], "outcome": comparison["outcome"], "completed_at": comparison["completed_at"], "provider_call_count": requested_calls + judge_calls + (1 if smoke_trace else 0)})
    _write_json(run_dir / "manifest.json", manifest, overwrite=True)
    seal_bundle(run_dir)
    return BaselineRunResult(run_id, run_dir, comparison)



def _validate_upstream_context(config: ExperimentConfig, prompt: str, judge_prompt: str, *, replay: bool) -> None:
    """Boundary v1: reject unsafe fresh protocols without modifying their templates."""
    recorded_only = replay and config.judge.provider.kind in {"replay", "fixture"}
    fields = {field for _, field, _, _ in Formatter().parse(prompt) if field}
    allowed = {"generation_context_json", "class_condition", "requested_count", "reference_examples"}
    judge_fields = {field for _, field, _, _ in Formatter().parse(judge_prompt) if field}
    if not recorded_only and (not fields <= allowed or not judge_fields <= {"profile_json", "candidate_json"} or config.generation.transport_version != "v2"):
        raise ValueError("TRAIN-only context boundary v1 rejects this fresh generation/judge context")


def _require_real_provider(config: ExperimentConfig) -> None:
    """Stop at the provider gate before constructing or calling a real adapter."""

    checks = (("generator", config.generator), ("judge", config.judge.provider))
    failures: list[tuple[str, str]] = []
    for role, provider in checks:
        readiness = provider_readiness(provider)
        if not readiness.ready:
            failures.append((role, readiness.reason))
    if failures:
        detail = "; ".join(f"{role}: {reason}" for role, reason in failures)
        raise RuntimeError(
            "Provider gate: no provider call was made. "
            f"{detail}. Configure the exact generator/judge base_url, model, and API key env, "
            f"then run: rcqasyn baselines run --config configs/experiments/pilot/{config.dataset.dataset_id}.yaml"
        )


def _provider_smoke(provider: Any, run_id: str, config: ExperimentConfig, plan: GenerationPlan) -> tuple[ProviderCallTrace, dict[str, Any]]:
    """Make one bounded, parse-checked provider call before pilot generation."""

    prompt = 'Return exactly this JSON object and no other text: {"ok":true}'
    response_format = {"type": config.generation.response_format} if config.generation.response_format else None
    response = provider.call(
        role="generation",
        prompt=prompt,
        request_index=0,
        temperature=0.0,
        seed=config.generation.provider_seed,
        max_tokens=min(config.generation.max_tokens, 64),
        response_format=response_format,
        reasoning_effort=config.generation.reasoning_effort,
    )
    trace = _trace(
        run_id,
        "generation_smoke",
        response,
        config.generation.prompt_version,
        plan.prompt_hash,
        None,
        config.generation.provider_seed,
        prompt=prompt,
        temperature=0.0,
        max_tokens=min(config.generation.max_tokens, 64),
        response_format=response_format,
        reasoning_effort=config.generation.reasoning_effort,
        transport_version=f"{config.generation.transport_version}-smoke",
    )
    usage = {
        "call_count": 1,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "total_tokens": response.total_tokens,
        "latency_ms": response.latency_ms,
        "cost_usd": response.cost_usd,
    }
    try:
        parsed = json.loads(response.response)
    except json.JSONDecodeError as error:
        return trace, {"status": "failed", "parse": "invalid_json", "error": f"smoke response was not valid JSON: {error}", **usage}
    if not isinstance(parsed, dict) or parsed.get("ok") is not True:
        return trace, {"status": "failed", "parse": "unexpected_json", "error": "smoke response did not contain the required {\"ok\":true} object", **usage}
    return trace, {"status": "ok", "parse": "json_object_ok", **usage}


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
    reference_policy = getattr(profile, "reference_policy", "per_class" if config.dataset.reference_examples_per_class is not None else "total_count")
    return GenerationPlan(
        plan_id=f"plan-{config.canonical_hash()[:16]}", requested_count=config.generation.requested_count,
        requested_class=next(iter(quotas)) if len(quotas) == 1 else None,
        dataset_id=profile.dataset_id, objective=config.generation.objective, class_strategy=config.generation.class_strategy,
        class_quotas=tuple(ClassQuota(label=label, count=count) for label, count in sorted(quotas.items())),
        reference_example_count=config.dataset.reference_example_count,
        reference_examples_per_class=config.dataset.reference_examples_per_class,
        reference_examples_enabled=config.dataset.reference_examples_enabled, source_profile_id=profile.profile_id,
        reference_policy=reference_policy,
        source_profile_hash=sha256_text(profile.model_dump_json()), generator_id=config.generation.generator_id,
        generator_version=config.generation.generator_version,
        generator_config={"generation": config.generation.model_dump(mode="json"), "provider": config.generator.model_dump(mode="json"), "dataset": {"reference_policy": reference_policy, "reference_example_count": config.dataset.reference_example_count, "reference_examples_per_class": config.dataset.reference_examples_per_class, "reference_examples_enabled": config.dataset.reference_examples_enabled}},
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


def _generation_seed_plan(config: ExperimentConfig, plan: GenerationPlan) -> dict[str, Any]:
    """Resolve the deterministic per-batch provider seed for every generation call.

    Asserts the M1.4 seed-confound correction still holds: distinct
    ``(dataset_id, requested_class, batch_index)`` tuples must map to distinct
    provider seeds.  A collision raises before any provider call is made.
    """

    entries: list[dict[str, Any]] = []
    seen: dict[int, tuple[str, str, int]] = {}
    for quota in plan.class_quotas:
        remaining = quota.count
        batch_index = 0
        while remaining > 0:
            count = min(plan.batch_size, remaining)
            key = (plan.dataset_id, str(quota.label), batch_index)
            seed = (
                generation_provider_seed(
                    config.dataset.root_seed, plan.dataset_id, str(quota.label), batch_index,
                    base_seed=config.generation.provider_seed,
                )
                if config.generation.provider_seed is not None
                else None
            )
            if seed is not None:
                if seed in seen and seen[seed] != key:
                    raise RuntimeError(
                        "generation seed confound: distinct "
                        f"{key} and {seen[seed]} both derived provider seed {seed}"
                    )
                seen[seed] = key
            entries.append({
                "root_seed": config.dataset.root_seed, "dataset_id": plan.dataset_id,
                "requested_class": str(quota.label), "batch_index": batch_index,
                "requested_count": count, "provider_seed": seed,
            })
            remaining -= count
            batch_index += 1
    distinct_tuples = {(e["dataset_id"], e["requested_class"], e["batch_index"]) for e in entries}
    distinct_seeds = {e["provider_seed"] for e in entries if e["provider_seed"] is not None}
    return {
        "schema_version": "m1-generation-seed-plan-v1",
        "base_provider_seed": config.generation.provider_seed,
        "derivation": "generation_provider_seed(root_seed, dataset_id, requested_class, batch_index, base_seed)",
        "calls": entries,
        "distinct_call_tuples": len(distinct_tuples),
        "distinct_provider_seeds": len(distinct_seeds),
        "all_seeds_unique": None if config.generation.provider_seed is None else len(distinct_seeds) == len(distinct_tuples),
    }


def _generate_pool(config: ExperimentConfig, run_id: str, plan: GenerationPlan, profile: Any, prompt_text: str, provider: Any, seed_plan: dict[str, Any] | None = None) -> tuple[list[CandidateRecord], list[ProviderCallTrace], list[ParseFailureEvent], int]:
    candidates: list[CandidateRecord] = []
    traces: list[ProviderCallTrace] = []
    failures: list[ParseFailureEvent] = []
    seed_by_key = {
        (entry["requested_class"], entry["batch_index"]): entry["provider_seed"]
        for entry in (seed_plan or _generation_seed_plan(config, plan))["calls"]
    }
    # (label, count, per-class batch index) so each batch gets a deterministic
    # unique provider seed rather than replaying one configured seed.
    requests: list[tuple[str, int, int]] = []
    for quota in plan.class_quotas:
        remaining = quota.count
        batch_index = 0
        while remaining > 0:
            count = min(plan.batch_size, remaining)
            requests.append((quota.label, count, batch_index))
            remaining -= count
            batch_index += 1
    requested_calls = len(requests)
    generation_context_json = json.dumps(profile.to_generation_context(), sort_keys=True) if hasattr(profile, "to_generation_context") else json.dumps(profile.model_dump(mode="json"), sort_keys=True)
    response_format = {"type": config.generation.response_format} if config.generation.response_format else None
    for call_index, (requested_class, count, batch_index) in enumerate(requests):
        batch_seed = seed_by_key[(requested_class, batch_index)]
        prompt = "[recorded-response replay; no upstream prompt executed]" if (isinstance(provider, ReplayProvider) or getattr(provider, "recorded_response_only", False)) else prompt_text.format(
            profile_json=json.dumps(profile.model_dump(mode="json"), sort_keys=True),
            generation_context_json=generation_context_json, class_condition=requested_class,
            requested_count=count, reference_examples=json.dumps(profile.reference_examples, sort_keys=True),
        )
        try:
            response = provider.call(
                role="generation", prompt=prompt, request_index=call_index,
                temperature=config.generation.temperature, seed=batch_seed,
                max_tokens=config.generation.max_tokens, response_format=response_format,
                reasoning_effort=config.generation.reasoning_effort,
            )
        except DurableCallFailure as error:
            failures.append(ParseFailureEvent(
                event_id=f"provider-generation-{call_index}", run_id=run_id, call_id=error.attempt_id,
                parser_version="provider-v1", error=f"provider failure: {error}", recoverable=False,
                created_at=datetime.now(UTC), metadata={"requested_class": requested_class, "requested_count": count,
                                                       "batch_index": batch_index, "provider_seed": batch_seed,
                                                       "temperature": config.generation.temperature, "max_tokens": config.generation.max_tokens,
                                                       "transport_version": config.generation.transport_version,
                                                       "response_format": config.generation.response_format,
                                                       "reasoning_effort": config.generation.reasoning_effort},
            ))
            continue
        call_id = response.call_id or f"generation-{call_index}"
        traces.append(_trace(
            run_id, "generation", response, config.generation.prompt_version, plan.prompt_hash, count,
            batch_seed, requested_class, prompt=prompt,
            temperature=config.generation.temperature, max_tokens=config.generation.max_tokens,
            response_format=response_format, reasoning_effort=config.generation.reasoning_effort,
            transport_version=config.generation.transport_version, batch_index=batch_index,
        ))
        parsed = parse_generation_response(
            response.response, run_id=run_id, call_id=call_id, generator_id=plan.generator_id,
            generator_version=plan.generator_version, prompt_version=plan.prompt_version,
            seed=batch_seed, requested_class=requested_class,
            requested_count=count, transport_version=config.generation.transport_version,
        )
        candidates.extend(parsed.candidates)
        failures.extend(parsed.failures)
    return candidates, traces, failures, requested_calls


def _trace(run_id: str, role: str, response: ProviderResponse, prompt_version: str | None, prompt_hash: str | None, requested_count: int | None, seed: int | None, requested_class: str | None = None, *, prompt: str | None = None, temperature: float | None = None, max_tokens: int | None = None, response_format: dict[str, Any] | None = None, reasoning_effort: str | None = None, transport_version: str | None = None, batch_index: int | None = None) -> ProviderCallTrace:
    return ProviderCallTrace(
        metadata={"batch_index": batch_index, "external_provider_call_id": response.external_call_id},
        call_id=response.call_id or f"call-{sha256_text(response.response)[:12]}", run_id=run_id, role=role,
        provider=response.provider, model=response.model, endpoint=response.endpoint, prompt_version=prompt_version,
        prompt_hash=prompt_hash, prompt=prompt, raw_response=response.response,
        requested_class=requested_class, requested_count=requested_count, max_tokens=max_tokens,
        temperature=temperature, seed=seed, input_tokens=response.input_tokens,
        output_tokens=response.output_tokens, total_tokens=response.total_tokens, cost_usd=response.cost_usd,
        latency_ms=response.latency_ms, finish_reason=response.finish_reason,
        response_format=response.response_format or response_format or {},
        reasoning_effort=response.reasoning_effort or reasoning_effort,
        reasoning_fields_present=response.reasoning_fields_present,
        transport_version=transport_version,
        prompt_chars=len(prompt) if prompt is not None else None,
        prompt_tokens_approx=((len(prompt) + 3) // 4) if prompt is not None else None,
        created_at=response.created_at, replay_source_id=response.replay_source_id,
    )


def _run_b1(candidates: list[CandidateRecord], train: pd.DataFrame, spec: Any, config: ExperimentConfig, run_dir: Path, evaluate: Callable[[pd.DataFrame], tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    accepted = list(candidates)
    result = _persist_baseline("b1", accepted, candidates, train, spec, config, run_dir, evaluate, decisions=[BaselineDecision(candidate_id=c.record_id, baseline="b1", accepted=True, reason="all parseable candidates accepted", created_at=datetime.now(UTC)) for c in candidates])
    result["failure_counts"] = {"duplicate": _duplicate_count(candidates)}
    return result


def _run_b2(candidates: list[CandidateRecord], train: pd.DataFrame, spec: Any, profile: Any, config: ExperimentConfig, run_dir: Path, evaluate: Callable[[pd.DataFrame], tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    suite = ValidatorSuite(spec, profile, range_severity=config.baselines.range_severity)
    accepted: list[CandidateRecord] = []
    all_evidence: list[Any] = []
    decisions: list[BaselineDecision] = []
    seen: set[str] = set()
    first_seen: dict[str, str] = {}
    for candidate in candidates:
        requested_class = candidate.metadata.get("requested_class")
        expected_class = requested_class if isinstance(requested_class, str) else None
        evidence = suite.validate(candidate, expected_class=expected_class)
        all_evidence.extend(evidence)
        duplicate = _canonical_hash(candidate) in seen
        seen.add(_canonical_hash(candidate))
        reject = rejects(evidence, frozenset(config.baselines.reject_severities)) or duplicate
        if duplicate:
            duplicate_evidence = Evidence(
                evidence_id=f"b2-duplicate-{candidate.record_id}", candidate_id=candidate.record_id,
                candidate_version=candidate.version, validator_id="b2-exact-duplicate", validator_version="1",
                dimension=QualityDimension.DIVERSITY, verdict=Verdict.FAIL, severity=Severity.INFO,
                message="existing B2 duplicate rule rejected an exact repeated candidate",
                created_at=datetime.now(UTC),
                metadata={"scope": "dataset_redundancy", "decision_provenance": True,
                          "first_seen_candidate_id": first_seen[_canonical_hash(candidate)]})
            evidence = (*evidence, duplicate_evidence)
            all_evidence.append(duplicate_evidence)
        first_seen.setdefault(_canonical_hash(candidate), candidate.record_id)
        if not reject:
            accepted.append(candidate)
        reason = "duplicate" if duplicate else "configured deterministic severity rejection" if reject else "all configured deterministic checks passed"
        decisions.append(BaselineDecision(candidate_id=candidate.record_id, baseline="b2", accepted=not reject, reason=reason, evidence_ids=tuple(item.evidence_id for item in evidence), created_at=datetime.now(UTC)))
    result = _persist_baseline("b2", accepted, candidates, train, spec, config, run_dir, evaluate, decisions=decisions, evidence=all_evidence)
    result["deterministic_rejections"] = sum(not decision.accepted for decision in decisions)
    missing_candidates = {item.candidate_id for item in all_evidence if item.metadata.get("missing_fields")}
    category_candidates = {item.candidate_id for item in all_evidence if item.validator_id == "categorical-domain" and item.verdict == Verdict.FAIL}
    target_candidates = {item.candidate_id for item in all_evidence if item.validator_id == "target-condition" and item.verdict == Verdict.FAIL}
    schema_candidates = {item.candidate_id for item in all_evidence if item.validator_id == "schema" and item.verdict == Verdict.FAIL}
    range_candidates = {item.candidate_id for item in all_evidence if item.validator_id == "observed-range" and item.verdict == Verdict.WARN}
    result["failure_counts"] = {
        "schema_failure": len(schema_candidates),
        "schema_failures": len(schema_candidates),
        "missing_field": len(missing_candidates),
        "category_invalid": len(category_candidates),
        "invalid_category": len(category_candidates),
        "target_wrong": len(target_candidates),
        "target_mismatch": len(target_candidates),
        "range_warning": len(range_candidates),
        "range_warnings": len(range_candidates),
        "duplicate": _duplicate_count(candidates),
        "b2_rejection": result["deterministic_rejections"],
        "b2_rejections": result["deterministic_rejections"],
        "deterministic_structural_rejection": result["deterministic_rejections"],
    }
    result["failure_record_ids"] = {
        "SCHEMA": sorted(schema_candidates),
        "MISSING_FIELD": sorted(missing_candidates),
        "INVALID_CATEGORY": sorted(category_candidates),
        "TARGET_MISMATCH": sorted(target_candidates),
        "OBSERVED_RANGE_WARNING": sorted(range_candidates),
        "B2_REJECTED": sorted(decision.candidate_id for decision in decisions if not decision.accepted),
    }
    result["deterministic_violations"] = len({item.candidate_id for item in all_evidence if item.verdict == Verdict.FAIL and item.validator_id != "b2-exact-duplicate"})
    result["deterministic_rejection_rate"] = result["deterministic_rejections"] / len(candidates) if candidates else None
    result["deterministic_violation_rate"] = result["deterministic_violations"] / len(candidates) if candidates else None
    return result


def _run_b3(candidates: list[CandidateRecord], train: pd.DataFrame, spec: Any, profile: Any, config: ExperimentConfig, judge_text: str, judge_hash: str, judge_version: str, run_dir: Path, provider: Any, evaluate: Callable[[pd.DataFrame], tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    judge = SingleLLMJudge(provider, threshold=config.judge.threshold, malformed_policy=config.judge.malformed_policy)
    accepted: list[CandidateRecord] = []
    decisions: list[BaselineDecision] = []
    results: list[JudgeResult] = []
    failures: list[ParseFailureEvent] = []
    traces: list[ProviderCallTrace] = []
    provider_failures = 0
    response_format = {"type": config.judge.response_format} if config.judge.response_format else None
    judge_profile = profile.to_generation_context() if config.generation.transport_version == "v2" and hasattr(profile, "to_generation_context") else profile.model_dump(mode="json")
    for index, candidate in enumerate(candidates):
        prompt = "[recorded-response replay; no upstream prompt executed]" if (isinstance(provider, ReplayProvider) or getattr(provider, "recorded_response_only", False)) else judge_text.format(profile_json=json.dumps(judge_profile, sort_keys=True), candidate_json=json.dumps(candidate.data, sort_keys=True))
        try:
            evaluation = judge.evaluate(
                prompt=prompt, run_id=run_dir.name, candidate_id=candidate.record_id,
                request_index=index, seed=config.generation.provider_seed, max_tokens=config.generation.max_tokens,
                response_format=response_format, reasoning_effort=config.judge.reasoning_effort,
            )
            response = evaluation.response
            call_id = response.call_id or f"judge-{index}"
            traces.append(_trace(
                run_dir.name, "judge", response, f"judge-{judge_version}", judge_hash, None,
                config.generation.provider_seed, prompt=prompt, temperature=0.0, max_tokens=config.generation.max_tokens,
                response_format=response_format, reasoning_effort=config.judge.reasoning_effort,
                transport_version="judge-v2" if response_format else "judge-v1",
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
        except DurableCallFailure as error:
            provider_failures += 1
            failures.append(ParseFailureEvent(event_id=f"judge-provider-{candidate.record_id}", run_id=run_dir.name, call_id=error.attempt_id, parser_version="provider-v1", error=f"judge provider failure: {error}", recoverable=False, created_at=datetime.now(UTC)))
            decisions.append(BaselineDecision(candidate_id=candidate.record_id, baseline="b3", accepted=False, reason="judge provider failure", created_at=datetime.now(UTC)))
    result = _persist_baseline("b3", accepted, candidates, train, spec, config, run_dir, evaluate, decisions=decisions, judge_results=results)
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
    result["failure_counts"] = {
        "judge_rejection": result["judge_rejections"],
        "judge_rejections": result["judge_rejections"],
        "judge_malformed": result["judge_malformed"],
        "judge_provider_failure": result["judge_provider_failures"],
        "duplicate": _duplicate_count(candidates),
    }
    malformed_ids = {
        failure.event_id.removeprefix("judge-parse-")
        for failure in failures if failure.parser_version == "judge-json-v1"
    }
    provider_ids = {
        failure.event_id.removeprefix("judge-provider-")
        for failure in failures if failure.parser_version == "provider-v1"
    }
    result["failure_record_ids"] = {
        "B3_REJECTED": sorted(
            decision.candidate_id for decision in decisions
            if not decision.accepted and decision.candidate_id not in malformed_ids and decision.candidate_id not in provider_ids
        ),
        "B3_MALFORMED": sorted(malformed_ids),
        "PROVIDER_ERROR": sorted(provider_ids),
    }
    return result


def _persist_baseline(name: str, accepted: list[CandidateRecord], all_candidates: list[CandidateRecord], train: pd.DataFrame, spec: Any, config: ExperimentConfig, run_dir: Path, evaluate: Callable[[pd.DataFrame], tuple[dict[str, Any], dict[str, Any]]], *, decisions: list[BaselineDecision], evidence: list[Any] | None = None, judge_results: list[JudgeResult] | None = None) -> dict[str, Any]:
    directory = run_dir / "baselines" / name
    _write_jsonl(directory / "candidates.jsonl", accepted)
    _write_jsonl(directory / "decisions.jsonl", decisions)
    if evidence is not None:
        _write_jsonl(directory / "evidence.jsonl", evidence)
    if judge_results is not None:
        _write_jsonl(directory / "judge_results.jsonl", judge_results)
    synthetic = pd.DataFrame([candidate.data for candidate in accepted], columns=[*spec.feature_columns, spec.target_column])
    intrinsic_issues: dict[str, str] = {}
    intrinsic, utility = evaluate(synthetic)
    intrinsic = finite_tree(intrinsic, issues=intrinsic_issues)
    utility = annotate_utility(utility, config.metrics.classifiers)
    if synthetic.empty:
        # Preserve every metric's null/empty detail while making the global
        # state explicit for report readers and downstream evaluability checks.
        intrinsic["status"] = "empty"
    intrinsic = annotate_intrinsic(intrinsic)
    _write_json(directory / "metrics.json", intrinsic)
    _write_json(directory / "classifier_metrics.json", utility)
    duplicate_hashes = [_canonical_hash(candidate) for candidate in all_candidates]
    duplicates = len(duplicate_hashes) - len(set(duplicate_hashes))
    duplicate_by_class = _duplicate_counts_by_class(all_candidates, spec.target_column)
    train_hashes = {
        _canonical_data_hash({column: row[column] for column in [*spec.feature_columns, spec.target_column]})
        for _, row in train[[*spec.feature_columns, spec.target_column]].iterrows()
    }
    train_match_ids = [candidate.record_id for candidate in all_candidates if _canonical_hash(candidate) in train_hashes]
    train_matches_by_class = _count_ids_by_class(all_candidates, train_match_ids, spec.target_column)
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
        "exact_duplicate_by_class": duplicate_by_class,
        "exact_train_match_count": len(train_match_ids),
        "exact_train_match_rate": len(train_match_ids) / raw_pool_count if raw_pool_count else None,
        "exact_train_match_by_class": train_matches_by_class,
        "exact_train_match_ids": train_match_ids,
        "exact_train_match_interpretation": "exact canonical equality with a TRAIN row only; no privacy claim",
        "accepted_record_ids": [candidate.record_id for candidate in accepted],
        "calls": 0,
        "cost_usd": None,
        "intrinsic": intrinsic, "intrinsic_metric_issues": intrinsic_issues,
        "utility": utility,
    }


def _comparison(config: ExperimentConfig, plan: GenerationPlan, candidates: list[CandidateRecord], failures: list[ParseFailureEvent], traces: list[ProviderCallTrace], requested_calls: int, judge_calls: int, b1: dict[str, Any], b2: dict[str, Any], b3: dict[str, Any], *, spec: Any | None = None, smoke_report: dict[str, Any] | None = None, split_fingerprint: str | None = None, wall_time_ms: float | None = None) -> dict[str, Any]:
    known_generation_input_tokens = _sum_nullable([trace.input_tokens for trace in traces]) if traces else None
    known_generation_output_tokens = _sum_nullable([trace.output_tokens for trace in traces]) if traces else None
    known_generation_total_tokens = _sum_nullable([trace.total_tokens for trace in traces]) if traces else None
    generation_usage_complete = requested_calls == len(traces) and all(
        value is not None for trace in traces for value in (trace.input_tokens, trace.output_tokens, trace.total_tokens)
    ) and (
        # v2 traces explicitly persist finish_reason, so do not present an
        # aggregate as complete when the provider envelope omitted it.  The
        # historical v1/replay contract predates that field and retains its
        # token aggregation semantics for backwards-compatible replays.
        config.generation.transport_version != "v2"
        or all(trace.finish_reason is not None for trace in traces)
    )
    generation_input_tokens = known_generation_input_tokens if generation_usage_complete else None
    generation_output_tokens = known_generation_output_tokens if generation_usage_complete else None
    generation_total_tokens = known_generation_total_tokens if generation_usage_complete else None
    judge_input_tokens = b3.get("judge_input_tokens")
    judge_output_tokens = b3.get("judge_output_tokens")
    judge_total_tokens = b3.get("judge_total_tokens")
    smoke_input_tokens = _nullable_number(smoke_report, "input_tokens")
    smoke_output_tokens = _nullable_number(smoke_report, "output_tokens")
    smoke_total_tokens = _nullable_number(smoke_report, "total_tokens")
    # No generation calls is a known zero contribution; an incomplete
    # generation run remains null so aggregate totals cannot imply complete
    # provider usage.
    generation_input_component = 0 if requested_calls == 0 else generation_input_tokens
    generation_output_component = 0 if requested_calls == 0 else generation_output_tokens
    generation_total_component = 0 if requested_calls == 0 else generation_total_tokens
    input_tokens = _sum_nullable([generation_input_component, judge_input_tokens, smoke_input_tokens])
    output_tokens = _sum_nullable([generation_output_component, judge_output_tokens, smoke_output_tokens])
    total_tokens = _sum_nullable([generation_total_component, judge_total_tokens, smoke_total_tokens])
    generation_recorded_latency = (
        0.0 if not traces and requested_calls == 0
        else sum(trace.latency_ms or 0.0 for trace in traces) if traces and all(trace.latency_ms is not None for trace in traces)
        else None
    )
    generation_latency = generation_recorded_latency if generation_usage_complete else None
    judge_latency = b3.get("judge_latency_ms")
    smoke_latency = _nullable_number(smoke_report, "latency_ms")
    latency_ms = _sum_float_nullable([generation_latency, judge_latency, smoke_latency])
    generation_cost = _sum_cost_nullable([trace.cost_usd for trace in traces]) if requested_calls == len(traces) else None
    judge_cost = b3.get("judge_cost_usd")
    smoke_cost = _nullable_number(smoke_report, "cost_usd")
    cost_usd = _sum_cost_nullable([0.0 if requested_calls == 0 else generation_cost, judge_cost, smoke_cost])
    failure_aggregation = _aggregate_failures(failures, b1, b2, b3, candidates=candidates, plan=plan, spec=spec)
    minority = _minority_analysis(spec, plan, candidates, b1, b2, b3) if spec is not None else {}
    endpoint = _sanitized_endpoint(config.generator.base_url)
    judge_endpoint = _sanitized_endpoint(config.judge.provider.base_url)
    same_model_note = (
        "generator and judge share one model; scores may inherit correlated errors and self-evaluation bias"
        if config.generator_judge_same_model else None
    )
    baseline_comparison = _baseline_comparison(
        config, b1, b2, b3,
        generation_attempted_calls=requested_calls,
        generation_successful_calls=len(traces),
        generation_known_input_tokens=known_generation_input_tokens,
        generation_known_output_tokens=known_generation_output_tokens,
        generation_known_total_tokens=known_generation_total_tokens,
        generation_usage_complete=generation_usage_complete,
        generation_recorded_latency_ms=generation_recorded_latency,
        judge_attempted_calls=int(b3.get("judge_attempted_calls", judge_calls)),
        judge_successful_calls=int(b3.get("judge_successful_calls", judge_calls)),
        judge_input_tokens=judge_input_tokens,
        judge_output_tokens=judge_output_tokens,
        judge_total_tokens=judge_total_tokens,
        judge_recorded_latency_ms=judge_latency,
        smoke_report=smoke_report,
    )
    failure_categories = [
        "PARSE", "SCHEMA", "MISSING_FIELD", "INVALID_CATEGORY", "TARGET_MISMATCH",
        "OBSERVED_RANGE_WARNING", "EXACT_DUPLICATE", "B2_REJECTED", "B3_REJECTED",
        "B3_MALFORMED", "PROVIDER_ERROR",
    ]
    return {
        "schema_version": "m1-comparison-v1", "dataset_id": plan.dataset_id, "requested": plan.requested_count, "experiment_requested": plan.requested_count,
        "generation_attempted_calls": requested_calls, "generation_successful_calls": len(traces),
        "generation_calls": requested_calls, "judge_attempted_calls": int(b3.get("judge_attempted_calls", judge_calls)),
        "judge_successful_calls": int(b3.get("judge_successful_calls", judge_calls)), "judge_calls": judge_calls,
        "judge_provider_failures": int(b3.get("judge_provider_failures", 0)),
        "provider_calls": requested_calls + int(b3.get("judge_attempted_calls", judge_calls)) + (1 if smoke_report and smoke_report.get("status") == "ok" else 0),
        "provider_smoke": smoke_report or {"status": "not_run"},
        "raw_pool_count": len(candidates), "parseable_record_count": len(candidates),
        "parse_success": len(candidates), "parse_success_rate": len(candidates) / plan.requested_count if plan.requested_count else None,
        "parse_failures": len(failures), "parse_failure_event_count": len(failures),
        "parse_affected_requested_record_count": failure_aggregation["global"]["PARSE"]["unique_affected_record_count"],
        "unparseable_requested_record_count": failure_aggregation["unparseable_requested_record_count"],
        "unparseable_rate": failure_aggregation["unparseable_rate"],
        "failure_categories": failure_categories,
        "failure_aggregation": failure_aggregation, "baselines": {"b1": b1, "b2": b2, "b3": b3},
        "deterministic_violation_rate": b2.get("deterministic_violation_rate"),
        "deterministic_rejection_rate": b2.get("deterministic_rejection_rate"),
        "judge_rejection_rate": b3.get("judge_rejection_rate"),
        "generation_input_tokens": generation_input_tokens, "generation_output_tokens": generation_output_tokens,
        "generation_total_tokens": generation_total_tokens, "judge_input_tokens": judge_input_tokens,
        "judge_output_tokens": judge_output_tokens, "judge_total_tokens": judge_total_tokens,
        "generation_successful_input_tokens": known_generation_input_tokens,
        "generation_successful_output_tokens": known_generation_output_tokens,
        "generation_successful_total_tokens": known_generation_total_tokens,
        "generation_usage_complete": generation_usage_complete,
        "generation_recorded_latency_ms": generation_recorded_latency,
        "generation_latency_ms": generation_latency, "judge_latency_ms": judge_latency,
        "generation_cost_usd": generation_cost, "judge_cost_usd": judge_cost,
        "smoke_input_tokens": smoke_input_tokens, "smoke_output_tokens": smoke_output_tokens,
        "smoke_total_tokens": smoke_total_tokens, "smoke_latency_ms": smoke_latency,
        "smoke_cost_usd": smoke_cost,
        "input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": total_tokens,
        "latency_ms": latency_ms, "cost_usd": cost_usd,
        "minority_analysis": minority,
        "baseline_comparison": baseline_comparison,
        "metadata": {
            "generator_model": config.generator.model,
            "judge_model": config.judge.provider.model,
            "generator_endpoint": endpoint,
            "judge_endpoint": judge_endpoint,
            "split_fingerprint": split_fingerprint,
            "class_quotas": {quota.label: quota.count for quota in getattr(plan, "class_quotas", ())},
            "generator_judge_same_model": config.generator_judge_same_model,
            "generation_transport_version": config.generation.transport_version,
            "generation_response_format": config.generation.response_format,
            "generation_reasoning_effort": config.generation.reasoning_effort,
            "generation_max_tokens": config.generation.max_tokens,
            "generation_timeout_seconds": config.generator.timeout_seconds,
            "correlated_error_self_evaluation_bias": same_model_note,
            "cost_policy": "null unless provider reports meaningful monetary cost",
            "exact_train_match_policy": "exact canonical equality only; no privacy claim",
        },
        "recorded_latency_ms": latency_ms,
        "wall_time_ms": wall_time_ms,
        "no_significance_claim": True, "policy": {"b1": "accept all parseable", "b2": "configured deterministic severity filtering", "b3": "one judge + static threshold + no calibration"},
    }


def _baseline_comparison(
    config: ExperimentConfig, b1: dict[str, Any], b2: dict[str, Any], b3: dict[str, Any], *,
    generation_attempted_calls: int | None = None,
    generation_successful_calls: int | None = None,
    generation_known_input_tokens: int | None = None,
    generation_known_output_tokens: int | None = None,
    generation_known_total_tokens: int | None = None,
    generation_usage_complete: bool | None = None,
    generation_recorded_latency_ms: float | None = None,
    judge_attempted_calls: int | None = None,
    judge_successful_calls: int | None = None,
    judge_input_tokens: int | None = None,
    judge_output_tokens: int | None = None,
    judge_total_tokens: int | None = None,
    judge_recorded_latency_ms: float | None = None,
    smoke_report: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build comparable baseline rows without filling unavailable metrics."""

    def metric_average_wasserstein(summary: dict[str, Any]) -> dict[str, Any]:
        values = [
            float(metric.get("wasserstein"))
            for metric in summary.get("intrinsic", {}).get("numeric", {}).values()
            if isinstance(metric, dict) and isinstance(metric.get("wasserstein"), (int, float))
        ]
        return {
            "value": sum(values) / len(values) if values else None,
            "status": "ok" if values else "not_evaluable",
            "observed_count": len(values),
        }

    def metric_correlation_error(summary: dict[str, Any]) -> dict[str, Any]:
        correlations = summary.get("intrinsic", {}).get("correlations", {})
        result: dict[str, Any] = {}
        values: list[float] = []
        for name in ("pearson", "spearman"):
            metric = correlations.get(name, {}) if isinstance(correlations, dict) else {}
            value = metric.get("mean_abs_error") if isinstance(metric, dict) else None
            result[name] = {"value": value, "status": "ok" if isinstance(value, (int, float)) else "not_evaluable"}
            if isinstance(value, (int, float)):
                values.append(float(value))
        result["value"] = sum(values) / len(values) if values else None
        result["status"] = "ok" if values else "not_evaluable"
        return result

    rows: list[dict[str, Any]] = []
    for name, summary in (("b1", b1), ("b2", b2), ("b3", b3)):
        requested = summary.get("requested", config.generation.requested_count)
        raw_pool_count = summary.get("raw_pool_count")
        parse_success_rate = summary.get("acceptance_rate")
        if isinstance(requested, (int, float)) and isinstance(raw_pool_count, (int, float)):
            parse_success_rate = float(raw_pool_count) / float(requested) if requested else None
        parse_validity = {
            "status": "ok" if raw_pool_count else "not_evaluable",
            "requested": requested,
            "parseable": raw_pool_count,
            "parse_failure_count": (int(requested) - int(raw_pool_count)) if isinstance(requested, int) and isinstance(raw_pool_count, int) else None,
            "parse_success_rate": parse_success_rate,
        }
        is_b3 = name == "b3"
        generation_calls = {
            "attempted": generation_attempted_calls,
            "successful": generation_successful_calls,
            "shared_generation_pool": True,
            "recorded_latency_ms": generation_recorded_latency_ms,
        }
        judge_calls = {
            "attempted": judge_attempted_calls if is_b3 else 0,
            "successful": judge_successful_calls if is_b3 else 0,
            "recorded_latency_ms": judge_recorded_latency_ms if is_b3 else None,
            "applicable": is_b3,
        }
        tokens = {
            "generation_input_tokens": generation_known_input_tokens,
            "generation_output_tokens": generation_known_output_tokens,
            "generation_total_tokens": generation_known_total_tokens,
            "generation_usage_complete": generation_usage_complete,
            "judge_input_tokens": judge_input_tokens if is_b3 else None,
            "judge_output_tokens": judge_output_tokens if is_b3 else None,
            "judge_total_tokens": judge_total_tokens if is_b3 else None,
            "judge_usage_complete": (
                judge_attempted_calls == judge_successful_calls
                and judge_input_tokens is not None
                and judge_output_tokens is not None
                and judge_total_tokens is not None
            ) if is_b3 and judge_attempted_calls is not None and judge_successful_calls is not None else False,
            "status": "complete" if generation_usage_complete else "known_successful_calls_only",
        }
        rows.append({
            "baseline": name,
            "requested": requested,
            "raw_pool_count": raw_pool_count,
            "accepted": summary.get("accepted"),
            "acceptance_rate": summary.get("acceptance_rate"),
            "exact_duplicate_count": summary.get("exact_duplicate_count"),
            "exact_train_match_count": summary.get("exact_train_match_count"),
            "parse_validity": parse_validity,
            "average_wasserstein": metric_average_wasserstein(summary),
            "correlation_error": metric_correlation_error(summary),
            "calls": {"generation": generation_calls, "judge": judge_calls},
            "tokens": tokens,
            "smoke": {
                "status": "separate",
                "call_count": _nullable_number(smoke_report, "call_count") if smoke_report else None,
                "input_tokens": _nullable_number(smoke_report, "input_tokens"),
                "output_tokens": _nullable_number(smoke_report, "output_tokens"),
                "total_tokens": _nullable_number(smoke_report, "total_tokens"),
                "latency_ms": _nullable_number(smoke_report, "latency_ms"),
                "cost_usd": _nullable_number(smoke_report, "cost_usd"),
            },
            "trtr": summary.get("utility", {}).get("TRTR", {}),
            "tstr": summary.get("utility", {}).get("TSTR", {}),
        })
    return rows


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


def _sum_float_nullable(values: list[object]) -> float | None:
    if any(value is not None and not isinstance(value, (int, float)) for value in values):
        return None
    if any(value is None for value in values):
        return None
    return float(sum(float(value) for value in values))


def _nullable_number(mapping: dict[str, Any] | None, key: str) -> int | float | None:
    if not mapping or mapping.get("status") == "not_run":
        return None
    value = mapping.get(key)
    return value if value is None or isinstance(value, (int, float)) else None


def _canonical_hash(candidate: CandidateRecord) -> str:
    return _canonical_data_hash(candidate.data)


def _canonical_data_hash(data: dict[str, Any]) -> str:
    normalized = {
        str(key): _json_scalar(value)
        for key, value in data.items()
    }
    return sha256_text(json.dumps(normalized, sort_keys=True, separators=(",", ":")))


def _json_scalar(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_scalar(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_scalar(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        if value is None or isinstance(value, (str, bool)):
            return value
        return None if pd.isna(value) else value
    missing = pd.isna(value)
    if isinstance(missing, bool) and missing:
        return None
    if hasattr(value, "item"):
        return _json_scalar(value.item())
    return str(value)


def _duplicate_count(candidates: list[CandidateRecord]) -> int:
    hashes = [_canonical_hash(candidate) for candidate in candidates]
    return len(hashes) - len(set(hashes))


def _duplicate_counts_by_class(candidates: list[CandidateRecord], target_column: str) -> dict[str, int]:
    grouped: dict[str, list[str]] = {}
    for candidate in candidates:
        label = str(candidate.data.get(target_column))
        grouped.setdefault(label, []).append(_canonical_hash(candidate))
    return {label: len(values) - len(set(values)) for label, values in sorted(grouped.items())}


def _count_ids_by_class(candidates: list[CandidateRecord], ids: list[str], target_column: str) -> dict[str, int]:
    selected = set(ids)
    counts: dict[str, int] = {}
    for candidate in candidates:
        if candidate.record_id in selected:
            label = str(candidate.data.get(target_column))
            counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))


def _aggregate_failures(
    failures: list[ParseFailureEvent], b1: dict[str, Any], b2: dict[str, Any], b3: dict[str, Any],
    *, candidates: list[CandidateRecord] | None = None, plan: GenerationPlan | None = None,
    spec: Any | None = None,
) -> dict[str, Any]:
    """Aggregate multi-label failure evidence with requested-class denominators.

    Generation failures are emitted once per provider response, while the
    denominator is requested records.  A failed batch therefore contributes
    ``requested_count`` affected requested slots and retains a separate
    ``failed_response_count`` event count for auditability.  Judge failures
    remain candidate-level events and are tracked separately from generation
    provider failures.
    """

    categories = (
        "PARSE", "SCHEMA", "MISSING_FIELD", "INVALID_CATEGORY", "TARGET_MISMATCH",
        "OBSERVED_RANGE_WARNING", "EXACT_DUPLICATE", "B2_REJECTED", "B3_REJECTED",
        "B3_MALFORMED", "PROVIDER_ERROR",
    )
    candidate_list = candidates or []
    candidate_by_id = {candidate.record_id: candidate for candidate in candidate_list}
    requested_by_id = {
        candidate.record_id: str(candidate.metadata.get("requested_class"))
        for candidate in candidate_list
        if candidate.metadata.get("requested_class") is not None
    }
    records: dict[str, dict[str, set[str]]] = {category: {} for category in categories}
    occurrences: dict[str, dict[str, int]] = {category: {} for category in categories}
    failed_response_counts: dict[str, dict[str, int]] = {category: {} for category in categories}
    provider_sources: dict[str, dict[str, int]] = {
        "generation": {"failed_response_count": 0, "affected_requested_record_count": 0},
        "judge": {"failed_response_count": 0, "affected_record_count": 0},
    }
    generation_provider_records: dict[str, set[str]] = {}
    seen_category_records: dict[str, set[str]] = {category: set() for category in categories}

    def add(
        category: str, record_id: str, requested_class: str | None, *, requested_count: int = 1,
        source: str | None = None, count_response: bool = True,
    ) -> None:
        if category not in records:
            return
        label = requested_class or "<UNKNOWN>"
        count = max(1, int(requested_count))
        # A category should identify each affected response/record once.  A
        # provider event may also appear in a baseline failure_record_ids
        # export, so de-duplicate that candidate/event identity here.
        if record_id in seen_category_records[category]:
            return
        seen_category_records[category].add(record_id)
        affected_ids = {record_id} if count == 1 else {f"{record_id}:slot-{index}" for index in range(count)}
        records[category].setdefault(label, set()).update(affected_ids)
        occurrences[category][label] = occurrences[category].get(label, 0) + count
        if count_response:
            failed_response_counts[category][label] = failed_response_counts[category].get(label, 0) + 1
        if source == "generation":
            provider_sources["generation"]["failed_response_count"] += 1
            provider_sources["generation"]["affected_requested_record_count"] += count
            generation_provider_records.setdefault(label, set()).update(affected_ids)
        elif source == "judge":
            provider_sources["judge"]["failed_response_count"] += 1
            provider_sources["judge"]["affected_record_count"] += count

    for failure in failures:
        requested_class = failure.metadata.get("requested_class")
        requested = str(requested_class) if requested_class is not None else None
        requested_count_value = failure.metadata.get("requested_count")
        requested_count = int(requested_count_value) if isinstance(requested_count_value, (int, float)) and requested_count_value > 0 else 1
        if failure.parser_version == "judge-json-v1":
            category = "B3_MALFORMED"
            add(category, f"event:{failure.event_id}", requested)
        elif failure.parser_version == "provider-v1":
            category = "PROVIDER_ERROR"
            is_generation = requested_count_value is not None or failure.event_id.startswith("provider-generation-")
            if not is_generation:
                requested = requested or requested_by_id.get(failure.event_id.removeprefix("judge-provider-"))
            add(category, f"event:{failure.event_id}", requested, requested_count=requested_count if is_generation else 1,
                source="generation" if is_generation else "judge")
        else:
            category = "PARSE"
            add(category, f"event:{failure.event_id}", requested, requested_count=requested_count)

    # Every exact duplicate after the first is marked, while retaining the
    # entire raw pool as the denominator.  This is a count of equality events,
    # not a privacy or disclosure claim.
    seen_hashes: set[str] = set()
    for candidate in candidate_list:
        canonical = _canonical_hash(candidate)
        if canonical in seen_hashes:
            add("EXACT_DUPLICATE", candidate.record_id, requested_by_id.get(candidate.record_id))
        seen_hashes.add(canonical)

    failure_event_ids = {failure.event_id for failure in failures}
    for category in ("SCHEMA", "MISSING_FIELD", "INVALID_CATEGORY", "TARGET_MISMATCH", "OBSERVED_RANGE_WARNING", "B2_REJECTED", "B3_REJECTED", "B3_MALFORMED", "PROVIDER_ERROR"):
        for record_id in b2.get("failure_record_ids", {}).get(category, []) + b3.get("failure_record_ids", {}).get(category, []):
            if category == "B3_MALFORMED" and f"judge-parse-{record_id}" in failure_event_ids:
                continue
            if category == "PROVIDER_ERROR" and f"judge-provider-{record_id}" in failure_event_ids:
                continue
            candidate = candidate_by_id.get(str(record_id))
            source = "judge" if category == "PROVIDER_ERROR" and str(record_id) in set(b3.get("failure_record_ids", {}).get(category, [])) else None
            add(category, str(record_id), requested_by_id.get(str(record_id)), source=source)
            if candidate is None and str(record_id).startswith("event:"):
                add(category, str(record_id), None)

    # Retain the original compact aliases consumed by earlier replay reports.
    global_counts = {category: sum(len(ids) for ids in by_class.values()) for category, by_class in records.items()}
    legacy: dict[str, int] = {
        "parse_failure": global_counts["PARSE"],
        "schema_failure": global_counts["SCHEMA"], "schema_failures": global_counts["SCHEMA"],
        "missing_field": global_counts["MISSING_FIELD"],
        "category_invalid": global_counts["INVALID_CATEGORY"], "invalid_category": global_counts["INVALID_CATEGORY"],
        "target_wrong": global_counts["TARGET_MISMATCH"], "target_mismatch": global_counts["TARGET_MISMATCH"],
        "range_warning": global_counts["OBSERVED_RANGE_WARNING"], "range_warnings": global_counts["OBSERVED_RANGE_WARNING"],
        "duplicate": global_counts["EXACT_DUPLICATE"],
        "b2_rejection": global_counts["B2_REJECTED"], "b2_rejections": global_counts["B2_REJECTED"],
        "deterministic_structural_rejection": global_counts["B2_REJECTED"],
        "judge_rejection": global_counts["B3_REJECTED"], "judge_rejections": global_counts["B3_REJECTED"],
        "judge_malformed": global_counts["B3_MALFORMED"],
        "judge_provider_failure": provider_sources["judge"]["affected_record_count"],
        "generation_provider_failure": provider_sources["generation"]["affected_requested_record_count"],
        "provider_error": global_counts["PROVIDER_ERROR"],
    }

    class_quotas = getattr(plan, "class_quotas", ()) if plan is not None else ()
    quotas = {str(quota.label): int(quota.count) for quota in class_quotas}
    raw_denominator = len(candidate_list)
    requested_denominator = plan.requested_count if plan is not None else raw_denominator

    def summary_for(labels: set[str], denominator: int) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for category in categories:
            ids = set().union(*(records[category].get(label, set()) for label in labels)) if labels else set()
            count = sum(occurrences[category].get(label, 0) for label in labels)
            parse_ids = set().union(*(records["PARSE"].get(label, set()) for label in labels)) if labels else set()
            provider_ids = set().union(*(generation_provider_records.get(label, set()) for label in labels)) if labels else set()
            unparseable_ids = parse_ids | provider_ids
            result[category] = {
                "occurrences": count,
                "unique_affected_record_count": len(ids),
                "failed_response_count": sum(failed_response_counts[category].get(label, 0) for label in labels),
                "denominator": denominator,
                "rate": len(ids) / denominator if denominator else None,
            }
        parse_ids = set().union(*(records["PARSE"].get(label, set()) for label in labels)) if labels else set()
        provider_ids = set().union(*(generation_provider_records.get(label, set()) for label in labels)) if labels else set()
        unparseable_ids = parse_ids | provider_ids
        result["unparseable"] = {
            "occurrences": len(unparseable_ids),
            "unique_affected_record_count": len(unparseable_ids),
            "denominator": denominator,
            "rate": len(unparseable_ids) / denominator if denominator else None,
        }
        return result

    by_requested: dict[str, Any] = {}
    for label, denominator in quotas.items():
        by_requested[label] = {
            "requested_count": denominator,
            "parseable_count": sum(1 for candidate in candidate_list if requested_by_id.get(candidate.record_id) == label),
            "failures": summary_for({label}, denominator),
        }
    minority_label = str(getattr(spec, "minority_label", "")) if spec is not None and getattr(spec, "minority_label", None) is not None else None
    majority_labels = set(quotas) - {minority_label} if minority_label is not None else set(quotas)
    minority_labels = {minority_label} if minority_label in quotas else set()
    by_role = {
        "majority": {
            "requested_count": sum(quotas.get(label, 0) for label in majority_labels),
            "failures": summary_for(majority_labels, sum(quotas.get(label, 0) for label in majority_labels)),
        },
        "minority": {
            "requested_count": sum(quotas.get(label, 0) for label in minority_labels),
            "failures": summary_for(minority_labels, sum(quotas.get(label, 0) for label in minority_labels)),
        },
    }
    global_summary = summary_for(set(quotas), requested_denominator)
    # Keep a top-level count for report readers that need the concise view.
    global_summary["raw_pool_count"] = raw_denominator
    global_unparseable = global_summary["unparseable"]
    global_summary["provider_error_breakdown"] = {
        "generation": provider_sources["generation"],
        "judge": provider_sources["judge"],
    }
    return {
        **legacy,
        "categories": list(categories),
        "global": global_summary,
        "unparseable_requested_record_count": global_unparseable["unique_affected_record_count"],
        "unparseable_rate": global_unparseable["rate"],
        "by_requested_class": by_requested,
        "majority_vs_minority": by_role,
        "provider_error_breakdown": {
            "generation": provider_sources["generation"],
            "judge": provider_sources["judge"],
        },
    }


def _minority_analysis(spec: Any, plan: GenerationPlan, candidates: list[CandidateRecord], b1: dict[str, Any], b2: dict[str, Any], b3: dict[str, Any]) -> dict[str, Any]:
    """Summarize minority behavior using only the authoritative dataset target."""

    target_column = str(spec.target_column)
    minority = spec.minority_label
    minority_label = None if minority is None else str(minority)
    minority_candidates = [candidate for candidate in candidates if str(candidate.data.get(target_column)) == minority_label] if minority_label is not None else []
    requested_count = next((quota.count for quota in plan.class_quotas if str(quota.label) == minority_label), 0) if minority_label is not None else 0
    parseable_count = len(minority_candidates)
    minority_ids = {candidate.record_id for candidate in minority_candidates}
    duplicate_count = len(minority_candidates) - len({_canonical_hash(candidate) for candidate in minority_candidates})

    def accepted_metrics(summary: dict[str, Any]) -> dict[str, Any]:
        accepted_ids = set(summary.get("accepted_record_ids", []))
        accepted_count = len(accepted_ids & minority_ids)
        return {
            "accepted_count": accepted_count,
            "accepted_rate": accepted_count / parseable_count if parseable_count else None,
            "requested_rate": accepted_count / requested_count if requested_count else None,
        }

    baselines = {"b1": b1, "b2": b2, "b3": b3}
    class_conditional = {
        name: summary.get("intrinsic", {}).get("class_conditional", {"status": "not_available"})
        for name, summary in baselines.items()
    }
    tstr = {
        name: summary.get("utility", {}).get("TSTR", {"status": "not_available"})
        for name, summary in baselines.items()
    }
    return {
        "authoritative_target_column": target_column,
        "requested_minority_label": minority_label,
        "requested_minority_count": requested_count,
        "parseable_minority_count": parseable_count,
        "b1": accepted_metrics(b1),
        "b2": accepted_metrics(b2),
        "b3": accepted_metrics(b3),
        "minority_duplicate_count": duplicate_count,
        "minority_duplicate_rate": duplicate_count / parseable_count if parseable_count else None,
        "class_conditional_discrepancy": class_conditional,
        "tstr": tstr,
    }


def _write_json(path: Path, value: Any, *, overwrite: bool = False) -> None:
    write_json(path, value, overwrite=overwrite)


def _write_jsonl(path: Path, values: list[Any]) -> None:
    assert_writable(path)
    if values:
        append_jsonl(path, values)
    else:
        write_text(path, "")


def _write_yaml(path: Path, value: Any) -> None:
    assert_writable(path)
    write_text(path, yaml.safe_dump(value, sort_keys=True))


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


def _sanitized_endpoint(value: str | None) -> str | None:
    """Retain endpoint identity while dropping query/fragment/userinfo."""

    if not value:
        return None
    parts = urlsplit(str(value))
    if not (parts.scheme or parts.netloc):
        return str(value).split("?", 1)[0].split("#", 1)[0]
    try:
        hostname = parts.hostname or ""
        host = f"[{hostname}]" if ":" in hostname and not hostname.startswith("[") else hostname
        netloc = host
        if parts.port is not None:
            netloc = f"{netloc}:{parts.port}"
    except ValueError:
        netloc = ""
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))
