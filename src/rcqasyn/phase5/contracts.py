from __future__ import annotations

from typing import Literal

from pydantic import Field

from rcqasyn.contracts._base import ContractModel

PARENT = "0a7005e3b36438ba52fa25dd99d9a2b54a1bf1b3"
STRATEGIES = ("source-order", "farthest-first", "coverage-greedy", "quality-coverage")


class SelectionConfig(ContractModel):
    schema_version: Literal["m7-selection-config-v1"] = "m7-selection-config-v1"
    strategy: Literal["source-order", "farthest-first", "coverage-greedy", "quality-coverage"]
    budget: int = Field(ge=0)
    policy_name: str = "combined-review"
    control_intersection: Literal["b2"] | None = None
    coverage_radius: float = Field(default=.05, ge=0, le=1, allow_inf_nan=False)
    near_duplicate_tolerance: float = Field(default=.01, ge=0, le=1, allow_inf_nan=False)
    minority_quota_fraction: float = Field(default=.5, ge=0, le=1, allow_inf_nan=False)
    seed: int = 42
