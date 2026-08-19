from typing import Protocol

from rcqasyn.contracts import AuditResult, DatasetState


class DatasetAuditor(Protocol):
    async def audit(self, state: DatasetState) -> AuditResult: ...
