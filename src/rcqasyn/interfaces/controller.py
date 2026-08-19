from typing import Protocol

from rcqasyn.contracts import Assessment, CandidateRecord, Decision


class DecisionController(Protocol):
    def decide(self, candidate: CandidateRecord, assessment: Assessment) -> Decision: ...
