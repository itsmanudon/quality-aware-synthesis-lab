"""Offline checks of the Phase 3 batch driver's cross-process guard (no provider call)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from study.v3 import budget, phase3_llm


def test_exclusive_lock_admits_one_holder(tmp_path: Path) -> None:
    with phase3_llm._exclusive(tmp_path) as first:
        assert first
        with phase3_llm._exclusive(tmp_path) as second:
            assert not second
    assert not (tmp_path / ".driver.lock").exists()
    with phase3_llm._exclusive(tmp_path) as again:
        assert again


def test_stale_lock_is_replaced(tmp_path: Path) -> None:
    lock = tmp_path / ".driver.lock"
    lock.write_text("1 0", encoding="utf-8")
    old = time.time() - phase3_llm.LOCK_STALE_SECONDS - 10
    os.utime(lock, (old, old))
    with phase3_llm._exclusive(tmp_path) as owned:
        assert owned


def test_submit_refuses_while_a_batch_is_uncollected(tmp_path: Path) -> None:
    model = "claude-haiku-5-5"
    root = tmp_path / model
    root.mkdir()
    (root / "batches.jsonl").write_text(json.dumps({"batch_id": "b1"}) + "\n", encoding="utf-8")
    # units=[] would otherwise return 0 pending; the in-flight batch must stop it first
    assert phase3_llm.submit(model, [], tmp_path) is None
    (root / "collected.jsonl").write_text(json.dumps({"batch_id": "b1"}) + "\n",
                                          encoding="utf-8")
    assert phase3_llm.submit(model, [], tmp_path) == 0


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_duplicate_ledger_line_counts_once(tmp_path: Path) -> None:
    ledger = tmp_path / "budget.jsonl"
    line = {"provider": "anthropic", "batch_id": "b1", "cost_usd": 0.25, "requests": 3}
    _write(ledger, [{"logged_at": "t1", **line}, {"logged_at": "t2", **line}])
    assert budget.spend("anthropic", ledger).known_usd == 0.5
    budget.mark_duplicate("anthropic", "t2", "test", path=ledger)
    assert budget.spend("anthropic", ledger).known_usd == 0.25
    assert len(budget.read_ledger(ledger)) == 3  # originals kept, one annotation added
    with pytest.raises(ValueError):
        budget.mark_duplicate("anthropic", "t2", "test", path=ledger)
    with pytest.raises(ValueError):  # the first line repeats nothing
        budget.mark_duplicate("anthropic", "t1", "test", path=ledger)


def test_state_uses_submitted_attempts_for_batch_requests(tmp_path: Path) -> None:
    failed = {"custom_id": "a", "status": "failed", "error": "x"}
    _write(tmp_path / "calls.jsonl", [failed, failed])  # one failure, collected twice
    _write(tmp_path / "submitted.jsonl", [{"custom_id": "a", "attempt": 1, "batch_id": "b"}])
    done, attempts = phase3_llm._state(tmp_path)
    assert not done and attempts == {"a": 1}
    assert len(phase3_llm._unique_calls(tmp_path)) == 1


def test_u3_eval_claims_a_unit_once_and_takes_over_dead_locks(tmp_path: Path) -> None:
    import importlib
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    u3_eval = importlib.import_module("claims")
    target = tmp_path / "unit.json"
    assert u3_eval.claim(target)
    lock = target.with_suffix(".lock")
    lock.write_text(f"{os.getppid()} 0", encoding="utf-8")  # a live process owns it
    assert not u3_eval.claim(target)
    lock.write_text("999999 0", encoding="utf-8")  # no such process: stale
    assert u3_eval.claim(target)
    target.write_text("{}", encoding="utf-8")
    lock.unlink()
    assert not u3_eval.claim(target)  # already evaluated
