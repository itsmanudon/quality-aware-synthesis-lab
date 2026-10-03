"""A provider/admission view with no whole-population or REAL TEST lineage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .profile import DatasetProfile


@dataclass(frozen=True)
class TrainingContext:
    dataset_id: str
    domains: dict[str, tuple[str, ...]]
    numeric_summary: dict[str, dict[str, float]]
    reference_examples: tuple[dict[str, Any], ...]
    context: dict[str, Any]

    @classmethod
    def from_profile(cls, profile: DatasetProfile) -> TrainingContext:
        context = profile.to_generation_context()
        return cls(
            profile.dataset_id,
            profile.domains,
            profile.numeric_summary,
            profile.reference_examples,
            context,
        )

    def to_generation_context(self) -> dict[str, Any]:
        return self.context

    def model_dump(self, **_: Any) -> dict[str, Any]:
        return self.context
