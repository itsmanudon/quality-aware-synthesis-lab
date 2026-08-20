# pyright: reportOptionalMemberAccess=false
from __future__ import annotations

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
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class ReplayProvider:
    def __init__(self, fixture_path: Path, *, model: str = "replay", provider: str = "replay") -> None:
        self.fixture_path = Path(fixture_path)
        raw = json.loads(self.fixture_path.read_text(encoding="utf-8"))
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

    def call(self, *, role: str, prompt: str, temperature: float = 0.0, seed: int | None = None, max_tokens: int = 2048, **_: object) -> ProviderResponse:
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
        return ProviderResponse(
            response=str(text), provider="openai_compatible", model=self.model, endpoint=_sanitized_endpoint(self.base_url),
            input_tokens=_int_or_none(usage.get("prompt_tokens")), output_tokens=_int_or_none(usage.get("completion_tokens")),
            total_tokens=_int_or_none(usage.get("total_tokens")), latency_ms=latency,
            call_id=str(body.get("id", "provider-call")), created_at=datetime.now(UTC),
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
