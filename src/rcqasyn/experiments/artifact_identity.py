"""Execution provenance bindings without modifying scientific metric payloads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rcqasyn.storage.artifacts import read_json, write_json
from rcqasyn.storage.ownership import file_hash

from .recorded_accounting import (
    validate_call_accounting,
    validate_call_purpose,
    validate_comparison_identities,
)
from .specification import fingerprint

BINDING_VERSION = "m1-artifact-bindings-v1"
IDENTITY_KEYS = (
    "execution_id",
    "dataset_id",
    "dataset_fingerprint",
    "split_fingerprint",
    "specification_fingerprint",
)


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _same(expected: Any, observed: Any, label: str) -> None:
    if expected != observed:
        raise ValueError(f"{label} identity mismatch")


def _required(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"required binding artifact is missing: {path.name}")
    value = read_json(path)
    if not isinstance(value, dict):
        raise TypeError(f"required binding artifact is invalid: {path.name}")
    return value


def explicit_identities(value: Any, expected: dict[str, Any], label: str) -> None:
    """Validate available identity declarations, including nested metadata."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in expected:
                _same(expected[key], item, f"{label}/{key}")
            else:
                explicit_identities(item, expected, f"{label}/{key}")
    elif isinstance(value, list):
        for item in value:
            explicit_identities(item, expected, label)


def write_execution_bindings(
    path: Path, comparison: dict[str, Any], scientific: dict[str, Any]
) -> str:
    """Capture resolved inputs and result origin before the execution is sealed."""
    identity = {key: comparison[key] for key in IDENTITY_KEYS}
    source_files = [
        "resolved_config.yaml",
        "scientific_specification.json",
        "dataset/split_manifest.json",
        "dataset/evaluation_population.json",
        "dataset/profile.json",
        "dataset/profile_source.json",
        "generation_plan.json",
        "generation_seed_plan.json",
        "prompts/generation.txt",
        "prompts/judge.txt",
        "candidates_raw.jsonl",
        "generation_failures.jsonl",
        "provider_calls.jsonl",
    ]
    source_files += [
        p.relative_to(path).as_posix() for p in sorted((path / "calls").glob("*.json"))
    ]
    binding = {
        "schema_version": BINDING_VERSION,
        **identity,
        "source_files": {name: file_hash(path / name) for name in source_files},
    }
    write_json(path / "execution_binding.json", binding)
    comparison["artifact_binding_version"] = BINDING_VERSION
    comparison["execution_binding_fingerprint"] = fingerprint(binding)
    comparison["result_binding_fingerprints"] = {}
    for name, baseline in comparison["baselines"].items():
        directory = path / "baselines" / name
        sources = [p for p in sorted(directory.glob("*.jsonl"))]
        result = {
            "schema_version": "m1-result-binding-v1",
            **identity,
            "baseline": name,
            "control_fingerprint": scientific["specification"]["controls"][name]["fingerprint"],
            "accepted_population_fingerprint": fingerprint(jsonl(directory / "candidates.jsonl")),
            "accepted_record_ids": baseline["accepted_record_ids"],
            "accepted_count": baseline["accepted"],
            "source_files": {p.name: file_hash(p) for p in sources},
            "result_files": {
                file: file_hash(directory / file)
                for file in ("metrics.json", "classifier_metrics.json")
            },
        }
        write_json(directory / "result_binding.json", result)
        comparison["result_binding_fingerprints"][name] = fingerprint(result)
    return comparison["execution_binding_fingerprint"]


