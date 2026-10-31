"""Study v3 provider adapters: Anthropic Messages, OpenAI-compatible Chat Completions.

One registry (``MODELS``) declares the eight generators. Anthropic uses the official
``anthropic`` SDK; OpenAI, Meta's Model API (OpenAI-compatible) and local Ollama use the
``openai`` SDK with a configured base URL. API providers pass through the existing
``rcqasyn`` provider gate before any client is built. Every call is checked against the
80% budget rule first and appended to ``budget.jsonl`` afterwards, with reasoning tokens
recorded separately where the provider reports them.

Keys are read from the environment (``.env`` via python-dotenv); they are never written,
logged or echoed. Endpoints in records are passed through ``_sanitized_endpoint``.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from rcqasyn.generation.provider import _sanitized_endpoint, provider_readiness
from study.v3 import budget
from study.v3.pricing import PRICES, cost_usd

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"


@dataclass(frozen=True)
class ModelSpec:
    name: str                 # study label
    provider: str             # anthropic | openai | meta | ollama
    model_id: str             # exact provider model ID
    base_url: str | None      # None -> SDK default (Anthropic); env-resolved for Ollama
    api_key_env: str | None
    batch_supported: bool
    # Request defaults chosen to keep generation cheap and comparable; every value sent
    # is recorded per call, so changing one is visible in the ledger and the traces.
    defaults: dict[str, Any] = field(default_factory=dict)
    note: str = ""


MODELS: dict[str, ModelSpec] = {
    spec.name: spec
    for spec in (
        # Haiku 5.5 / Sonnet 5.5 reject non-default sampling params and take no seed.
        # Thinking is switched off at low effort ("disabled" on Haiku 5.5, "between_tools"
        # on Sonnet 5.5, the only accepted off-switch there).
        ModelSpec("claude-haiku-5-5", "anthropic", "claude-haiku-5-5", None,
                  "ANTHROPIC_API_KEY", True,
                  {"thinking": {"type": "disabled"}, "effort": "low"}),
        ModelSpec("claude-sonnet-5-5", "anthropic", "claude-sonnet-5-5", None,
                  "ANTHROPIC_API_KEY", True,
                  {"thinking": {"type": "between_tools"}, "effort": "low"}),
        ModelSpec("gpt-6-luna", "openai", "gpt-6-luna", "https://api.openai.com/v1",
                  "OPENAI_API_KEY", True, {"reasoning_effort": "none"},
                  note="plan says GPT-6.1-luna; OpenAI lists only gpt-6-luna (Gate 0)"),
        ModelSpec("gpt-6.1-terra", "openai", "gpt-6.1-terra", "https://api.openai.com/v1",
                  "OPENAI_API_KEY", True, {"reasoning_effort": "low"},
                  note="reasoning_effort values for terra not documented on its page; "
                       "'low' used until verified"),
        # Standard endpoint: Meta does not train on content. Reasoning cannot be disabled
        # ("none" is a 400); "minimal" is the lowest documented effort.
        ModelSpec("muse-spark-1.3", "meta", "muse-spark-1.3", "https://api.meta.ai/v1",
                  "META_API_KEY", False, {"reasoning_effort": "minimal"}),
        ModelSpec("gemma4:e4b", "ollama", "gemma4:e4b", None, None, False,
                  {"temperature": 0.7}),
        ModelSpec("qwen2.5:7b-instruct", "ollama", "qwen2.5:7b-instruct", None, None, False,
                  {"temperature": 0.7}),
        ModelSpec("llama3.1:8b", "ollama", "llama3.1:8b", None, None, False,
                  {"temperature": 0.7}),
    )
}


@dataclass(frozen=True)
class CallResult:
    text: str
    model: str
    provider: str
    endpoint: str | None
    mode: str  # sync | batch
    input_tokens: int | None
    cached_input_tokens: int | None
    output_tokens: int | None
    reasoning_tokens: int | None
    latency_ms: float | None
    call_id: str | None
    finish_reason: str | None
    request: dict[str, Any]
    raw: dict[str, Any]
    cost_usd: float | None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProviderNotReady(RuntimeError):
    pass


def load_env() -> None:
    """Load ``.env`` into the process environment without reading values ourselves."""
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


def resolve_base_url(spec: ModelSpec) -> str | None:
    if spec.provider == "ollama":
        return os.environ.get("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL
    return spec.base_url


def require_ready(spec: ModelSpec) -> None:
    """Refuse before any client is built when configuration is incomplete.

    API providers reuse ``rcqasyn``'s gate (absolute URL, real model, populated key env
    var). Local Ollama has no key, so it is checked for an absolute URL and a model in
    the registry; reachability is verified separately by listing the server's models.
    """
    base_url = resolve_base_url(spec) or "https://api.anthropic.com"
    if spec.provider == "ollama":
        if not base_url.startswith(("http://", "https://")):
            raise ProviderNotReady("OLLAMA_BASE_URL must be an absolute HTTP(S) URL")
        return
    readiness = provider_readiness(SimpleNamespace(
        kind="openai_compatible", base_url=base_url, model=spec.model_id,
        api_key_env=spec.api_key_env,
    ))
    if not readiness.ready:
        raise ProviderNotReady(f"{spec.name}: {readiness.reason}")


def build_client(spec: ModelSpec, *, timeout: float = 120.0) -> Any:
    require_ready(spec)
    if spec.provider == "anthropic":
        import anthropic

        assert spec.api_key_env is not None
        return anthropic.Anthropic(api_key=os.environ[spec.api_key_env], timeout=timeout,
                                   max_retries=0)
    import openai

    key = os.environ[spec.api_key_env] if spec.api_key_env else "ollama"
    # Retries are ours (one per failed batch, recorded), not the SDK's silent ones.
    return openai.OpenAI(api_key=key, base_url=resolve_base_url(spec), timeout=timeout,
                         max_retries=0)


def _dump(response: Any) -> dict[str, Any]:
    if isinstance(response, dict):
        return response
    dumped = response.model_dump(mode="json")
    assert isinstance(dumped, dict)
    return dumped


def _int(value: object) -> int | None:
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else None


# --------------------------------------------------------------------------- requests


def anthropic_params(spec: ModelSpec, prompt: str, *, max_tokens: int,
                     overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = {**spec.defaults, **(overrides or {})}
    params: dict[str, Any] = {
        "model": spec.model_id,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if "thinking" in settings:
        params["thinking"] = settings["thinking"]
    if "effort" in settings:
        params["output_config"] = {"effort": settings["effort"]}
    return params


def chat_params(spec: ModelSpec, prompt: str, *, max_tokens: int, seed: int | None = None,
                response_format: dict[str, Any] | None = None,
                overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = {**spec.defaults, **(overrides or {})}
    params: dict[str, Any] = {
        "model": spec.model_id,
        "messages": [{"role": "user", "content": prompt}],
    }
    # Hosted reasoning models count reasoning against max_completion_tokens; Ollama's
    # OpenAI-compatible layer documents max_tokens.
    params["max_tokens" if spec.provider == "ollama" else "max_completion_tokens"] = max_tokens
    for key in ("temperature", "reasoning_effort"):
        if key in settings:
            params[key] = settings[key]
    if seed is not None:
        params["seed"] = seed
    if response_format is not None:
        params["response_format"] = response_format
    return params


# -------------------------------------------------------------------------- responses


def parse_anthropic(spec: ModelSpec, body: dict[str, Any], request: dict[str, Any], *,
                    mode: str, latency_ms: float | None, endpoint: str | None) -> CallResult:
    text = "".join(
        block.get("text", "") for block in body.get("content", []) or []
        if isinstance(block, dict) and block.get("type") == "text"
    )
    usage = body.get("usage") or {}
    uncached = _int(usage.get("input_tokens"))
    cache_read = _int(usage.get("cache_read_input_tokens")) or 0
    cache_write = _int(usage.get("cache_creation_input_tokens")) or 0
    # Anthropic reports uncached, cache-read and cache-write input separately; the ledger
    # keeps the provider-total prompt count and the cached part of it. No cache_control is
    # sent, so cache writes should stay 0; any write is billed here at the base input rate.
    total_in = None if uncached is None else uncached + cache_read + cache_write
    output = _int(usage.get("output_tokens"))
    return CallResult(
        text=text, model=spec.model_id, provider=spec.provider, endpoint=endpoint, mode=mode,
        input_tokens=total_in, cached_input_tokens=cache_read, output_tokens=output,
        # Thinking tokens are billed inside output_tokens and not reported separately.
        reasoning_tokens=None, latency_ms=latency_ms, call_id=body.get("id"),
        finish_reason=body.get("stop_reason"), request=request, raw=body,
        cost_usd=cost_usd(spec.model_id, input_tokens=total_in, output_tokens=output,
                          cached_input_tokens=cache_read, batch=mode == "batch"),
    )


def parse_chat(spec: ModelSpec, body: dict[str, Any], request: dict[str, Any], *,
               mode: str, latency_ms: float | None, endpoint: str | None) -> CallResult:
    choices = body.get("choices") or []
    choice = choices[0] if choices else {}
    message = choice.get("message") or {}
    usage = body.get("usage") or {}
    prompt_details = usage.get("prompt_tokens_details") or {}
    completion_details = usage.get("completion_tokens_details") or {}
    input_tokens = _int(usage.get("prompt_tokens"))
    output_tokens = _int(usage.get("completion_tokens"))
    cached = _int(prompt_details.get("cached_tokens"))
    if cached is None and input_tokens is not None:
        cached = 0  # field absent = provider reports no cached prompt tokens
    priced = spec.provider != "ollama"
    return CallResult(
        text=str(message.get("content") or ""), model=spec.model_id, provider=spec.provider,
        endpoint=endpoint, mode=mode, input_tokens=input_tokens, cached_input_tokens=cached,
        output_tokens=output_tokens,
        reasoning_tokens=_int(completion_details.get("reasoning_tokens")),
        latency_ms=latency_ms, call_id=body.get("id"),
        finish_reason=choice.get("finish_reason"), request=request, raw=body,
        cost_usd=(cost_usd(spec.model_id, input_tokens=input_tokens,
                           output_tokens=output_tokens, cached_input_tokens=cached,
                           batch=mode == "batch") if priced else 0.0),
    )


# ------------------------------------------------------------------------------ calls


def _ledger_record(result: CallResult, *, purpose: str, n_requests: int = 1,
                   batch_id: str | None = None) -> dict[str, Any]:
    card = PRICES.get(result.model)
    return {
        "provider": result.provider, "model": result.model, "mode": result.mode,
        "purpose": purpose, "requests": n_requests, "batch_id": batch_id,
        "call_id": result.call_id, "input_tokens": result.input_tokens,
        "cached_input_tokens": result.cached_input_tokens,
        "output_tokens": result.output_tokens, "reasoning_tokens": result.reasoning_tokens,
        "cost_usd": result.cost_usd, "latency_ms": result.latency_ms,
        "finish_reason": result.finish_reason,
        "price_card": card.as_dict() if card else None,
    }


def call(spec: ModelSpec, prompt: str, *, purpose: str, max_tokens: int,
         seed: int | None = None, response_format: dict[str, Any] | None = None,
         overrides: dict[str, Any] | None = None, client: Any | None = None,
         ledger: Path = budget.LEDGER,
         raw_sink: Callable[[dict[str, Any]], None] | None = None) -> CallResult:
    """One synchronous call: budget check, request, raw persisted, then parsed and logged.

    ``raw_sink`` receives the raw provider body before any parsing (raw-before-parsed).
    A failed call is logged with ``cost_usd: null`` so the budget guard stops on it.
    """
    budget.check_budget(spec.provider, spec.model_id, prompt_chars=len(prompt),
                        max_output_tokens=max_tokens, path=ledger)
    api: Any = client if client is not None else build_client(spec)
    endpoint = _sanitized_endpoint(resolve_base_url(spec) or "https://api.anthropic.com")
    if spec.provider == "anthropic":
        if seed is not None:
            raise ValueError("Anthropic Messages takes no seed; pass seed=None")
        request = anthropic_params(spec, prompt, max_tokens=max_tokens, overrides=overrides)
        send: Callable[[], Any] = lambda: api.messages.create(**request)
        parse = parse_anthropic
    else:
        request = chat_params(spec, prompt, max_tokens=max_tokens, seed=seed,
                              response_format=response_format, overrides=overrides)
        send = lambda: api.chat.completions.create(**request)
        parse = parse_chat
    started = time.perf_counter()
    try:
        body = _dump(send())
    except Exception as error:
        budget.append({
            "provider": spec.provider, "model": spec.model_id, "mode": "sync",
            "purpose": purpose, "requests": 1, "error": type(error).__name__,
            "error_message": str(error)[:500],
            # A failed hosted call may still have been billed; unknown, not zero.
            "cost_usd": 0.0 if spec.provider in budget.LOCAL_PROVIDERS else None,
            "input_tokens": None, "output_tokens": None, "reasoning_tokens": None,
        }, path=ledger)
        raise
    latency = (time.perf_counter() - started) * 1000
    if raw_sink is not None:
        raw_sink(body)
    result = parse(spec, body, request, mode="sync", latency_ms=latency, endpoint=endpoint)
    budget.append(_ledger_record(result, purpose=purpose), path=ledger)
    return result


# ------------------------------------------------------------------------------ batch


@dataclass(frozen=True)
class BatchRequest:
    custom_id: str
    prompt: str
    max_tokens: int
    seed: int | None = None
    response_format: dict[str, Any] | None = None


def submit_batch(spec: ModelSpec, requests: Iterable[BatchRequest], *, purpose: str,
                 client: Any | None = None, ledger: Path = budget.LEDGER,
                 work_dir: Path | None = None) -> dict[str, Any]:
    """Submit a batch and return a JSON-able handle; cost is logged when collected."""
    if not spec.batch_supported:
        raise ValueError(f"{spec.name} has no batch API")
    items = list(requests)
    if not items:
        raise ValueError("empty batch")
    ids = [item.custom_id for item in items]
    if len(set(ids)) != len(ids):
        raise ValueError("custom_id values must be unique within a batch")
    budget.check_budget(
        spec.provider, spec.model_id, batch=True, n_requests=1, path=ledger,
        prompt_chars=sum(len(item.prompt) for item in items),
        max_output_tokens=sum(item.max_tokens for item in items),
    )
    api: Any = client if client is not None else build_client(spec)
    if spec.provider == "anthropic":
        if any(item.seed is not None for item in items):
            raise ValueError("Anthropic Messages takes no seed")
        payload = [
            {"custom_id": item.custom_id,
             "params": anthropic_params(spec, item.prompt, max_tokens=item.max_tokens)}
            for item in items
        ]
        created = _dump(api.messages.batches.create(requests=payload))
        batch_id = str(created["id"])
    else:
        lines = [
            json.dumps({
                "custom_id": item.custom_id, "method": "POST", "url": "/v1/chat/completions",
                "body": chat_params(spec, item.prompt, max_tokens=item.max_tokens,
                                    seed=item.seed, response_format=item.response_format),
            }, sort_keys=True)
            for item in items
        ]
        if work_dir is None:
            raise ValueError("OpenAI batches need work_dir for the request JSONL")
        work_dir.mkdir(parents=True, exist_ok=True)
        request_file = work_dir / f"batch-{purpose}-{len(items)}.jsonl"
        request_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with request_file.open("rb") as handle:
            uploaded = _dump(api.files.create(file=handle, purpose="batch"))
        created = _dump(api.batches.create(
            input_file_id=uploaded["id"], endpoint="/v1/chat/completions",
            completion_window="24h",
        ))
        batch_id = str(created["id"])
    return {"model": spec.name, "provider": spec.provider, "batch_id": batch_id,
            "purpose": purpose, "custom_ids": ids,
            "submitted_at": datetime.now(UTC).isoformat()}


def batch_status(spec: ModelSpec, batch_id: str, *, client: Any | None = None) -> str:
    """Normalized status: ``ended`` when results can be collected, else provider status."""
    api: Any = client if client is not None else build_client(spec)
    if spec.provider == "anthropic":
        status = str(_dump(api.messages.batches.retrieve(batch_id))["processing_status"])
        return "ended" if status == "ended" else status
    status = str(_dump(api.batches.retrieve(batch_id))["status"])
    return "ended" if status in {"completed", "failed", "expired", "cancelled"} else status


def collect_batch(spec: ModelSpec, handle: dict[str, Any], *, client: Any | None = None,
                  ledger: Path = budget.LEDGER,
                  raw_sink: Callable[[dict[str, Any]], None] | None = None,
                  ) -> dict[str, CallResult | dict[str, Any]]:
    """Fetch results keyed by custom_id (never by position); log one ledger line.

    Errored items map to their raw error object. The ledger line sums tokens and cost
    over succeeded items; cost is ``None`` if any succeeded item lacks accounting.
    """
    api: Any = client if client is not None else build_client(spec)
    batch_id = str(handle["batch_id"])
    endpoint = _sanitized_endpoint(resolve_base_url(spec) or "https://api.anthropic.com")
    raw_items: list[dict[str, Any]] = []
    if spec.provider == "anthropic":
        raw_items = [_dump(item) for item in api.messages.batches.results(batch_id)]
    else:
        batch = _dump(api.batches.retrieve(batch_id))
        for key in ("output_file_id", "error_file_id"):
            file_id = batch.get(key)
            if file_id:
                content = api.files.content(file_id)
                text = content.text if hasattr(content, "text") else str(content)
                raw_items.extend(json.loads(line) for line in text.splitlines() if line.strip())
    results: dict[str, CallResult | dict[str, Any]] = {}
    for item in raw_items:
        if raw_sink is not None:
            raw_sink(item)
        custom_id = str(item["custom_id"])
        if spec.provider == "anthropic":
            outcome = item.get("result") or {}
            if outcome.get("type") == "succeeded":
                results[custom_id] = parse_anthropic(
                    spec, outcome["message"], {"custom_id": custom_id}, mode="batch",
                    latency_ms=None, endpoint=endpoint)
            else:
                results[custom_id] = outcome
        else:
            response = item.get("response") or {}
            if response.get("status_code") == 200 and isinstance(response.get("body"), dict):
                results[custom_id] = parse_chat(
                    spec, response["body"], {"custom_id": custom_id}, mode="batch",
                    latency_ms=None, endpoint=endpoint)
            else:
                results[custom_id] = item.get("error") or response
    succeeded = [value for value in results.values() if isinstance(value, CallResult)]

    def total(attr: str) -> int | None:
        values = [getattr(value, attr) for value in succeeded]
        return None if any(v is None for v in values) else sum(values)

    costs = [value.cost_usd for value in succeeded]
    budget.append({
        "provider": spec.provider, "model": spec.model_id, "mode": "batch",
        "purpose": handle.get("purpose"), "batch_id": batch_id,
        "requests": len(handle.get("custom_ids", [])), "succeeded": len(succeeded),
        "errored": len(results) - len(succeeded),
        "missing": len(set(handle.get("custom_ids", [])) - set(results)),
        "input_tokens": total("input_tokens"),
        "cached_input_tokens": total("cached_input_tokens"),
        "output_tokens": total("output_tokens"), "reasoning_tokens": total("reasoning_tokens"),
        "cost_usd": None if any(c is None for c in costs) else round(sum(c or 0 for c in costs), 10),
        "price_card": PRICES[spec.model_id].as_dict() if spec.model_id in PRICES else None,
    }, path=ledger)
    return results
