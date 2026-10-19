"""Small fixed registry; no plugin service or candidate admission policy."""
from __future__ import annotations

from typing import Any

from .contracts import M2Evidence
from .validators import TrainEvidenceModel

REGISTRY = {
    "authoritative_structure": {"version": "1", "scope": "source-declared structure"},
    "local_support": {"version": "1", "scope": "TRAIN neighborhood and descriptive class support"},
    "cross_feature": {"version": "1", "scope": "TRAIN covariance relationships"},
}


def run_validators(model: TrainEvidenceModel, occurrence: dict[str, Any]) -> list[M2Evidence]:
    rows = model.score(occurrence)
    if [r.validator_family for r in rows] != list(REGISTRY):
        raise ValueError("validator output does not match the versioned registry")
    return rows
