"""Offline tests for Study v3 adapters: recorded response shapes, fake clients, no network."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from study.v3 import budget, providers
from study.v3.pricing import cost_usd

# Response bodies in the shapes documented by each provider (Anthropic Messages; OpenAI
# Chat Completions, which Meta's Model API and Ollama mirror).
ANTHROPIC_BODY = {
    "id": "msg_fixture", "type": "message", "role": "assistant", "model": "claude-haiku-5-5",
    "content": [{"type": "text", "text": '{"ok":true}'}], "stop_reason": "end_turn",
    "usage": {"input_tokens": 20, "output_tokens": 7, "cache_read_input_tokens": 0,
              "cache_creation_input_tokens": 0},
}
CHAT_BODY = {
    "id": "chatcmpl_fixture", "object": "chat.completion", "model": "muse-spark-1.3",
    "choices": [{"index": 0, "finish_reason": "stop",
                 "message": {"role": "assistant", "content": '{"ok":true}'}}],
    "usage": {"prompt_tokens": 30, "completion_tokens": 50, "total_tokens": 80,
              "prompt_tokens_details": {"cached_tokens": 10},
              "completion_tokens_details": {"reasoning_tokens": 40}},
}


class FakeAnthropic:
    def __init__(self, body: dict[str, Any] | Exception) -> None:
        self.sent: list[dict[str, Any]] = []
        self.body = body
        batches = SimpleNamespace(
            create=lambda requests: self._record("batch", requests) or {"id": "msgbatch_1"},
            retrieve=lambda batch_id: {"id": batch_id, "processing_status": "ended"},
            results=lambda batch_id: [
                {"custom_id": "b", "result": {"type": "succeeded", "message": ANTHROPIC_BODY}},
                {"custom_id": "a", "result": {"type": "errored",
                                              "error": {"type": "overloaded_error"}}},
            ],
        )
        self.messages = SimpleNamespace(create=self._create, batches=batches)

    def _record(self, kind: str, payload: Any) -> None:
        self.sent.append({kind: payload})

    def _create(self, **params: Any) -> dict[str, Any]:
        self.sent.append(params)
        if isinstance(self.body, Exception):
            raise self.body
        return self.body


class FakeChat:
    def __init__(self, body: dict[str, Any]) -> None:
        self.sent: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.body = body

    def _create(self, **params: Any) -> dict[str, Any]:
        self.sent.append(params)
        return self.body


@pytest.fixture()
def ledger(tmp_path: Path) -> Path:
    return tmp_path / "budget.jsonl"


def test_registry_declares_the_eight_generators() -> None:
    assert len(providers.MODELS) == 8
    by_provider = {spec.provider for spec in providers.MODELS.values()}
    assert by_provider == {"anthropic", "openai", "meta", "ollama"}
    # Meta must use the standard (non-training) model, never the contributor variant.
    assert providers.MODELS["muse-spark-1.3"].model_id == "muse-spark-1.3"
    assert all("contributor" not in s.model_id for s in providers.MODELS.values())


def test_anthropic_call_logs_tokens_and_cost(ledger: Path) -> None:
    spec = providers.MODELS["claude-haiku-5-5"]
    client = FakeAnthropic(ANTHROPIC_BODY)
    raws: list[dict[str, Any]] = []
    result = providers.call(spec, "hi", purpose="test", max_tokens=32, client=client,
                            ledger=ledger, raw_sink=raws.append)
    assert result.text == '{"ok":true}'
    assert raws == [ANTHROPIC_BODY]
    sent = client.sent[0]
    assert "temperature" not in sent and "seed" not in sent
    assert sent["thinking"] == {"type": "disabled"}
    assert sent["output_config"] == {"effort": "low"}
    row = budget.read_ledger(ledger)[0]
    assert row["provider"] == "anthropic" and row["input_tokens"] == 20
    assert row["cost_usd"] == pytest.approx((20 * 0.10 + 7 * 0.50) / 1e6)
    assert row["reasoning_tokens"] is None


def test_anthropic_rejects_seed(ledger: Path) -> None:
    with pytest.raises(ValueError, match="no seed"):
        providers.call(providers.MODELS["claude-haiku-5-5"], "hi", purpose="t",
                       max_tokens=8, seed=1, client=FakeAnthropic(ANTHROPIC_BODY),
                       ledger=ledger)


def test_chat_call_records_reasoning_and_cached_tokens(ledger: Path) -> None:
    spec = providers.MODELS["muse-spark-1.3"]
    client = FakeChat(CHAT_BODY)
    result = providers.call(spec, "hi", purpose="test", max_tokens=512, seed=7,
                            client=client, ledger=ledger)
    sent = client.sent[0]
    assert sent["max_completion_tokens"] == 512 and "max_tokens" not in sent
    assert sent["reasoning_effort"] == "minimal" and sent["seed"] == 7
    assert result.reasoning_tokens == 40 and result.cached_input_tokens == 10
    expected = (20 * 1.25 + 10 * 0.15 + 50 * 4.25) / 1e6
    assert budget.read_ledger(ledger)[0]["cost_usd"] == pytest.approx(expected)


def test_ollama_is_free_and_uses_max_tokens(ledger: Path) -> None:
    spec = providers.MODELS["llama3.1:8b"]
    client = FakeChat({**CHAT_BODY, "usage": {"prompt_tokens": 5, "completion_tokens": 3}})
    result = providers.call(spec, "hi", purpose="t", max_tokens=16, seed=3,
                            client=client, ledger=ledger)
    assert client.sent[0]["max_tokens"] == 16 and client.sent[0]["temperature"] == 0.7
    assert result.cost_usd == 0.0 and result.reasoning_tokens is None


def test_missing_usage_keeps_cost_null_and_stops_budget(ledger: Path) -> None:
    spec = providers.MODELS["gpt-6-luna"]
    body = {**CHAT_BODY, "usage": {}}
    result = providers.call(spec, "hi", purpose="t", max_tokens=8,
                            client=FakeChat(body), ledger=ledger)
    assert result.cost_usd is None and result.input_tokens is None
    with pytest.raises(budget.BudgetStop, match="unknown cost"):
        budget.check_budget("openai", "gpt-6-luna", prompt_chars=2, max_output_tokens=8,
                            path=ledger)


def test_failed_hosted_call_is_logged_with_unknown_cost(ledger: Path) -> None:
    spec = providers.MODELS["claude-haiku-5-5"]
    with pytest.raises(RuntimeError):
        providers.call(spec, "hi", purpose="t", max_tokens=8,
                       client=FakeAnthropic(RuntimeError("boom")), ledger=ledger)
    row = budget.read_ledger(ledger)[0]
    assert row["error"] == "RuntimeError" and row["cost_usd"] is None


def test_budget_guard_stops_before_eighty_percent(ledger: Path) -> None:
    budget.append({"provider": "openai", "model": "gpt-6-luna", "cost_usd": 3.19}, path=ledger)
    budget.check_budget("openai", "gpt-6-luna", prompt_chars=10, max_output_tokens=10,
                        path=ledger)
    with pytest.raises(budget.BudgetStop, match="80%"):
        budget.check_budget("openai", "gpt-6-luna", prompt_chars=10,
                            max_output_tokens=50_000, path=ledger)
    budget.check_budget("ollama", "llama3.1:8b", prompt_chars=10**9, max_output_tokens=10**9,
                        path=ledger)


def test_haiku_long_prompt_tier_and_batch_discount() -> None:
    short = cost_usd("claude-haiku-5-5", input_tokens=1000, output_tokens=100)
    assert short == pytest.approx((1000 * 0.10 + 100 * 0.50) / 1e6)
    long = cost_usd("claude-haiku-5-5", input_tokens=200_000, output_tokens=100)
    assert long == pytest.approx((200_000 * 0.50 + 100 * 2.50) / 1e6)
    batch = cost_usd("claude-haiku-5-5", input_tokens=1000, output_tokens=100, batch=True)
    assert batch == pytest.approx(short / 2)  # type: ignore[operator]
    assert cost_usd("claude-haiku-5-5", input_tokens=None, output_tokens=1) is None
    with pytest.raises(ValueError, match="no batch"):
        cost_usd("muse-spark-1.3", input_tokens=1, output_tokens=1, batch=True)


def test_anthropic_batch_round_trip_keys_by_custom_id(ledger: Path) -> None:
    spec = providers.MODELS["claude-haiku-5-5"]
    client = FakeAnthropic(ANTHROPIC_BODY)
    handle = providers.submit_batch(
        spec, [providers.BatchRequest("a", "x", 16), providers.BatchRequest("b", "y", 16)],
        purpose="t", client=client, ledger=ledger)
    assert handle["batch_id"] == "msgbatch_1"
    assert providers.batch_status(spec, "msgbatch_1", client=client) == "ended"
    results = providers.collect_batch(spec, handle, client=client, ledger=ledger)
    assert isinstance(results["b"], providers.CallResult)
    assert results["b"].mode == "batch"
    assert not isinstance(results["a"], providers.CallResult)
    row = budget.read_ledger(ledger)[-1]
    assert (row["succeeded"], row["errored"], row["missing"]) == (1, 1, 0)
    assert row["cost_usd"] == pytest.approx((20 * 0.10 + 7 * 0.50) / 1e6 / 2)


def test_openai_batch_writes_jsonl_and_parses_output(ledger: Path, tmp_path: Path) -> None:
    spec = providers.MODELS["gpt-6-luna"]
    output = json.dumps({"custom_id": "a", "response": {"status_code": 200, "body": CHAT_BODY}})
    uploads: list[bytes] = []
    client = SimpleNamespace(
        files=SimpleNamespace(
            create=lambda file, purpose: uploads.append(file.read()) or {"id": "file_in"},
            content=lambda file_id: SimpleNamespace(text=output + "\n"),
        ),
        batches=SimpleNamespace(
            create=lambda **kw: {"id": "batch_1", **kw},
            retrieve=lambda batch_id: {"id": batch_id, "status": "completed",
                                       "output_file_id": "file_out", "error_file_id": None},
        ),
    )
    handle = providers.submit_batch(spec, [providers.BatchRequest("a", "x", 16, seed=5)],
                                    purpose="t", client=client, ledger=ledger,
                                    work_dir=tmp_path)
    line = json.loads(uploads[0].decode().strip())
    assert line["url"] == "/v1/chat/completions" and line["body"]["seed"] == 5
    assert providers.batch_status(spec, "batch_1", client=client) == "ended"
    results = providers.collect_batch(spec, handle, client=client, ledger=ledger)
    assert isinstance(results["a"], providers.CallResult)
    assert results["a"].reasoning_tokens == 40


def test_gate_refuses_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(providers.ProviderNotReady, match="OPENAI_API_KEY"):
        providers.require_ready(providers.MODELS["gpt-6-luna"])


def test_meta_has_no_batch(ledger: Path) -> None:
    with pytest.raises(ValueError, match="no batch"):
        providers.submit_batch(providers.MODELS["muse-spark-1.3"],
                               [providers.BatchRequest("a", "x", 8)], purpose="t",
                               client=object(), ledger=ledger)
