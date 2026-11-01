"""Append-only API budget ledger (``study/v3/budget.jsonl``) and the 80% stop rule.

Every provider call or collected batch appends one line. The guard refuses a new call when
the provider's logged spend plus that call's worst-case cost would pass 80% of the cap, or
when any earlier line for the provider has unknown cost (spend can then not be bounded).
Crossing 80% is a user gate (CLAUDE.md), so the guard raises instead of warning.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from study.v3.pricing import PRICES

LEDGER = Path(__file__).resolve().parent / "budget.jsonl"
CAPS_USD: dict[str, float] = {"anthropic": 5.0, "openai": 4.0, "meta": 140.0}
STOP_FRACTION = 0.8
LOCAL_PROVIDERS = frozenset({"ollama"})


class BudgetStop(RuntimeError):
    """Raised before a call that could cross the 80% gate; the user must approve."""


@dataclass(frozen=True)
class Spend:
    provider: str
    known_usd: float
    unknown_cost_lines: int
    cap_usd: float | None

    @property
    def stop_at_usd(self) -> float | None:
        return None if self.cap_usd is None else self.cap_usd * STOP_FRACTION


def read_ledger(path: Path = LEDGER) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def spend(provider: str, path: Path = LEDGER) -> Spend:
    """Known spend; an unknown-cost line counts at its reconciled upper bound, if any.

    A failed call keeps ``cost_usd: null`` (missing accounting is never 0). A later
    ``reconcile`` line may bound it from above (worst case at list price); the bound is
    added to the known spend, so the 80% rule stays conservative.
    """
    rows = [r for r in read_ledger(path) if r.get("provider") == provider]
    bounds = {r["reconciles"]: float(r["cost_usd_upper_bound"]) for r in rows
              if r.get("kind") == "reconciliation"}
    repeated = {r["repeats"] for r in rows if r.get("kind") == "duplicate_line"}
    known = 0.0
    unknown = 0
    for row in rows:
        if row.get("kind") in ("reconciliation", "duplicate_line"):
            continue
        if row.get("logged_at") in repeated:
            continue
        cost = row.get("cost_usd")
        if cost is None:
            if row.get("logged_at") in bounds:
                known += bounds[row["logged_at"]]
            else:
                unknown += 1
        else:
            known += float(cost)
    return Spend(provider, round(known, 10), unknown, CAPS_USD.get(provider))


def reconcile(provider: str, logged_at: str, model: str, *, prompt_chars: int,
              max_output_tokens: int, basis: str, path: Path = LEDGER) -> dict[str, Any]:
    """Bound an unknown-cost line by its worst case; the original line is left unchanged."""
    targets = [r for r in read_ledger(path) if r.get("provider") == provider
               and r.get("logged_at") == logged_at and r.get("cost_usd") is None]
    if len(targets) != 1:
        raise ValueError("reconcile needs exactly one unknown-cost line with that timestamp")
    bound = worst_case_cost(model, prompt_chars=prompt_chars,
                            max_output_tokens=max_output_tokens)
    return append({"kind": "reconciliation", "provider": provider, "model": model,
                   "reconciles": logged_at, "cost_usd_upper_bound": round(bound, 10),
                   "basis": basis}, path=path)


def mark_duplicate(provider: str, logged_at: str, basis: str,
                   path: Path = LEDGER) -> dict[str, Any]:
    """Annotate a ledger line that repeats an earlier one (the same batch logged twice).

    Both original lines are kept. ``spend`` skips the annotated repeat. Only a line equal to
    an earlier one in every field except ``logged_at`` qualifies, and only one with a batch id.
    """
    rows = [r for r in read_ledger(path) if r.get("provider") == provider]
    targets = [i for i, r in enumerate(rows) if r.get("logged_at") == logged_at]
    if len(targets) != 1:
        raise ValueError("mark_duplicate needs exactly one line with that timestamp")
    line = {k: v for k, v in rows[targets[0]].items() if k != "logged_at"}
    if not line.get("batch_id"):
        raise ValueError("only a batch line can repeat")
    earlier = [r for r in rows[:targets[0]]
               if {k: v for k, v in r.items() if k != "logged_at"} == line]
    if not earlier:
        raise ValueError("no earlier identical line; not a duplicate")
    if any(r.get("kind") == "duplicate_line" and r.get("repeats") == logged_at for r in rows):
        raise ValueError("already marked")
    return append({"kind": "duplicate_line", "provider": provider, "repeats": logged_at,
                   "first_logged_at": earlier[0]["logged_at"], "basis": basis}, path=path)


def worst_case_cost(model: str, *, prompt_chars: int, max_output_tokens: int,
                    batch: bool = False, n_requests: int = 1) -> float:
    """Upper bound for a call: one token per prompt character, full output budget."""
    card = PRICES[model]
    rate_in = card.long_input_per_mtok or card.input_per_mtok
    rate_out = card.long_output_per_mtok or card.output_per_mtok
    total = (prompt_chars * rate_in + max_output_tokens * rate_out) / 1e6 * n_requests
    if batch and card.batch_discount is not None:
        total *= card.batch_discount
    return total


def check_budget(provider: str, model: str, *, prompt_chars: int, max_output_tokens: int,
                 batch: bool = False, n_requests: int = 1, path: Path = LEDGER) -> None:
    if provider in LOCAL_PROVIDERS:
        return
    current = spend(provider, path)
    if current.cap_usd is None:
        raise BudgetStop(f"no declared budget cap for provider {provider!r}")
    if current.unknown_cost_lines:
        raise BudgetStop(
            f"{provider}: {current.unknown_cost_lines} ledger line(s) have unknown cost; "
            "spend cannot be bounded until they are reconciled"
        )
    projected = current.known_usd + worst_case_cost(
        model, prompt_chars=prompt_chars, max_output_tokens=max_output_tokens,
        batch=batch, n_requests=n_requests,
    )
    assert current.stop_at_usd is not None
    if projected > current.stop_at_usd:
        raise BudgetStop(
            f"{provider}: projected spend ${projected:.4f} would pass 80% of the "
            f"${current.cap_usd:.2f} cap; stop and ask the user"
        )


def append(record: dict[str, Any], path: Path = LEDGER) -> dict[str, Any]:
    row = {"logged_at": datetime.now(UTC).isoformat(), **record}
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
        handle.flush()
    return row
