# pyright: reportOptionalMemberAccess=false
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit


@dataclass(frozen=True)
class ProviderResponse:
    response: str
    provider: str
    model: str
    endpoint: str | None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: float | None = None
    replay_source_id: str | None = None
    cost_usd: float | None = None
    call_id: str | None = None
    external_call_id: str | None = None
    finish_reason: str | None = None
    response_format: dict[str, Any] | None = None
    reasoning_effort: str | None = None
    reasoning_fields_present: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class ProviderReadiness:
    ready: bool
    reason: str


def provider_readiness(config: Any) -> ProviderReadiness:
    """Validate provider configuration without making a provider request.

    Loopback/local-model examples are intentionally treated as placeholders.
    A real local deployment can opt in only after replacing the placeholder
    model/base URL and supplying the configured key environment variable.
    """

    kind = str(getattr(config, "kind", "")).lower()
    if kind in {"replay", "fixture"}:
        return ProviderReadiness(True, "replay provider; no network call")
    if kind not in {"openai", "openai_compatible"}:
        return ProviderReadiness(False, f"unsupported provider kind {kind!r}")
    base_url = str(getattr(config, "base_url", "") or "").strip()
    model = str(getattr(config, "model", "") or "").strip()
    api_key_env = getattr(config, "api_key_env", None)
    if not base_url:
        return ProviderReadiness(False, "base_url is missing")
    if not model:
        return ProviderReadiness(False, "model is missing")
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ProviderReadiness(False, "base_url must be an absolute HTTP(S) URL")
    local_host = parsed.hostname.lower() in {"127.0.0.1", "localhost", "::1"} or parsed.hostname.endswith(".local")
    placeholder_model = model.lower() in {"local-model", "local-judge-model", "replay", "placeholder"}
    if local_host and placeholder_model:
        return ProviderReadiness(False, "loopback endpoint and placeholder model are not real provider configuration")
    if not api_key_env:
        return ProviderReadiness(False, "api_key_env is missing")
    if not os.environ.get(str(api_key_env)):
        return ProviderReadiness(False, f"configured API key environment variable is missing: {api_key_env}")
    return ProviderReadiness(True, "base URL, model, and configured key environment variable are present")


class ReplayProvider:
    def __init__(self, fixture_path: Path, *, model: str = "replay", provider: str = "replay") -> None:
        self.fixture_path = Path(fixture_path)
        fixture_bytes = self.fixture_path.read_bytes()
        self.fixture_sha256 = hashlib.sha256(fixture_bytes).hexdigest()
        raw = json.loads(fixture_bytes.decode("utf-8"))
        if not isinstance(raw, dict):
            raise TypeError("replay fixture must be a JSON object")
        self._queues: dict[str, list[dict[str, Any]]] = {}
        for role in ("generation", "judge"):
            values = raw.get(role, [])
            if not isinstance(values, list):
                raise TypeError(f"replay fixture {role!r} must be an array")
            self._queues[role] = [item for item in values if isinstance(item, dict)]
        self.model = model
        self.provider = provider

    def call(self, *, role: str, prompt: str, request_index: int = 0, **_: object) -> ProviderResponse:
        queue = self._queues.get(role)
        if queue is None:
            raise ValueError(f"unsupported replay role: {role}")
        if not queue:
            raise RuntimeError(f"replay fixture exhausted for {role}")
        item = queue.pop(0)
        usage = item.get("usage") if isinstance(item.get("usage"), dict) else {}
        response = item.get("response")
        if not isinstance(response, str):
            response = json.dumps(response, ensure_ascii=False)
        return ProviderResponse(
            response=response,
            provider=self.provider,
            model=str(item.get("model", self.model)),
            endpoint=None,
            input_tokens=_int_or_none(usage.get("input_tokens")),
            output_tokens=_int_or_none(usage.get("output_tokens")),
            total_tokens=_int_or_none(usage.get("total_tokens")),
            latency_ms=float(item.get("latency_ms", 0.0)),
            replay_source_id=str(item.get("source_id", f"{role}-{request_index}")),
            cost_usd=None,
            call_id=str(item.get("call_id", f"replay-{role}-{request_index}")),
        )


