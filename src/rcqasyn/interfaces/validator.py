from collections.abc import Sequence
from typing import Protocol

from rcqasyn.contracts import CandidateRecord, Evidence, ValidationContext


class Validator(Protocol):
    async def validate(
        self, candidate: CandidateRecord, context: ValidationContext
    ) -> Sequence[Evidence]: ...