def validate_execution_bindings(
    path: Path, manifest: dict[str, Any], scientific: dict[str, Any], comparison: dict[str, Any]
) -> None:
    import yaml

    from rcqasyn.config.experiment import ExperimentConfig
    from rcqasyn.datasets.profile import DatasetProfile
    from rcqasyn.generation.parser import parse_generation_response, parse_judge_response
    from rcqasyn.utils.hashing import sha256_text

    from .runner import _generation_plan, _generation_seed_plan, _sanitized_endpoint
    from .specification import seed_provenance

    _same(
        BINDING_VERSION,
        manifest.get("artifact_binding_version"),
        "required artifact binding version",
    )
    _same(
        BINDING_VERSION,
        comparison.get("artifact_binding_version"),
        "required comparison binding version",
    )
    binding = _required(path / "execution_binding.json")
    _same(BINDING_VERSION, binding.get("schema_version"), "execution binding schema")
    for owner in (manifest, comparison):
        _same(fingerprint(binding), owner.get("execution_binding_fingerprint"), "execution binding")
    identity = {key: manifest[key] for key in IDENTITY_KEYS}
    for key, expected in identity.items():
        _same(expected, binding.get(key), f"required execution binding {key}")
    required_sources = {
        "resolved_config.yaml",
        "scientific_specification.json",
        "dataset/split_manifest.json",
        "dataset/evaluation_population.json",
        "dataset/profile.json",
        "dataset/profile_source.json",
        "generation_plan.json",
        "generation_seed_plan.json",
        "prompts/generation.txt",
        "prompts/judge.txt",
        "candidates_raw.jsonl",
        "generation_failures.jsonl",
        "provider_calls.jsonl",
    }
    required_sources.update(p.relative_to(path).as_posix() for p in (path / "calls").glob("*.json"))
    _same(required_sources, set(binding["source_files"]), "required source graph binding")
    for relative, sha256 in binding["source_files"].items():
        _same(sha256, file_hash(path / relative), f"{relative} source binding")

    spec = scientific["specification"]
    config = ExperimentConfig.model_validate(
        yaml.safe_load((path / "resolved_config.yaml").read_text(encoding="utf-8"))
    )
    _same(config.canonical_hash(), manifest.get("config_hash"), "recorded configuration")
    _same(
        config.dataset.model_dump(mode="json"),
        spec["dataset_run"],
        "scientific configuration dataset",
    )
    _same(
        config.generation.model_dump(mode="json"),
        spec["generation"],
        "scientific configuration generation",
    )
    _same(
        list(config.metrics.classifiers),
        spec["evaluation"]["classifiers"],
        "scientific configuration classifiers",
    )
    _same(
        config.generator_judge_same_model,
        spec["generator_judge_same_model"],
        "shared provider configuration",
    )
    for role, provider in (("generator", config.generator), ("judge", config.judge.provider)):
        resolved = provider.model_dump(
            mode="json", exclude={"fixture", "api_key_env", "timeout_seconds"}
        )
        _same(
            resolved,
            {k: v for k, v in spec["providers"][role].items() if k != "recorded_responses_sha256"},
            f"{role} configuration",
        )
        _same(provider.model, manifest.get(f"{role}_model"), f"{role} manifest model")
        _same(
            _sanitized_endpoint(provider.base_url),
            manifest.get(f"{role}_endpoint"),
            f"{role} manifest endpoint",
        )
    _same(config.dataset.root_seed, manifest.get("root_seed"), "manifest root seed")
    for key, value in (
        ("generator_judge_same_model", config.generator_judge_same_model),
        ("generation_transport_version", config.generation.transport_version),
        ("generation_response_format", config.generation.response_format),
        ("generation_reasoning_effort", config.generation.reasoning_effort),
        ("generation_max_tokens", config.generation.max_tokens),
        ("generation_timeout_seconds", config.generator.timeout_seconds),
    ):
        _same(value, manifest.get(key), f"manifest recorded {key}")
    profile = DatasetProfile.model_validate_json(
        (path / "dataset/profile_source.json").read_text(encoding="utf-8")
    )
    _same(
        profile.model_dump(mode="json"),
        read_json(path / "dataset/profile.json"),
        "profile serialized source",
    )
    plan = _generation_plan(config, profile, spec["prompts"]["generation"])
    _same(
        plan.model_dump(mode="json"),
        read_json(path / "generation_plan.json"),
        "resolved generation plan",
    )
    seed_plan = _generation_seed_plan(config, plan)
    _same(seed_plan, read_json(path / "generation_seed_plan.json"), "generation seed plan")
    split = read_json(path / "dataset/split_manifest.json")
    from types import SimpleNamespace

    _same(
        seed_provenance(config, SimpleNamespace(split_seed=split["split_seed"]), seed_plan),
        manifest.get("seed_provenance"),
        "manifest seed provenance",
    )
    _same(
        {q.label: q.count for q in plan.class_quotas},
        manifest.get("class_quotas"),
        "manifest quotas",
    )
    controls = spec["controls"]
    for name, control in controls.items():
        _same(fingerprint(control["descriptor"]), control["fingerprint"], f"{name} control")
    _same(
        config.baselines.model_dump(mode="json"),
        controls["b2"]["descriptor"]["configuration"],
        "B2 configuration",
    )
    _same(
        config.judge.model_dump(mode="json", exclude={"provider"}),
        controls["b3"]["descriptor"]["judge"],
        "judge configuration",
    )
    _same(
        profile.model_dump(mode="json")["domains"],
        controls["b2"]["descriptor"]["train_domains"],
        "B2 TRAIN domains",
    )
    _same(
        {
            col: {bound: value[bound] for bound in ("min", "max")}
            for col, value in profile.numeric_summary.items()
        },
        controls["b2"]["descriptor"]["train_ranges"],
        "B2 TRAIN ranges",
    )
    _same(
        fingerprint(profile.to_generation_context()),
        controls["b3"]["descriptor"]["train_context_sha256"],
        "judge TRAIN context",
    )
    templates = {
        role: (path / f"prompts/{role}.txt").read_text(encoding="utf-8")
        for role in ("generation", "judge")
    }
    for role, template in templates.items():
        _same(sha256_text(template), spec["prompts"][role], f"{role} prompt bytes")

    from .recorded_requirements import validate_recorded_requirements
    from .recorded_split import validate_recorded_split

    population_path = path / "dataset/evaluation_population.json"
    _same(identity["dataset_fingerprint"], file_hash(population_path), "normalized population source")
    population = read_json(population_path)
    validate_recorded_split(spec, split, profile.model_dump(mode="json"), population)
    target_index = population["columns"].index(spec["dataset"]["definition"]["target_column"])
    train_indices = set(split["train_indices"])
    train_classes = sorted({
        str(row[target_index])
        for index, row in zip(population["index"], population["data"], strict=True)
        if index in train_indices and row[target_index] is not None
    })
    validate_recorded_requirements(spec, config, profile, train_classes=train_classes)

    raw = jsonl(path / "candidates_raw.jsonl")
    raw_by_id = {row["record_id"]: row for row in raw}
    _same(len(raw), len(raw_by_id), "unique raw candidate")
    calls = {p.stem: read_json(p) for p in (path / "calls").glob("*.json")}
    traces = jsonl(path / "provider_calls.jsonl") + jsonl(
        path / "baselines/b3/provider_calls.jsonl"
    )
    traces_by_id = {trace["call_id"]: trace for trace in traces}
    _same(len(traces), len(traces_by_id), "unique provider trace")
    for call_id, call in calls.items():
        _same("m1-call-evidence-v1", call.get("schema_version"), "durable call schema")
        _same(identity["execution_id"], call.get("execution_id"), "durable call execution")
        _same(call_id, call.get("attempt_id"), "durable call attempt")
        if call.get("status") not in {"returned", "failed"}:
            raise ValueError("durable call status identity is invalid")
        request = call["request"]
        validate_call_purpose(call)
        role = request["role"]
        if role not in {"generation", "judge", "smoke"}:
            raise ValueError("durable call role identity is invalid")
        provider_role = "judge" if call["purpose"] == "judge" else "generator"
        _same(
            spec["providers"][provider_role],
            call.get("provider_identity"),
            "durable call configured provider",
        )
        _same(
            scientific["fingerprint"],
            call.get("specification_fingerprint"),
            "durable call scientific binding",
        )
        if call["status"] == "returned":
            trace = traces_by_id.get(call_id)
            if trace is None:
                raise ValueError("returned durable call has no provider trace identity")
            response = call["response"]
            _same(call["purpose"], trace["role"], "trace role")
            for key in (
                "provider",
                "model",
                "endpoint",
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "cost_usd",
                "latency_ms",
                "finish_reason",
                "replay_source_id",
            ):
                _same(response.get(key), trace.get(key), f"trace response {key}")
            from datetime import datetime

            _same(
                datetime.fromisoformat(response["created_at"]),
                datetime.fromisoformat(trace["created_at"]),
                "trace response timestamp",
            )
            _same(response["response"], trace.get("raw_response"), "trace raw response")
            _same(
                response.get("call_id"),
                trace.get("metadata", {}).get("external_provider_call_id"),
                "trace external provider ID",
            )
            _same(
                response.get("response_format") or request.get("response_format") or {},
                trace.get("response_format"),
                "trace response format",
            )
            _same(
                response.get("reasoning_effort") or request.get("reasoning_effort"),
                trace.get("reasoning_effort"),
                "trace reasoning effort",
            )
            for key in ("prompt", "temperature", "seed", "max_tokens"):
                _same(request.get(key), trace.get(key), f"trace request {key}")
    for trace in traces:
        if trace["call_id"] not in calls or calls[trace["call_id"]]["status"] != "returned":
            raise ValueError("provider trace has no returned durable call identity")
    generation_calls = [call for call in calls.values() if call["purpose"] == "generation"]
    generation_calls.sort(key=lambda call: call["request"]["request_index"])
    _same(len(seed_plan["calls"]), len(generation_calls), "generation attempted call count")
    reconstructed = []
    parsed_failures = []
    for index, (call, entry) in enumerate(zip(generation_calls, seed_plan["calls"], strict=True)):
        request = call["request"]
        _same(index, request["request_index"], "generation request order")
        for key, expected in (
            ("seed", entry["provider_seed"]),
            ("temperature", config.generation.temperature),
            ("max_tokens", config.generation.max_tokens),
            (
                "response_format",
                {"type": config.generation.response_format}
                if config.generation.response_format
                else None,
            ),
            ("reasoning_effort", config.generation.reasoning_effort),
        ):
            _same(expected, request.get(key), f"generation request {key}")
        prompt = (
            "[recorded-response replay; no upstream prompt executed]"
            if call["recorded_response_only"]
            else templates["generation"].format(
                profile_json=json.dumps(profile.model_dump(mode="json"), sort_keys=True),
                generation_context_json=json.dumps(profile.to_generation_context(), sort_keys=True),
                class_condition=entry["requested_class"],
                requested_count=entry["requested_count"],
                reference_examples=json.dumps(profile.reference_examples, sort_keys=True),
            )
        )
        _same(prompt, request["prompt"], "generation rendered prompt")
        if call["status"] != "returned":
            continue
        trace = traces_by_id[call["attempt_id"]]
        for key in ("requested_class", "requested_count"):
            _same(entry[key], trace[key], f"generation trace {key}")
        _same(spec["prompts"]["generation"], trace["prompt_hash"], "generation trace prompt")
        parsed = parse_generation_response(
            call["response"]["response"],
            run_id=manifest["run_id"],
            call_id=call["attempt_id"],
            generator_id=plan.generator_id,
            generator_version=plan.generator_version,
            prompt_version=plan.prompt_version,
            seed=entry["provider_seed"],
            requested_class=entry["requested_class"],
            requested_count=entry["requested_count"],
            transport_version=config.generation.transport_version,
        )
        reconstructed.extend(row.model_dump(mode="json") for row in parsed.candidates)
        parsed_failures.extend(row.model_dump(mode="json") for row in parsed.failures)
    _same(
        [{k: v for k, v in row.items() if k != "created_at"} for row in reconstructed],
        [{k: v for k, v in row.items() if k != "created_at"} for row in raw],
        "candidate generation provenance",
    )
    _same(len(raw), comparison.get("raw_pool_count"), "comparison raw population")
    for key in ("requested", "experiment_requested"):
        _same(plan.requested_count, comparison.get(key), f"comparison {key}")
    _same(
        plan.requested_count,
        comparison["generation_accounting"]["requested"],
        "generation accounting requested",
    )
    _same(
        len(raw),
        comparison["generation_accounting"]["returned_parseable"],
        "generation accounting returned",
    )

    generation_failures = jsonl(path / "generation_failures.jsonl")
    for failure in generation_failures:
        call = calls.get(failure["call_id"])
        if call is None or call["purpose"] != "generation":
            raise ValueError("generation failure call identity mismatch")
        if failure["parser_version"] == "provider-v1":
            _same("failed", call["status"], "generation provider failure call status")
        else:
            _same("returned", call["status"], "generation parse failure call status")
            _same(
                call["response"]["response"],
                failure.get("raw_output"),
                "generation failure raw response",
            )
    _same(
        [{k: v for k, v in row.items() if k != "created_at"} for row in parsed_failures],
        [
            {k: v for k, v in row.items() if k != "created_at"}
            for row in generation_failures
            if row["parser_version"] != "provider-v1"
        ],
        "generation parse failure provenance",
    )
    _same(
        {call["attempt_id"] for call in generation_calls if call["status"] == "failed"},
        {row["call_id"] for row in generation_failures if row["parser_version"] == "provider-v1"},
        "generation failed call coverage",
    )
    judge_calls = [call for call in calls.values() if call["purpose"] == "judge"]
    judge_calls.sort(key=lambda call: call["request"]["request_index"])
    _same(len(raw), len(judge_calls), "judge candidate call population")
    validate_call_accounting(
        manifest, comparison, calls, generation_failures,
        jsonl(path / "baselines/b3/judge_failures.jsonl"),
        jsonl(path / "baselines/b3/decisions.jsonl"),
    )
    validate_comparison_identities(
        {key: value for key, value in comparison.items() if key != "baselines"},
        {
            **identity, "run_id": manifest["run_id"],
            "scientific_fingerprint": scientific["fingerprint"],
            "science_fingerprint": scientific["fingerprint"],
        },
        controls,
    )
    for index, (call, candidate) in enumerate(zip(judge_calls, raw, strict=True)):
        request = call["request"]
        _same(index, request["request_index"], "judge request candidate order")
        for key, value in (
            ("seed", config.generation.provider_seed),
            ("max_tokens", config.generation.max_tokens),
            ("temperature", 0.0),
            (
                "response_format",
                {"type": config.judge.response_format} if config.judge.response_format else None,
            ),
            ("reasoning_effort", config.judge.reasoning_effort),
        ):
            _same(value, request.get(key), f"judge request {key}")
        judge_profile = (
            profile.to_generation_context()
            if config.generation.transport_version == "v2"
            else profile.model_dump(mode="json")
        )
        prompt = (
            "[recorded-response replay; no upstream prompt executed]"
            if call["recorded_response_only"]
            else templates["judge"].format(
                profile_json=json.dumps(judge_profile, sort_keys=True),
                candidate_json=json.dumps(candidate["data"], sort_keys=True),
            )
        )
        _same(prompt, request["prompt"], "judge candidate rendered prompt")
        if call["status"] == "returned":
            _same(
                spec["prompts"]["judge"],
                traces_by_id[call["attempt_id"]]["prompt_hash"],
                "judge trace prompt binding",
            )

    _same(
        set(comparison["baselines"]),
        set(comparison.get("result_binding_fingerprints", {})),
        "required baseline binding identities",
    )
    for name, baseline in comparison["baselines"].items():
        directory = path / "baselines" / name
        expected = {
            **identity,
            "run_id": manifest["run_id"],
            "control_fingerprint": controls[name]["fingerprint"],
            "baseline": name,
            "control_id": name,
            "baseline_id": name,
            "science_fingerprint": scientific["fingerprint"],
            "scientific_fingerprint": scientific["fingerprint"],
        }
        result_binding = _required(directory / "result_binding.json")
        _same("m1-result-binding-v1", result_binding.get("schema_version"), "result binding schema")
        _same(
            fingerprint(result_binding),
            comparison.get("result_binding_fingerprints", {}).get(name),
            "required result binding fingerprint",
        )
        for key, value in expected.items():
            if key in (*IDENTITY_KEYS, "control_fingerprint"):
                _same(value, result_binding.get(key), f"required result binding {key}")
        _same(name, result_binding.get("baseline"), "result binding baseline")
        accepted = jsonl(directory / "candidates.jsonl")
        expected["accepted_population_fingerprint"] = fingerprint(accepted)
        decisions = jsonl(directory / "decisions.jsonl")
        _same(
            list(raw_by_id),
            [d["candidate_id"] for d in decisions],
            f"{name} decision source population",
        )
        for decision in decisions:
            _same(name, decision["baseline"], "decision baseline")
            if type(decision["accepted"]) is not bool:
                raise ValueError("decision acceptance identity is invalid")
        source_accepted = [raw_by_id[d["candidate_id"]] for d in decisions if d["accepted"]]
        _same(source_accepted, accepted, f"{name} accepted candidate population")
        ids = [row["record_id"] for row in accepted]
        _same(ids, baseline.get("accepted_record_ids"), f"{name} accepted population order")
        _same(len(accepted), baseline.get("accepted"), f"{name} accepted population count")
        _same(len(raw), baseline.get("raw_pool_count"), f"{name} raw population count")
        _same(plan.requested_count, baseline.get("requested"), f"{name} requested population")
        _same(
            fingerprint(accepted),
            result_binding.get("accepted_population_fingerprint"),
            "required accepted population binding",
        )
        _same(ids, result_binding.get("accepted_record_ids"), "result accepted population order")
        _same(
            len(accepted), result_binding.get("accepted_count"), "result accepted population count"
        )
        source_paths = {p.name for p in directory.glob("*.jsonl")}
        _same(source_paths, set(result_binding["source_files"]), "required result source graph")
        for filename, sha256 in result_binding["source_files"].items():
            _same(sha256, file_hash(directory / filename), "result source binding")
            explicit_identities(jsonl(directory / filename), expected, filename)
        _same(
            {"metrics.json", "classifier_metrics.json"},
            set(result_binding["result_files"]),
            "required metric files binding",
        )
        for filename in result_binding["result_files"]:
            metric = read_json(directory / filename)
            explicit_identities(metric, expected, filename)
            _same(
                result_binding["result_files"][filename],
                file_hash(directory / filename),
                "result metric origin binding",
            )
        explicit_identities(baseline, expected, name)
        if name == "b2":
            evidence = jsonl(directory / "evidence.jsonl")
            by_id = {row["evidence_id"]: row for row in evidence}
            _same(len(evidence), len(by_id), "unique evidence identity")
            for row in evidence:
                if row["candidate_id"] not in raw_by_id:
                    raise ValueError("evidence candidate source identity mismatch")
                _same(
                    raw_by_id[row["candidate_id"]]["version"],
                    row["candidate_version"],
                    "evidence candidate version",
                )
            for decision in decisions:
                _same(
                    [
                        row["evidence_id"]
                        for row in evidence
                        if row["candidate_id"] == decision["candidate_id"]
                    ],
                    decision["evidence_ids"],
                    "decision evidence join",
                )
        if name == "b3":
            results = jsonl(directory / "judge_results.jsonl")
            by_id = {row["result_id"]: row for row in results}
            _same(len(results), len(by_id), "unique judge result identity")
            for row in results:
                candidate_id = row["candidate_id"]
                if candidate_id not in raw_by_id or row["judge_call_id"] not in calls:
                    raise ValueError("judge result source identity mismatch")
                call = calls[row["judge_call_id"]]
                _same("judge", call["request"]["role"], "judge result call role")
                _same(
                    list(raw_by_id).index(candidate_id),
                    call["request"]["request_index"],
                    "judge result candidate call join",
                )
                parsed = parse_judge_response(
                    call["response"]["response"],
                    run_id=manifest["run_id"],
                    candidate_id=candidate_id,
                    judge_call_id=call["attempt_id"],
                ).model_dump(mode="json")
                _same(
                    {k: v for k, v in parsed.items() if k != "created_at"},
                    {k: v for k, v in row.items() if k != "created_at"},
                    "judge result response provenance",
                )
            result_by_candidate = {row["candidate_id"]: row for row in results}
            _same(len(results), len(result_by_candidate), "unique candidate judge result")
            failure_by_candidate = {}
            for failure in jsonl(directory / "judge_failures.jsonl"):
                call = calls.get(failure["call_id"])
                if call is None or call["purpose"] != "judge":
                    raise ValueError("judge failure call identity mismatch")
                index = call["request"]["request_index"]
                candidate_id = raw[index]["record_id"]
                if candidate_id in failure_by_candidate:
                    raise ValueError("duplicate judge failure candidate identity")
                failure_by_candidate[candidate_id] = failure
                if failure["parser_version"] == "provider-v1":
                    _same("failed", call["status"], "judge failure call status")
                    _same(
                        f"judge-provider-{candidate_id}",
                        failure["event_id"],
                        "judge failure candidate join",
                    )
                else:
                    _same("judge-json-v1", failure["parser_version"], "judge failure parser")
                    _same("returned", call["status"], "judge malformed call status")
                    _same(
                        f"judge-parse-{candidate_id}",
                        failure["event_id"],
                        "judge malformed candidate join",
                    )
                    _same(
                        call["response"]["response"],
                        failure["raw_output"],
                        "judge malformed raw response",
                    )
                    try:
                        parse_judge_response(
                            call["response"]["response"],
                            run_id=manifest["run_id"],
                            candidate_id=candidate_id,
                            judge_call_id=call["attempt_id"],
                        )
                    except ValueError as error:
                        _same(str(error), failure["error"], "judge parser failure provenance")
                    else:
                        raise ValueError("judge failure contradicts returned result identity")
            _same(
                set(),
                set(result_by_candidate) & set(failure_by_candidate),
                "judge result/failure disjointness",
            )
            _same(
                set(raw_by_id),
                set(result_by_candidate) | set(failure_by_candidate),
                "judge result/failure candidate coverage",
            )
            for decision in decisions:
                expected_result = result_by_candidate.get(decision["candidate_id"])
                _same(
                    expected_result["result_id"] if expected_result else None,
                    decision.get("judge_result_id"),
                    "decision recorded judge result join",
                )
                result_id = decision.get("judge_result_id")
                if result_id:
                    result = by_id.get(result_id)
                    if result is None:
                        raise ValueError("decision judge result identity is missing")
                    _same(
                        decision["candidate_id"],
                        result["candidate_id"],
                        "decision judge candidate join",
                    )
                elif decision["accepted"]:
                    raise ValueError("accepted decision requires judge result identity")


