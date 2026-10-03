"""Persist transport evidence before any parser or evaluator sees a response."""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rcqasyn.contracts.m1 import finite_tree
from rcqasyn.generation.provider import ReplayProvider
from rcqasyn.storage.artifacts import write_json


class EvidenceWriteError(Exception):
    """Durability failure must escape provider/parse rejection handlers."""


class DurableProvider:
    def __init__(self, provider: Any, directory: Path, role: str) -> None:
        self.provider = provider
        self.directory = directory
        self.role = role
        self.counter = 0
        self.recorded_response_only = isinstance(provider, ReplayProvider)

    def call(self, **kwargs: Any) -> Any:
        attempt = f"{self.role}-{self.counter}"
        self.counter += 1
        path = self.directory / "calls" / f"{attempt}.json"
        request = {
            "schema_version": "m1-call-evidence-v1",
            "attempt_id": attempt,
            "execution_id": self.directory.name,
            "requested_at": datetime.now(UTC).isoformat(),
            "request": kwargs,
        }
        try:
            response = self.provider.call(**kwargs)
        except Exception as error:
            self._persist(
                path,
                {
                    **request,
                    "status": "failed",
                    "failure_type": type(error).__name__,
                    "reason": str(error),
                },
            )
            raise
        raw = asdict(response)
        raw["created_at"] = response.created_at.isoformat()
        issues: dict[str, str] = {}
        raw = finite_tree(raw, issues=issues)
        self._persist(
            path, {**request, "status": "returned", "response": raw, "availability_issues": issues}
        )
        return replace(response, call_id=attempt, external_call_id=response.call_id)

    @staticmethod
    def _persist(path: Path, value: Any) -> None:
        try:
            write_json(path, value)
        except Exception as error:
            raise EvidenceWriteError(f"cannot durably persist call evidence: {path}") from error
