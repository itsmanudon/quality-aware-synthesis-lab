from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from rcqasyn.contracts import JudgeResult
from rcqasyn.generation.parser import parse_judge_response
from rcqasyn.generation.provider import ProviderResponse


class _JudgeProvider(Protocol):
    def call(self, *, role: str, prompt: str, request_index: int = 0, **kwargs: object) -> ProviderResponse: ...


@dataclass(frozen=True)
class JudgeEvaluation:
    response: ProviderResponse
    result: JudgeResult | None
    error: str | None = None


class SingleLLMJudge:
    """One-provider, one-call-per-candidate judge with a static threshold.

    This service intentionally performs no calibration, fusion, ensemble voting,
    factual verification, repair, or regeneration. Malformed output is surfaced
    as an error for the caller's configured ``reject`` policy.
    """

    def __init__(self, provider: _JudgeProvider, *, threshold: float, malformed_policy: str = "reject") -> None:
        if malformed_policy != "reject":
            raise ValueError("malformed_policy currently supports only 'reject'")
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("judge threshold must be in [0, 1]")
        self.provider = provider
        self.threshold = threshold
        self.malformed_policy = malformed_policy

    def evaluate(self, *, prompt: str, run_id: str, candidate_id: str, request_index: int,
                 seed: int | None, max_tokens: int) -> JudgeEvaluation:
        response = self.provider.call(
            role="judge", prompt=prompt, request_index=request_index,
            temperature=0.0, seed=seed, max_tokens=max_tokens,
        )
        call_id = response.call_id or f"judge-{request_index}"
        try:
            result = parse_judge_response(response.response, run_id=run_id, candidate_id=candidate_id, judge_call_id=call_id)
        except ValueError as error:
            return JudgeEvaluation(response=response, result=None, error=str(error))
        return JudgeEvaluation(response=response, result=result)

    def accepts(self, result: JudgeResult) -> bool:
        verdict = result.verdict.value if hasattr(result.verdict, "value") else result.verdict
        return result.score >= self.threshold and verdict in {"pass", "warn"}


SingleLLMJudgeBaseline = SingleLLMJudge

__all__ = ["JudgeEvaluation", "SingleLLMJudge", "SingleLLMJudgeBaseline"]
