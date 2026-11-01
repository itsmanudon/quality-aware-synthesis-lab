"""Offline checks of the Phase 3 batch driver's cross-process guard (no provider call)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from study.v3 import phase3_llm


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
