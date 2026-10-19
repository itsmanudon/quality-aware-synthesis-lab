from __future__ import annotations

from pathlib import Path
from typing import Any

from rcqasyn.phase2.common import digest, read_bundle, verify_envelope
from rcqasyn.phase5.geometry import complete_record
from rcqasyn.phase5.workflow import load_context

from .objective import reevaluate, restore_model
from .repair import propose_repair


def audit_core(root: Path, source: Path, core: Path) -> dict[str, Any]:
    """Check recorded derived/source identities and frozen evidence, without refitting."""
    ctx = load_context(root, source)
    manifest = read_bundle(core / "manifest")
    repairs = read_bundle(core / "repairs")
    verify_envelope(manifest, "m6-core-manifest-v1")
    verify_envelope(repairs, "m6-repair-study-v1")
    if (
        repairs["fingerprint"] != manifest["repair_bundle_fingerprint"]
        or digest(repairs["records"]) != repairs["record_content_fingerprint"]
    ):
        raise ValueError("repair registry contradiction")
    raw = {o["occurrence_id"]: o for g in ctx.geometries.values() for o in g.occurrences}
    if len(repairs["records"]) != len(raw):
        raise ValueError("repair registry population mismatch")
    structural = {
        r["occurrence_id"]: r
        for r in ctx.m2["evidence"]
        if r["validator_family"] == "authoritative_structure"
    }
    models = {d: restore_model(ctx, d) for d in ctx.geometries}
    versions = {}
    seen = set()
    for record in repairs["records"]:
        verify_envelope(record, "m6-repair-record-v1")
        p = record["proposal"]
        parent = p["parent_occurrence_id"]
        if parent in seen or parent not in raw:
            raise ValueError("foreign/duplicate parent")
        seen.add(parent)
        original = raw[parent]
        if p != propose_repair(original, ctx.specifications[p["dataset_id"]], structural[parent]):
            raise ValueError("repair differs from approved source-bound policy")
        if record["post"]:
            if record["post"] != reevaluate(ctx, models[p["dataset_id"]], p):
                raise ValueError("post-repair frozen evidence contradiction")
            versions[p["derived_occurrence_id"]] = (p, record)
    if seen != set(raw):
        raise ValueError("missing parent")
    fingerprints = []
    for row in manifest["constructions"]:
        value = read_bundle(
            core / "constructions" / f"{row['dataset_id']}-{row['strategy']}-{row['condition']}"
        )
        verify_envelope(value, "m6-m7-construction-v1")
        if (
            value["fingerprint"] != row["fingerprint"]
            or digest(value["selected_records"]) != value["selected_content_fingerprint"]
        ):
            raise ValueError("construction identity mismatch")
        d = value["dataset_id"]
        parents = []
        payloads = []
        if (
            value["reference_fingerprint"] != ctx.geometries[d].reference["fingerprint"]
            or value["phase4_fingerprint"] != ctx.shadow["fingerprint"]
            or value["specification_fingerprint"] != ctx.specifications[d]["fingerprint"]
        ):
            raise ValueError("construction reference mismatch")
        for selected in value["selected_records"]:
            oid = selected["occurrence_id"]
            parent = selected["parent_occurrence_id"]
            if parent not in raw or raw[parent]["dataset_id"] != d:
                raise ValueError("foreign selected parent")
            original = raw[parent]
            if selected["parent_payload_sha256"] != original["payload_sha256"]:
                raise ValueError("parent payload mismatch")
            if oid in versions:
                p, r = versions[oid]
                if (
                    parent != p["parent_occurrence_id"]
                    or selected["derivation_fingerprint"] != r["fingerprint"]
                    or r["post"]["decision"]["action"] != "PROVISIONAL_PASS"
                    or value["condition"] != "repair-augmented"
                ):
                    raise ValueError("derived admission contradiction")
                expected = p["repaired_payload"]
            else:
                if (
                    oid != parent
                    or oid not in raw
                    or selected["derivation_fingerprint"] is not None
                    or structural[oid]["authoritative_validity"] == "INVALID"
                ):
                    raise ValueError("original structural reject or foreign selection")
                decision = next(
                    r
                    for r in ctx.shadow["decisions"]
                    if r["occurrence_id"] == oid and r["policy"]["name"] == "combined-review"
                )
                if decision["action"] != "PROVISIONAL_PASS":
                    raise ValueError("non-provisional raw selection")
                expected = original["payload"]
            if (
                selected["payload"] != expected
                or digest(expected) != selected["payload_sha256"]
                or not complete_record(expected, ctx.specifications[d]["specification"])
            ):
                raise ValueError("altered/incomplete selected payload")
            for key in ("source_artifact", "source_artifact_sha256", "source_occurrence_ordinal"):
                if selected[key] != original[key]:
                    raise ValueError("source locator mismatch")
            parents.append(parent)
            payloads.append(digest(expected))
        n = len(parents)
        if (
            len(set(parents)) != n
            or n != value["budget_achieved"]
            or n > value["budget_requested"]
            or value["shortfall"] != value["budget_requested"] - n
        ):
            raise ValueError("parent exclusivity/budget contradiction")
        if value["metrics"]["exact_duplicate_rate"] != (1 - len(set(payloads)) / n if n else 0):
            raise ValueError("duplicate accounting contradiction")
        if [r["selection_rank"] for r in value["trace"]] != list(range(1, n + 1)) or [
            r["occurrence_id"] for r in value["trace"]
        ] != [r["occurrence_id"] for r in value["selected_records"]]:
            raise ValueError("selection trace order contradiction")
        fingerprints.append(value["fingerprint"])
    content = {"repairs": repairs["record_content_fingerprint"], "constructions": fingerprints}
    if digest(content) != manifest["substantive_content_fingerprint"]:
        raise ValueError("core substantive identity mismatch")
    return {
        "status": "PASS",
        "parents": len(raw),
        "derived": len(versions),
        "constructions": len(fingerprints),
        "post_evidence_replayed": True,
        "fit_performed": False,
        "real_test_used": False,
        "substantive_content_fingerprint": manifest["substantive_content_fingerprint"],
    }
