"""Provider adapters, prompt rendering, and strict candidate parsing."""

from .parser import ParsedCandidates, parse_generation_response, parse_judge_response
from .prompts import PromptTemplate, load_prompt
from .provider import (
    OpenAICompatibleGenerator,
    OpenAICompatibleProvider,
    ProviderResponse,
    ReplayGenerator,
    ReplayProvider,
)

__all__ = [
    "OpenAICompatibleGenerator",
    "OpenAICompatibleProvider",
    "ParsedCandidates",
    "PromptTemplate",
    "ProviderResponse",
    "ReplayGenerator",
    "ReplayProvider",
    "load_prompt",
    "parse_generation_response",
    "parse_judge_response",
]
