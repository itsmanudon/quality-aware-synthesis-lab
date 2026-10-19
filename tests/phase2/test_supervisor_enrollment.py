from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from rcqasyn.phase2.approval import authenticate_review
from rcqasyn.phase2.common import read_bundle
from rcqasyn.phase2.enrollment import prepare_offline_enrollment


def test_offline_enrollment_is_pinned_public_evidence_not_authority(tmp_path, supervisor_signer):
    pin = supervisor_signer.key_id
    tip = "a" * 64
    output = supervisor_signer.directory / "offline-enrollment"
    prepare_offline_enrollment(supervisor_signer.trust, pin, tip, output)
    value = read_bundle(output)
    assert value["validation_status"] == "PENDING_PROTECTED_DEPLOYMENT"
    assert value["official"] is False and value["production_approval"] is False
    assert value["enrollment"]["expected_key_id"] == pin
    assert value["enrollment"]["expected_history_tip"] == tip
    with pytest.raises(ValueError, match="caller-selected"):
        authenticate_review(tmp_path, {}, [], {}, {}, [], tmp_path / "history", None, output)
    with pytest.raises(ValueError, match="protected supervisor enrollment"):
        authenticate_review(tmp_path, {}, [], {}, {}, [], tmp_path / "history", value)


@pytest.mark.parametrize("failure", ["pin", "history", "repository", "relative"])
def test_offline_enrollment_fails_before_output(tmp_path, supervisor_signer, failure):
    pin = "f" * 64 if failure == "pin" else supervisor_signer.key_id
    tip = "not-a-tip" if failure == "history" else "a" * 64
    output = supervisor_signer.directory / ("bad-" + failure)
    if failure == "repository":
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        output = repo / "enrollment"
    if failure == "relative":
        output = Path("relative-enrollment")
    with pytest.raises(ValueError):
        prepare_offline_enrollment(supervisor_signer.trust, pin, tip, output)
    assert not output.exists()


def test_enrollment_tool_has_no_ordinary_cli_or_environment_activation(tmp_path,
                                                                      supervisor_signer,
                                                                      monkeypatch):
    script = Path(__file__).resolve().parents[2] / "scripts/enroll_phase2_supervisor.py"
    spec = importlib.util.spec_from_file_location("disposable_enrollment_tool", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = supervisor_signer.directory / "script-enrollment"
    args = [str(script), "--public-policy", str(supervisor_signer.trust),
            "--expected-key-id", supervisor_signer.key_id,
            "--expected-history-tip", "a" * 64, "--output", str(output)]
    monkeypatch.setattr("sys.argv", args)
    with pytest.raises(SystemExit):
        module.main()
    assert not output.exists()
    monkeypatch.setattr("sys.argv", [*args, "--confirm-protected-environment"])
    module.main()
    value = read_bundle(output)
    assert value["validation_status"] == "PENDING_PROTECTED_DEPLOYMENT"
    monkeypatch.setenv("RCQASYN_SUPERVISOR_ENROLLMENT", str(output))
    with pytest.raises(ValueError, match="official approval disabled"):
        authenticate_review(tmp_path, {}, [], {}, {}, [], tmp_path / "history", value)
    # Public enrollment records contain only JSON-compatible public material.
    assert "PRIVATE KEY" not in json.dumps(value)
