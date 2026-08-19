from typing import Protocol

from rcqasyn.contracts import CandidateRecord, DatasetContribution, DatasetState


class DatasetOptimizer(Protocol):
    def evaluate_contribution(
        self, candidate: CandidateRecord, state: DatasetState
    ) -> DatasetContribution: ...
