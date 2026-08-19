from __future__ import annotations

import uuid


def random_id(prefix: str = "id") -> str:
    """Return a readable, non-deterministic UUID4 identifier."""
    if not prefix.strip():
        raise ValueError("prefix must be non-empty")
    return f"{prefix.strip()}-{uuid.uuid4()}"


def content_id(content: bytes | str, prefix: str = "content") -> str:
    import hashlib

    if not prefix.strip():
        raise ValueError("prefix must be non-empty")
    payload = content.encode("utf-8") if isinstance(content, str) else content
    return f"{prefix.strip()}-{hashlib.sha256(payload).hexdigest()}"


def run_id() -> str:
    return random_id("run")


def record_id() -> str:
    return random_id("record")


def evidence_id() -> str:
    return random_id("evidence")


def assessment_id() -> str:
    return random_id("assessment")


def decision_id() -> str:
    return random_id("decision")


new_run_id = run_id
new_record_id = record_id
new_evidence_id = evidence_id
new_assessment_id = assessment_id
new_decision_id = decision_id
