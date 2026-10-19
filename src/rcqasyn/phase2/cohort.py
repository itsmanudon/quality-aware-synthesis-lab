from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rcqasyn.storage.artifacts import read_json
from rcqasyn.storage.ownership import file_hash
from rcqasyn.utils.hashing import sha256_text

from .common import (
    csv_rows,
    digest,
    envelope,
    snapshot,
    verify_envelope,
    verify_sources,
)
from .contracts import COHORT
from .provenance import validate_crosswalk

MASTER = "artifacts/reports/p1/p1_human_review.csv"
BLIND = "artifacts/reports/human_audit/blinded"


def build_cohort(root: Path, crosswalks: list[dict[str, Any]]) -> dict[str, Any]:
    for crosswalk in crosswalks:
        validate_crosswalk(root, crosswalk)
    original = csv_rows(root / MASTER)
    selection = read_json(root / "artifacts/reports/p1/p1_human_review_manifest.json")
    population = selection.get("population_kind", "research")
    if population not in ("research", "synthetic_fixture"):
        raise ValueError("unsupported source population kind")
    old_a = csv_rows(root / BLIND / "reviewer_a_blind.csv")
    old_b = csv_rows(root / BLIND / "reviewer_b_blind.csv")
    if population == "research" and (len(original) != 120 or len(old_b) != 40):
        raise ValueError("approved historical 120/40 population is incomplete")
    if len(old_a) != len(original) or selection["row_count"] != len(original):
        raise ValueError("original review membership mismatch")
    records = [r for cw in crosswalks for r in cw["records"]]
    rows, changes, ledger = [], [], []
    for position, old in enumerate(original, 2):
        matches = [r for r in records if r["source_execution_id"] == old["run_id"]
                   and r["legacy_candidate_id"] == old["record_id"]
                   and r["payload"] == json.loads(old["candidate_json"])
                   and r["raw_response_sha256"] == sha256_text(old["raw_output"].replace("\r\n", "\n"))]
        if len(matches) != 1:
            raise ValueError("review payload does not identify exactly one source occurrence")
        occurrence = matches[0]
        if old["dataset_id"] != occurrence["dataset_id"]:
            raise ValueError("foreign dataset binding")
        fields = {**occurrence["generation_metadata"],
                  **{k: v for k, v in occurrence["diagnostics"].items()
                     if k not in ("record_id", "requested_class")}}
        fields["canonical_hash"] = occurrence["recorded_payload_sha256"]
        fields.update(
            b1_status="accepted" if occurrence["controls"]["b1"]["decision"]["accepted"]
            else "rejected",
            b2_status="accepted" if occurrence["controls"]["b2"]["decision"]["accepted"]
            else "rejected",
            b2_reason=occurrence["controls"]["b2"]["decision"]["reason"],
            b3_status="accepted" if occurrence["controls"]["b3"]["decision"]["accepted"]
            else "rejected", b3_score=occurrence["controls"]["b3"]["result"]["score"],
        )
        delta = {}
        for key, value in fields.items():
            if key not in old:
                continue
            observed = old[key]
            if key == "target_class" and value == "nan" and observed == "":
                continue  # Legacy CSV exported the diagnostic missing-class sentinel as blank.
            if value is None:
                same = observed == ""
            elif isinstance(value, bool):
                same = observed.lower() == str(value).lower()
            elif isinstance(value, (int, float)):
                same = bool(observed) and float(observed) == value
            else:
                same = observed == str(value)
            if not same:
                delta[key] = {"original": observed, "source_backed": value}
        row_id = "review-" + digest({"cohort_version": COHORT,
                                     "original_master_sha256": file_hash(root / MASTER),
                                     "position": position,
                                     "occurrence_id": occurrence["occurrence_id"]})
        row = {
            "review_row_id": row_id, "occurrence_id": occurrence["occurrence_id"],
            "legacy_candidate_id": occurrence["legacy_candidate_id"],
            "source_execution_id": occurrence["source_execution_id"],
            "source_occurrence_locator": {
                "artifact": occurrence["source_artifact"],
                "sha256": occurrence["source_artifact_sha256"],
                "ordinal": occurrence["source_occurrence_ordinal"]},
            "payload_sha256": occurrence["payload_sha256"], "dataset_id": old["dataset_id"],
            "crosswalk_version": occurrence["crosswalk_version"], "cohort_version": COHORT,
            "source_provenance_reference": occurrence["source_attempt_id_or_evidenced_locator"],
            "payload": occurrence["payload"], "original_review_row": position,
            "requested_class": occurrence["generation_metadata"]["requested_class"],
            "role": old["role"],
            "source_evidence": fields, "controls": occurrence["controls"],
        }
        rows.append(row)
        if delta:
            changes.append({"review_row_id": row_id, "original_review_row": position,
                            "original_record": old, "field_changes": delta,
                            "source_occurrence_locator": row["source_occurrence_locator"]})
        ledger.append({"review_row": position, "original_candidate_id": old["record_id"],
                       "source_run": old["run_id"],
                       "source_attempt": row["source_provenance_reference"],
                       "source_ordinal": occurrence["source_occurrence_ordinal"],
                       "canonical_payload_hash": occurrence["payload_sha256"],
                       "recorded_hash": old["canonical_hash"],
                       "binding_status": "RECOVERABLE" if delta else "VERIFIED",
                       "failure_reason": ",".join(sorted(delta)),
                       "recommended_action": "Preserve payload and source-bound metadata"
                       if delta else "Retain occurrence binding"})
    if len({r["occurrence_id"] for r in rows}) != len(rows):
        raise ValueError("duplicate selected occurrence identity")
    # Existing packet identities are aliases, not unique keys for source reconstruction.
    aliases = {}
    for packet in (old_a, old_b):
        for item in packet:
            matches = [r for r in rows if r["legacy_candidate_id"] == item["record_id"]
                       and r["dataset_id"] == item["dataset_id"]
                       and r["payload"] == json.loads(item["candidate_json"])]
            if len(matches) != 1:
                raise ValueError("packet identity is missing or ambiguous")
            row_id = matches[0]["review_row_id"]
            if item["annotation_id"] in aliases and aliases[item["annotation_id"]] != row_id:
                raise ValueError("packet alias collision")
            aliases[item["annotation_id"]] = row_id
    primary_ids = [aliases[r["annotation_id"]] for r in old_a]
    overlap_ids = [aliases[r["annotation_id"]] for r in old_b]
    if primary_ids != [r["review_row_id"] for r in rows]:
        raise ValueError("primary packet order differs from original cohort")
    if len(set(overlap_ids)) != len(overlap_ids) or not set(overlap_ids) <= set(primary_ids):
        raise ValueError("invalid fixed overlap membership")
    sources = snapshot(root, [root / MASTER,
                       root / "artifacts/reports/p1/p1_human_review_manifest.json",
                       *(root / BLIND).glob("*")])
    return envelope(COHORT, {
        "cohort_version": COHORT, "population_kind": population,
        "cohort_status": "PENDING_INDEPENDENT_VERIFICATION",
        "validation_status": "INTERNALLY_SOURCE_VALIDATED",
        "source_files": sources,
        "crosswalk_fingerprints": [c["fingerprint"] for c in crosswalks],
        "records": rows, "overlap_review_row_ids": overlap_ids, "legacy_blind_aliases": aliases,
        "reconciliation_ledger": ledger, "changes": changes,
        "review_raw_output_comparison": "Historical CSV CRLF normalized to LF for witness "
        "comparison only; original CSV bytes and source response hash are retained. "
        "Diagnostic target_class=nan was exported as blank; source sentinel retained.",
        "selection_limitations": "Recorded nonrepresentative cohort retained; historical ID-only "
        "diagnostic lookup biased strata. No resampling or population-wide inference.",
    })


def validate_cohort(root: Path, value: dict[str, Any],
                    crosswalks: list[dict[str, Any]]) -> dict[str, Any]:
    verify_envelope(value, COHORT)
    verify_sources(root, value["source_files"])
    if build_cohort(root, crosswalks) != value:
        raise ValueError("cohort differs from preserved source payload/order/evidence")
    return {"records": len(value["records"]), "overlap": len(value["overlap_review_row_ids"]),
            "payloads_preserved": True, "source_bound": True,
            "cohort_fingerprint": value["fingerprint"],
            "supervisor_approved": False}
