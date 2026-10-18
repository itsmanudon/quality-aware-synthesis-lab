"""Explicitly untrusted synthetic diagnostics; never a supervisor authority provider."""
from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from .approval import _verify_review_signature, read_approval_json
from .common import envelope, write_bundle
from .contracts import SupervisorTrust


@dataclass(frozen=True)
class FixtureTrustAnchor:
    """A test expectation, not a security boundary against in-process Python code."""

    policy: Path
    expected_key_id: str
    expected_history_tip: str


def diagnose_fixture_review(root: Path, cohort: dict[str, Any],
                            crosswalks: list[dict[str, Any]], protocol: dict[str, Any],
                            approval: dict[str, Any], proposals: list[dict[str, Any]],
                            history: Path, attestation: dict[str, Any] | None,
                            anchor: FixtureTrustAnchor | None) -> dict[str, Any]:
    if cohort.get("population_kind") != "synthetic_fixture":
        raise ValueError("fixture diagnostics refuse research populations")
    if anchor is None:
        raise ValueError("explicit isolated fixture anchor required; no production trust fallback")
    if not isinstance(anchor, FixtureTrustAnchor):
        raise TypeError("fixture anchor must be an explicit test expectation")
    path = anchor.policy
    if not path.is_absolute():
        raise ValueError("fixture policy must be an absolute external path")
    resolved = path.resolve(strict=True)
    if (any(resolved.is_relative_to(p.resolve()) for p in (root, history.parent))
            or any((p / ".git").exists() for p in resolved.parents)):
        raise ValueError("fixture policy must be outside repositories/review data")
    trust = SupervisorTrust.model_validate_json(json.dumps(read_approval_json(resolved)))
    key_id = sha256(bytes.fromhex(trust.public_key_hex)).hexdigest()
    if key_id != trust.key_id or trust.key_id != anchor.expected_key_id:
        raise ValueError("fixture key differs from independently selected test pin")
    if len(anchor.expected_history_tip) != 64:
        raise ValueError("explicit retained fixture history tip required")
    return _verify_review_signature(root, cohort, crosswalks, protocol, approval,
                                     proposals, history, attestation, trust,
                                     anchor.expected_history_tip)


def import_fixture_diagnostic(root: Path, cohort: dict[str, Any],
                              crosswalks: list[dict[str, Any]], protocol: dict[str, Any],
                              approval: dict[str, Any], proposals: list[dict[str, Any]],
                              history: Path, attestation: dict[str, Any] | None,
                              anchor: FixtureTrustAnchor | None, output: Path) -> Path:
    from rcqasyn.storage.ownership import bundle_lock

    with bundle_lock(history):
        value = diagnose_fixture_review(root, cohort, crosswalks, protocol, approval,
                                         proposals, history, attestation, anchor)
        return write_bundle(output, envelope("untrusted-fixture-review-diagnostic-v1", value))
