from typing import Protocol

from rcqasyn.contracts import CandidateRecord, GenerationRequest


class Generator(Protocol):
    async def generate(self, request: GenerationRequest) -> CandidateRecord: ...