def validate_legacy_identities(path: Path, manifest: dict[str, Any]) -> None:
    """Check recorded declarations without requiring identities absent historically."""
    expected = {key: manifest[key] for key in ("run_id", *IDENTITY_KEYS) if key in manifest}
    if "specification_fingerprint" in manifest:
        expected["science_fingerprint"] = manifest["specification_fingerprint"]
        expected["scientific_fingerprint"] = manifest["specification_fingerprint"]
    comparison_path = path / "comparison.json"
    if not comparison_path.is_file():
        return
    comparison = _required(comparison_path)
    explicit_identities(
        {k: v for k, v in comparison.items() if k != "baselines"}, expected, "legacy comparison"
    )
    for relative in ("dataset/split_manifest.json", "dataset/profile.json", "generation_plan.json"):
        if (path / relative).is_file():
            artifact = _required(path / relative)
            explicit_identities(artifact, expected, f"legacy {relative}")
            if (
                relative.endswith("split_manifest.json")
                and "root_seed" in manifest
                and "root_seed" in artifact
            ):
                _same(manifest["root_seed"], artifact["root_seed"], "legacy split root seed")
    for name, baseline in comparison.get("baselines", {}).items():
        baseline_expected = {**expected, "baseline": name, "baseline_id": name, "control_id": name}
        explicit_identities(baseline, baseline_expected, f"legacy {name}")
        for filename in ("metrics.json", "classifier_metrics.json"):
            metric_path = path / "baselines" / name / filename
            if metric_path.is_file():
                explicit_identities(
                    _required(metric_path), baseline_expected, f"legacy {name}/{filename}"
                )
