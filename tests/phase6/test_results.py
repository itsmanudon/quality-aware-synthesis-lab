from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

from rcqasyn.phase2.common import digest, read_bundle, write_bundle
from rcqasyn.phase3.validators import TrainEvidenceModel
from rcqasyn.phase6.audit import audit_core

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(os.environ.get("P2_SOURCE_ROOT", str(ROOT)))
BASE = ROOT / "artifacts/reports/phase6"


@pytest.fixture(scope="module")
def report():
    return read_bundle(BASE / "report-v2")


def test_actual_source_derived_audit_without_model_fit(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("M2 constructor/fitting must not run")

    monkeypatch.setattr(TrainEvidenceModel, "__init__", forbidden)
    result = audit_core(ROOT, SOURCE, BASE / "core-v1")
    assert result["status"] == "PASS"
    assert (result["parents"], result["derived"], result["constructions"]) == (601, 54, 24)
    assert result["post_evidence_replayed"] and not result["real_test_used"]


def test_real_replays_and_unavailable_denominators(report):
    a = read_bundle(BASE / "core-v1/manifest")
    b = read_bundle(BASE / "core-replay-v1/manifest")
    assert a["substantive_content_fingerprint"] == b["substantive_content_fingerprint"]
    x = read_bundle(BASE / "utility-v1")
    y = read_bundle(BASE / "utility-replay-v1")
    assert (
        x["result_content_fingerprint"] == y["result_content_fingerprint"] == digest(x["results"])
    )
    assert len(x["results"]) == 138 and x["status_counts"] == {"ok": 114, "unavailable": 24}
    assert report["registry_count"] == len(report["registry"]) == 258


def test_actual_repairs_preserve_classes_and_bounds(report):
    repairs = read_bundle(BASE / "core-v1/repairs")
    attempted = [r for r in repairs["records"] if r["post"]]
    assert len(attempted) == 54 and sum(r["proposal"]["edited_fields"] for r in attempted) == 73
    for r in attempted:
        p = r["proposal"]
        assert 0 < p["edited_fields"] <= 3
        assert all(e["absolute_change"] <= 0.5 for e in p["edits"])
        assert p["original_payload"]["class"] == p["repaired_payload"]["class"]
        assert set(p["original_payload"]) == set(p["repaired_payload"])
        assert r["post"]["decision"]["calibration_status"] == "NOT_ELIGIBLE_UNAPPROVED_LABELS"
        assert r["post"]["decision"]["human_validity"] == "NOT_ESTABLISHED"
    assert (
        repairs["original_m2_replay_exact"] and repairs["original_m2_maximum_score_difference"] == 0
    )
    assert sum(r["repair_ineligible"] for r in report["repair_summary"].values()) == 21


def test_frozen_m4_reference_membership_preserved():
    repairs = read_bundle(BASE / "core-v1/repairs")
    shadow = read_bundle(ROOT / "artifacts/reports/phase4/shadow-v1")
    for r in repairs["records"]:
        if not r["post"]:
            continue
        d = r["proposal"]["dataset_id"]
        for family, actual in r["post"]["vector"]["normalized"].items():
            reference = shadow["harmonized"]["references"][d][family]
            assert actual["reference_fingerprint"] == reference["fingerprint"]
            assert actual["reference_n"] == len(reference["members"])
            assert not any(
                m["occurrence_id"] == r["proposal"]["derived_occurrence_id"]
                for m in reference["members"]
            )


def test_fixed_budget_fairness_and_no_duplicate_parents():
    manifest = read_bundle(BASE / "core-v1/manifest")
    for row in manifest["constructions"]:
        v = read_bundle(
            BASE
            / "core-v1/constructions"
            / f"{row['dataset_id']}-{row['strategy']}-{row['condition']}"
        )
        assert (
            v["budget_requested"]
            == v["budget_achieved"]
            == {"Abalone19": 56, "Ecoli4": 70, "page-blocks0": 49}[v["dataset_id"]]
        )
        assert (
            len({r["parent_occurrence_id"] for r in v["selected_records"]}) == v["budget_achieved"]
        )
        if v["condition"] == "original":
            old = read_bundle(
                ROOT
                / f"artifacts/reports/phase5/study-v1/datasets/{v['dataset_id']}-{v['strategy']}-b{v['budget_requested']}"
            )
            assert v["metrics"] == old["metrics"]
            assert [r["occurrence_id"] for r in v["selected_records"]] == [
                r["occurrence_id"] for r in old["selected_records"]
            ]


def test_guarded_real_record_immutable(tmp_path):
    value = read_bundle(BASE / "core-v1/repairs")["records"][0]
    output = tmp_path / "record"
    write_bundle(output, value)
    write_bundle(output, value)
    with pytest.raises(FileExistsError):
        write_bundle(output, {**value, "changed": True})


def test_deterministic_report_rendering(report):
    spec = importlib.util.spec_from_file_location(
        "phase6_report", ROOT / "scripts/report_phase6.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.markdown(report) == (BASE / "report-v2/report.md").read_text()
    assert module.figures(report) == module.figures(report)
