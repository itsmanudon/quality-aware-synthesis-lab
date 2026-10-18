from __future__ import annotations

import copy
import json
import os
import shutil
from pathlib import Path

import pytest

from rcqasyn.phase2.common import digest
from rcqasyn.phase2.provenance import extract_crosswalk, resolve_occurrence, validate_crosswalk

ROOT = Path(os.environ.get("P2_SOURCE_ROOT", str(Path(__file__).resolve().parents[2])))
RUN = Path("artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829")


@pytest.fixture(scope="module")
def crosswalk():
    return extract_crosswalk(ROOT, ROOT / RUN)


def test_all_200_source_occurrences_and_collisions(crosswalk):
    assert crosswalk["summary"] == {
        "occurrences": 200, "unique_occurrence_ids": 200, "unique_legacy_ids": 185,
        "unique_payloads": 181, "collision_groups": 15,
        "different_content_collision_groups": 15, "unresolved_occurrences": 0}
    first, later = crosswalk["records"][0], crosswalk["records"][40]
    assert first["legacy_candidate_id"] == later["legacy_candidate_id"]
    assert first["occurrence_id"] != later["occurrence_id"]
    assert first["payload_sha256"] != later["payload_sha256"]
    assert first["source_attempt_id_or_evidenced_locator"]["line"] == 2
    assert later["source_attempt_id_or_evidenced_locator"]["line"] == 10
    assert first["controls"]["b3"]["result"]["judge_call_id"] == "chatcmpl-424"


def test_identity_reproducible_and_content_duplicates_not_collapsed(crosswalk):
    assert extract_crosswalk(ROOT, ROOT / RUN) == crosswalk
    hashes = {}
    for row in crosswalk["records"]:
        hashes.setdefault(row["payload_sha256"], []).append(row["occurrence_id"])
    assert any(len(ids) > 1 for ids in hashes.values())
    assert all(len(ids) == len(set(ids)) for ids in hashes.values())
    with pytest.raises(ValueError, match="missing or ambiguous"):
        resolve_occurrence(crosswalk, "foreign-id")


def test_forged_crosswalk_metadata_rejected_even_after_refingerprinting(crosswalk):
    forged = copy.deepcopy(crosswalk)
    forged["records"][0]["generation_metadata"]["provider_seed"] = 123
    forged["fingerprint"] = digest({k: v for k, v in forged.items() if k != "fingerprint"})
    with pytest.raises(ValueError, match="authoritative occurrence"):
        validate_crosswalk(ROOT, forged)


@pytest.fixture
def source_copy(tmp_path):
    shutil.copytree(ROOT / "configs/datasets", tmp_path / "configs/datasets")
    shutil.copytree(ROOT / RUN, tmp_path / RUN)
    return tmp_path


@pytest.mark.parametrize("artifact", [
    "candidates_raw.jsonl", "provider_calls.jsonl", "baselines/b2/evidence.jsonl",
    "baselines/b3/judge_results.jsonl", "baselines/b3/provider_calls.jsonl"])
def test_missing_source_fails(source_copy, artifact):
    (source_copy / RUN / artifact).unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        extract_crosswalk(source_copy, source_copy / RUN)


def test_corrupted_hash_fails(source_copy):
    path = source_copy / RUN / "copying_diagnostics.json"
    value = json.loads(path.read_text())
    value["records"][0]["canonical_hash"] = "0" * 64
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="payload hash"):
        extract_crosswalk(source_copy, source_copy / RUN)


def test_duplicate_indistinguishable_trace_is_ambiguous(source_copy):
    path = source_copy / RUN / "provider_calls.jsonl"
    lines = path.read_text().splitlines()
    path.write_text("\n".join([*lines, lines[1]]) + "\n")
    with pytest.raises(ValueError, match="ambiguous"):
        extract_crosswalk(source_copy, source_copy / RUN)


@pytest.mark.parametrize("relative", ["../outside", "/absolute"])
def test_bounded_source_locator(relative):
    from rcqasyn.phase2.common import source_path
    with pytest.raises(ValueError):
        source_path(ROOT, relative)
