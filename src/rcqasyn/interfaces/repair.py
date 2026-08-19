from typing import Protocol

from rcqasyn.contracts import CandidateRecord, RepairRequest


class RepairAgent(Protocol):
    async def repair(self, request: RepairRequest) -> CandidateRecord: ...
