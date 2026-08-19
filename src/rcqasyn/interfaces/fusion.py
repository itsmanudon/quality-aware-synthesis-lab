from collections.abc import Sequence
from typing import Protocol

from rcqasyn.contracts import Assessment, CandidateRecord, Evidence


class EvidenceFusion(Protocol):
    def fuse(self, candidate: CandidateRecord, evidence: Sequence[Evidence]) -> Assessment: ...
