"""Prepare public enrollment evidence offline; never auto-enable production approval."""
from __future__ import annotations

import json
from pathlib import Path

from .approval import read_approval_json
from .common import envelope, write_bundle
from .contracts import SupervisorEnrollment


def prepare_offline_enrollment(policy: Path, expected_key_id: str,
                               expected_history_tip: str, output: Path) -> Path:
    """Run only with public data in the supervisor's separately protected context.

    OS/process isolation and installed authority integration are separate requirements.
    This record cannot enable the fail-closed production consumer in this build.
    """
    destination = output.resolve()
    if not output.is_absolute() or ".." in output.parts:
        raise ValueError("offline enrollment destination must be an absolute external path")
    if any((parent / ".git").exists() for parent in (destination, *destination.parents)):
        raise ValueError("offline enrollment must stay outside repositories")
    value = SupervisorEnrollment.model_validate_json(json.dumps({
        "trust": read_approval_json(policy), "expected_key_id": expected_key_id,
        "expected_history_tip": expected_history_tip}))
    return write_bundle(output, envelope("offline-supervisor-enrollment-record-v1", {
        "enrollment": value.model_dump(mode="json"), "official": False,
        "production_approval": False, "validation_status": "PENDING_PROTECTED_DEPLOYMENT"}))
