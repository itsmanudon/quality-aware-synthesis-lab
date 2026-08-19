from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from rcqasyn.contracts import DatasetSpec, RunManifest, RunStatus

NOW = datetime(2025, 1, 1, tzinfo=UTC)


def _manifest(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "run_id": "run-1",
        "experiment_name": "smoke",
        "started_at": NOW,
        "status": RunStatus.RUNNING,
        "config_hash": "abc123",
        "root_seed": 42,
        "dataset": DatasetSpec(
            dataset_id="dataset-1", display_name="Dataset", task_type="classification"
        ),
        "generator": "generator-1",
        "artifact_schema_version": "1",
    }
    values.update(overrides)
    return values


def test_run_manifest_completion_and_json_round_trip() -> None:
    running = RunManifest(**_manifest())
    assert RunManifest.model_validate_json(running.model_dump_json()) == running
    completed = RunManifest(**_manifest(status=RunStatus.COMPLETED, completed_at=NOW))
    assert completed.completed_at == NOW


def test_run_manifest_rejects_inconsistent_completion() -> None:
    with pytest.raises(ValidationError):
        RunManifest(**_manifest(status=RunStatus.COMPLETED))
    with pytest.raises(ValidationError):
        RunManifest(**_manifest(completed_at=datetime(2024, 12, 31, tzinfo=UTC)))
    with pytest.raises(ValidationError):
        RunManifest(**_manifest(status=RunStatus.RUNNING, completed_at=NOW))
