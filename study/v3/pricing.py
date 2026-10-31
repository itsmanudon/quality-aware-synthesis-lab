"""List prices for Study v3 generators, as read from each provider's own pricing page.

Prices are USD per million tokens. They were read on 2026-10-31 (Phase 0) and must be
re-checked before the Phase 3 pilot; a changed price is a new entry, never an edit that
silently re-prices logged calls (every budget line records the price card it used).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

CHECKED_ON = "2026-10-31"


@dataclass(frozen=True)
class PriceCard:
    provider: str
    model: str
    input_per_mtok: float
    cached_input_per_mtok: float
    output_per_mtok: float
    batch_discount: float | None  # multiplier on all rates under Batch; None = no batch API
    source_url: str
    checked_on: str = CHECKED_ON
    # Claude Haiku 5.5 bills the whole request at a higher tier above this prompt length.
    long_prompt_threshold: int | None = None
    long_input_per_mtok: float | None = None
    long_cached_input_per_mtok: float | None = None
    long_output_per_mtok: float | None = None
    note: str = ""

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


_ANTHROPIC = "https://platform.claude.com/docs/en/about-claude/pricing"
_OPENAI = "https://developers.openai.com/api/docs/pricing"
_META = "https://dev.meta.ai/docs/pricing-rate-limits"

PRICES: dict[str, PriceCard] = {
    card.model: card
    for card in (
        PriceCard("anthropic", "claude-haiku-5-5", 0.10, 0.01, 0.50, 0.5, _ANTHROPIC,
                  long_prompt_threshold=100_000, long_input_per_mtok=0.50,
                  long_cached_input_per_mtok=0.05, long_output_per_mtok=2.50),
        PriceCard("anthropic", "claude-sonnet-5-5", 2.00, 0.10, 10.00, 0.5, _ANTHROPIC),
        PriceCard("openai", "gpt-6-luna", 0.10, 0.01, 0.50, 0.5, _OPENAI,
                  note="short-context (<=272K) rate; plan names 'GPT-6.1-luna', which the "
                       "pricing page does not list - gpt-6-luna pending Gate 0"),
        PriceCard("openai", "gpt-6.1-terra", 1.00, 0.05, 5.00, 0.5, _OPENAI,
                  note="short-context (<=272K) rate"),
        PriceCard("meta", "muse-spark-1.3", 1.25, 0.15, 4.25, None, _META,
                  note="standard mode (content not used for training); no batch API "
                       "documented; reasoning tokens are billed inside output tokens"),
    )
}


def cost_usd(
    model: str,
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    cached_input_tokens: int | None = 0,
    batch: bool = False,
) -> float | None:
    """Cost of one call at list price, or ``None`` when accounting is incomplete.

    ``input_tokens`` is the provider's total prompt count; ``cached_input_tokens`` is the
    part of it served from cache. Missing counts stay ``None`` (never defaulted to 0).
    """
    card = PRICES.get(model)
    if card is None or input_tokens is None or output_tokens is None or cached_input_tokens is None:
        return None
    if batch and card.batch_discount is None:
        raise ValueError(f"{model} has no batch API price")
    rate_in, rate_cached, rate_out = (
        card.input_per_mtok, card.cached_input_per_mtok, card.output_per_mtok
    )
    if card.long_prompt_threshold is not None and input_tokens > card.long_prompt_threshold:
        assert card.long_input_per_mtok is not None
        assert card.long_cached_input_per_mtok is not None
        assert card.long_output_per_mtok is not None
        rate_in, rate_cached, rate_out = (
            card.long_input_per_mtok, card.long_cached_input_per_mtok, card.long_output_per_mtok
        )
    uncached = max(input_tokens - cached_input_tokens, 0)
    total = (uncached * rate_in + cached_input_tokens * rate_cached + output_tokens * rate_out) / 1e6
    if batch:
        assert card.batch_discount is not None
        total *= card.batch_discount
    return round(total, 10)
