"""Phase 0 smoke calls: one bounded call per declared generator.

Usage::

    python -m study.v3.smoke local            # three Ollama models (no API spend)
    python -m study.v3.smoke api              # five API models, one call each
    python -m study.v3.smoke api --only gpt-6-luna

Each call uses the M1 harness's smoke contract (the reply must be exactly ``{"ok":true}``),
is budget-checked and logged to ``budget.jsonl``. Raw bodies go to the gitignored
``runs/phase0/smoke/``; a compact summary (no raw text beyond the reply) is merged into
``report/phase0-smoke.json``. A model whose call fails is recorded as failed, not retried
here; the allowed single retry is a separate, deliberate invocation.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from study.v3 import providers

HERE = Path(__file__).resolve().parent
RAW_DIR = HERE / "runs" / "phase0" / "smoke"
SUMMARY = HERE / "report" / "phase0-smoke.json"
PROMPT = 'Return exactly this JSON object and no other text: {"ok":true}'
# Reasoning models spend hidden tokens before answering; budgets stay small and bounded.
MAX_TOKENS = {"muse-spark-1.3": 1024, "gpt-6.1-terra": 1024, "gpt-6-luna": 256}
DEFAULT_MAX_TOKENS = 64
LOCAL = ("gemma4:e4b", "qwen2.5:7b-instruct", "llama3.1:8b")
API = ("claude-haiku-5-5", "claude-sonnet-5-5", "gpt-6-luna", "gpt-6.1-terra",
       "muse-spark-1.3")


def _ollama_models() -> list[str]:
    base = providers.resolve_base_url(providers.MODELS[LOCAL[0]])
    assert base is not None
    with urllib.request.urlopen(base.rstrip("/") + "/models", timeout=10) as response:
        return [item["id"] for item in json.load(response)["data"]]


def _contract_ok(text: str) -> bool:
    try:
        return json.loads(text.strip()) == {"ok": True}
    except json.JSONDecodeError:
        return False


def run_one(name: str) -> dict[str, Any]:
    spec = providers.MODELS[name]
    raw: list[dict[str, Any]] = []
    started = datetime.now(UTC).isoformat()
    row: dict[str, Any] = {"model": name, "provider": spec.provider,
                           "model_id": spec.model_id, "started_at": started}
    try:
        result = providers.call(
            spec, PROMPT, purpose="phase0-smoke",
            max_tokens=MAX_TOKENS.get(name, DEFAULT_MAX_TOKENS),
            seed=None if spec.provider == "anthropic" else 20261031,
            raw_sink=raw.append,
            # Gemma 4 E4B (9.6 GB) exceeds the 8 GB GPU and its first load spills to CPU;
            # the default 120 s timed out on the first attempt (logged in budget.jsonl).
            client=(providers.build_client(spec, timeout=600.0)
                    if spec.provider == "ollama" else None),
        )
    # Any provider/SDK failure is a smoke result to record, not a crash.
    except Exception as error:  # noqa: BLE001
        row.update(status="failed", error=type(error).__name__, message=str(error)[:500])
        return row
    finally:
        if raw:
            RAW_DIR.mkdir(parents=True, exist_ok=True)
            safe = name.replace(":", "_")
            (RAW_DIR / f"{safe}.json").write_text(
                json.dumps(raw[0], indent=2, sort_keys=True), encoding="utf-8")
    row.update(
        status="ok" if _contract_ok(result.text) else "contract_mismatch",
        reply=result.text[:200], finish_reason=result.finish_reason,
        request={k: v for k, v in result.request.items() if k != "messages"},
        input_tokens=result.input_tokens, output_tokens=result.output_tokens,
        reasoning_tokens=result.reasoning_tokens, cost_usd=result.cost_usd,
        latency_ms=round(result.latency_ms or 0.0, 1), call_id=result.call_id,
        served_model=result.raw.get("model"),
    )
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("group", choices=("local", "api"))
    parser.add_argument("--only", nargs="*", default=None)
    args = parser.parse_args(argv)
    providers.load_env()
    names = list(args.only or (LOCAL if args.group == "local" else API))
    summary: dict[str, Any] = (
        json.loads(SUMMARY.read_text(encoding="utf-8")) if SUMMARY.exists() else {}
    )
    available: list[str] = []
    if args.group == "local":
        available = _ollama_models()
        summary["ollama_models_listed"] = sorted(available)
    for name in names:
        if args.group == "local" and name not in available:
            row = {"model": name, "provider": "ollama", "status": "unavailable",
                   "message": "model not listed by the Ollama server"}
        else:
            row = run_one(name)
        summary.setdefault("calls", {})[name] = row
        print(json.dumps({k: row.get(k) for k in ("model", "status", "reply", "input_tokens",
                                                   "output_tokens", "reasoning_tokens",
                                                   "cost_usd", "error", "message")}))
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if all(r.get("status") == "ok" for r in summary["calls"].values()
                    if r["model"] in names) else 1


if __name__ == "__main__":
    sys.exit(main())