class ReplayGenerator(ReplayProvider):
    """Concrete generation-facing adapter over :class:`ReplayProvider`.

    The provider retains a role-aware ``call`` API because M1 traces batched
    calls rather than the legacy one-record async generator protocol.
    """

    def generate_batch(self, *, prompt: str, request_index: int = 0, temperature: float = 0.0,
                       seed: int | None = None, max_tokens: int = 2048) -> ProviderResponse:
        return self.call(role="generation", prompt=prompt, request_index=request_index,
                         temperature=temperature, seed=seed, max_tokens=max_tokens)


class OpenAICompatibleProvider:
    """Minimal optional HTTP adapter; endpoint and key name are always configuration-driven."""

    def __init__(self, *, base_url: str, model: str, api_key_env: str | None = None, timeout: float = 60.0) -> None:
        if not base_url:
            raise ValueError("base_url is required")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key_env = api_key_env
        self.timeout = timeout

    def call(
        self, *, role: str, prompt: str, temperature: float = 0.0, seed: int | None = None,
        max_tokens: int = 2048, response_format: dict[str, Any] | None = None,
        reasoning_effort: str | None = None, **_: object,
    ) -> ProviderResponse:
        key = os.environ.get(self.api_key_env) if self.api_key_env else None
        if self.api_key_env and not key:
            raise RuntimeError(f"provider API key environment variable is missing: {self.api_key_env}")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if seed is not None:
            payload["seed"] = seed
        if response_format is not None:
            payload["response_format"] = response_format
        if reasoning_effort is not None:
            payload["reasoning_effort"] = reasoning_effort
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {key}"} if key else {})},
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
            raise RuntimeError(f"provider call failed for {_sanitized_endpoint(self.base_url)}: {error}") from error
        latency = (time.perf_counter() - started) * 1000
        try:
            text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError("provider response had no choices[0].message.content") from error
        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        choice = body["choices"][0]
        message = choice["message"]
        reasoning_fields = tuple(
            field for field in ("reasoning", "reasoning_content", "thinking")
            if field in message
        )
        return ProviderResponse(
            response=str(text), provider="openai_compatible", model=self.model, endpoint=_sanitized_endpoint(self.base_url),
            input_tokens=_int_or_none(usage.get("prompt_tokens")), output_tokens=_int_or_none(usage.get("completion_tokens")),
            total_tokens=_int_or_none(usage.get("total_tokens")), latency_ms=latency,
            call_id=str(body.get("id", "provider-call")), finish_reason=str(choice.get("finish_reason")) if choice.get("finish_reason") is not None else None,
            response_format=response_format, reasoning_effort=reasoning_effort,
            reasoning_fields_present=reasoning_fields, created_at=datetime.now(UTC),
        )


class OpenAICompatibleGenerator(OpenAICompatibleProvider):
    """Concrete generation adapter using the shared OpenAI-compatible provider."""

    def generate_batch(self, *, prompt: str, request_index: int = 0, temperature: float = 0.0,
                       seed: int | None = None, max_tokens: int = 2048) -> ProviderResponse:
        return self.call(role="generation", prompt=prompt, request_index=request_index,
                         temperature=temperature, seed=seed, max_tokens=max_tokens)


def _int_or_none(value: object) -> int | None:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _sanitized_endpoint(value: str) -> str:
    """Keep endpoint identity; query strings/fragments may contain secrets."""
    parts = urlsplit(value)
    if not (parts.scheme or parts.netloc):
        return value.split("?", 1)[0].split("#", 1)[0]
    # urlsplit().netloc may contain userinfo; retain only host and port.
    try:
        hostname = parts.hostname or ""
        host = f"[{hostname}]" if ":" in hostname and not hostname.startswith("[") else hostname
        netloc = host
        if parts.port is not None:
            netloc = f"{netloc}:{parts.port}"
    except ValueError:
        netloc = ""
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))
