from __future__ import annotations

import copy
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

from rcqasyn.phase2.common import csv_text, digest, envelope, read_bundle, write_bundle
from rcqasyn.phase5.contracts import SelectionConfig
from rcqasyn.phase5.geometry import Geometry, complete_record
from rcqasyn.phase5.selection import select
from rcqasyn.phase5.workflow import Context, load_context, pool

from .objective import reevaluate, restore_model
from .repair import POLICY, propose_repair


def run_repairs(ctx: Context, revision: str) -> dict[str, Any]:
    started = time.perf_counter()
    models = {d: restore_model(ctx, d) for d in ctx.geometries}
    old = {(r["occurrence_id"], r["validator_family"]): r for r in ctx.m2["evidence"]}
    decisions = {
        r["occurrence_id"]: r
        for r in ctx.shadow["decisions"]
        if r["policy"]["name"] == "combined-review"
    }
    original_vectors = {v["occurrence_id"]: v for v in ctx.shadow["harmonized"]["vectors"]}
    records, audits = [], []
    exact = True
    maximum_difference = 0.0
    for d, g in ctx.geometries.items():
        for o in g.occurrences:
            restored = [r.model_dump(mode="json") for r in models[d].score(o)]
            for r in restored:
                previous = old[o["occurrence_id"], r["validator_family"]]
                exact = exact and r == previous
                if (
                    r["authoritative_validity"] != previous["authoritative_validity"]
                    or r["status"] != previous["status"]
                ):
                    raise ValueError("restored M2 source state contradicts frozen evidence")
                if r["raw_score"] is not None:
                    delta = abs(r["raw_score"] - previous["raw_score"])
                    maximum_difference = max(maximum_difference, delta)
                    if delta > 1e-12:
                        raise ValueError("restored M2 scores contradict recorded fitted model")
            structural = old[o["occurrence_id"], "authoritative_structure"]
            proposal = propose_repair(o, ctx.specifications[d], structural)
            post = reevaluate(ctx, models[d], proposal) if proposal["repair_attempted"] else None
            categories = []
            for issue in structural["quantities"]["violations"]:
                code = issue["reason"]
                if code == "ABSENT_DECLARED_FIELD":
                    category = "MISSING_CLASS" if issue["field"] == g.target else "MISSING_FEATURE"
                elif code == "NONINTEGRAL_DECLARED_INTEGER":
                    category = "FRACTIONAL_INTEGER_FIELD"
                elif code == "NONNUMERIC_PRIMITIVE":
                    category = "INVALID_PRIMITIVE"
                elif code == "UNDECLARED_NOMINAL_VALUE":
                    category = "UNSUPPORTED_NOMINAL_CATEGORY"
                else:
                    category = "OTHER_STRUCTURAL_VIOLATION"
                categories.append(category)
            if structural["status"] != "AVAILABLE" or structural["quantities"].get(
                "unverified_constraints"
            ):
                categories.append("UNSUPPORTED_OR_AMBIGUOUS")
            before = original_vectors[o["occurrence_id"]]
            delta_percentiles = {
                f: post["vector"]["normalized"][f]["percentile"]
                - before["normalized"][f]["percentile"]
                if post
                and post["vector"]["normalized"][f]["percentile"] is not None
                and before["normalized"][f]["percentile"] is not None
                else None
                for f in ("local_support", "cross_feature")
            }
            record = envelope(
                "m6-repair-record-v1",
                {
                    "proposal": proposal,
                    "post": post,
                    "original_decision": decisions[o["occurrence_id"]],
                    "original_vector_fingerprint": before["fingerprint"],
                    "original_scores": {
                        f: before["normalized"][f] for f in ("local_support", "cross_feature")
                    },
                    "percentile_changes": delta_percentiles,
                },
            )
            records.append(record)
            audits.append(
                {
                    "occurrence_id": o["occurrence_id"],
                    "dataset_id": d,
                    "payload_sha256": o["payload_sha256"],
                    "source_ordinal": o["source_occurrence_ordinal"],
                    "pre_structural_state": proposal["pre_structural_state"],
                    "violation_categories": sorted(set(categories)),
                    "structural_violation_fields": len(structural["quantities"]["violations"]),
                    "multiple_simultaneous_violations": len(structural["quantities"]["violations"])
                    > 1,
                    "eligibility": proposal["eligibility"],
                    "outcome": post["repair_outcome"] if post else "NOT_ATTEMPTED",
                    "reasons": proposal["reasons"],
                    "derived_occurrence_id": proposal["derived_occurrence_id"],
                    "edited_fields": proposal["edited_fields"],
                    "edits": proposal["edits"],
                    "post_structural_status": post["post_repair_structural_status"]
                    if post
                    else proposal["pre_structural_state"],
                    "old_action": decisions[o["occurrence_id"]]["action"],
                    "new_action": post["decision"]["action"] if post else None,
                    "local_percentile_change": delta_percentiles["local_support"],
                    "global_percentile_change": delta_percentiles["cross_feature"],
                }
            )
    summary = {}
    for d in sorted(ctx.geometries):
        selected = [r for r in audits if r["dataset_id"] == d]
        summary[d] = {
            "occurrences": len(selected),
            "structurally_invalid": sum(
                r["pre_structural_state"] == "STRUCTURALLY_INVALID" for r in selected
            ),
            "repair_eligible": sum(r["eligibility"] == "REPAIR_ELIGIBLE" for r in selected),
            "repair_ineligible": sum(r["eligibility"] == "REPAIR_INELIGIBLE" for r in selected),
            "repair_attempted": sum(r["outcome"] != "NOT_ATTEMPTED" for r in selected),
            "repair_successful": sum(r["outcome"] == "REPAIR_APPLIED" for r in selected),
            "repair_failed": sum(r["outcome"] == "REPAIR_FAILED" for r in selected),
            "post_actions": dict(
                Counter(r["new_action"] for r in selected if r["new_action"] is not None)
            ),
            "violation_category_records": dict(
                Counter(c for r in selected for c in r["violation_categories"])
            ),
            "multiple_violation_records": sum(
                r["multiple_simultaneous_violations"] for r in selected
            ),
        }
    return envelope(
        "m6-repair-study-v1",
        {
            "implementation_revision": revision,
            "policy": POLICY,
            "source_m2_fingerprint": ctx.m2["fingerprint"],
            "source_phase4_fingerprint": ctx.shadow["fingerprint"],
            "records": records,
            "audit": audits,
            "record_content_fingerprint": digest(records),
            "summary": summary,
            "original_m2_replay_exact": exact,
            "original_m2_maximum_score_difference": maximum_difference,
            "fit_performed": False,
            "reference_reranked": False,
            "real_test_used": False,
            "human_approved_labels_used": False,
            "runtime_seconds": time.perf_counter() - started,
        },
    )


def construction(
    ctx: Context, repairs: dict[str, Any], plan: dict[str, Any], revision: str
) -> list[dict[str, Any]]:
    results = []
    for d, base in ctx.geometries.items():
        additions = []
        post_byid = {}
        for record in repairs["records"]:
            p = record["proposal"]
            post = record["post"]
            if p["dataset_id"] != d or post is None:
                continue
            original = next(
                o for o in base.occurrences if o["occurrence_id"] == p["parent_occurrence_id"]
            )
            derived = {
                **copy.deepcopy(original),
                "occurrence_id": p["derived_occurrence_id"],
                "payload": p["repaired_payload"],
                "payload_sha256": p["repaired_payload_sha256"],
                "parent_occurrence_id": p["parent_occurrence_id"],
                "parent_payload_sha256": p["parent_payload_sha256"],
                "derivation_fingerprint": record["fingerprint"],
            }
            additions.append(derived)
            post_byid[derived["occurrence_id"]] = post
        for strategy in plan["coverage"]["strategies"]:
            config = SelectionConfig(
                strategy=strategy,
                budget=plan["coverage"]["budgets"][d],
                coverage_radius=plan["coverage"]["radius"],
                near_duplicate_tolerance=plan["coverage"]["near_tolerance"],
                minority_quota_fraction=plan["coverage"]["minority_quota_fraction"],
            )
            original_eligible, original_concern, _ = pool(ctx, d, config)
            for condition in plan["coverage"]["conditions"]:
                added = additions if condition == "repair-augmented" else []
                g = (
                    Geometry(base.reference, [*base.occurrences, *added], base.fields, base.target)
                    if added
                    else base
                )
                eligible = list(original_eligible)
                concerns = dict(original_concern)
                for i in range(len(base.occurrences), len(g.occurrences)):
                    o = g.occurrences[i]
                    post = post_byid[o["occurrence_id"]]
                    if post["decision"]["action"] == "PROVISIONAL_PASS" and complete_record(
                        o["payload"], ctx.specifications[d]["specification"]
                    ):
                        eligible.append(i)
                        concerns[i] = post["vector"]["fusion"]["uncalibrated_max"]
                recipe = select(g, eligible, concerns, config)
                selected = recipe.pop("selected_indices")
                rows = []
                parents = []
                for i in selected:
                    o = g.occurrences[i]
                    parent = o.get("parent_occurrence_id", o["occurrence_id"])
                    parents.append(parent)
                    rows.append(
                        {
                            "occurrence_id": o["occurrence_id"],
                            "payload_sha256": o["payload_sha256"],
                            "payload": copy.deepcopy(o["payload"]),
                            "parent_occurrence_id": parent,
                            "parent_payload_sha256": o.get(
                                "parent_payload_sha256", o["payload_sha256"]
                            ),
                            "derivation_fingerprint": o.get("derivation_fingerprint"),
                            "source_artifact": o["source_artifact"],
                            "source_artifact_sha256": o["source_artifact_sha256"],
                            "source_occurrence_ordinal": o["source_occurrence_ordinal"],
                        }
                    )
                if len(set(parents)) != len(parents):
                    raise ValueError("original/derived physical parent counted twice")
                if condition == "original":
                    historical = read_bundle(
                        ctx.root
                        / f"artifacts/reports/phase5/study-v1/datasets/{d}-{strategy}-b{config.budget}"
                    )
                    if [r["occurrence_id"] for r in rows] != [
                        r["occurrence_id"] for r in historical["selected_records"]
                    ] or recipe["metrics"] != historical["metrics"]:
                        raise ValueError("M7 original condition no longer reproduces frozen result")
                results.append(
                    envelope(
                        "m6-m7-construction-v1",
                        {
                            "dataset_id": d,
                            "strategy": strategy,
                            "condition": condition,
                            "configuration": config.model_dump(mode="json"),
                            "implementation_revision": revision,
                            "raw_crosswalk_fingerprint": next(
                                c["fingerprint"]
                                for c in ctx.crosswalks
                                if c["records"][0]["dataset_id"] == d
                            ),
                            "repair_record_content_fingerprint": repairs[
                                "record_content_fingerprint"
                            ],
                            "phase4_fingerprint": ctx.shadow["fingerprint"],
                            "reference_fingerprint": base.reference["fingerprint"],
                            "specification_fingerprint": ctx.specifications[d]["fingerprint"],
                            "eligible_n": len(eligible),
                            "selected_records": rows,
                            "selected_content_fingerprint": digest(rows),
                            "derived_selected": sum(
                                r["derivation_fingerprint"] is not None for r in rows
                            ),
                            "source_parent_exclusivity": True,
                            "human_approval": "PENDING_SUPERVISOR_REVIEW",
                            **recipe,
                        },
                    )
                )
    return results


def run_core(root: Path, source: Path, output: Path, plan: dict[str, Any]) -> dict[str, Any]:
    ctx = load_context(root, source)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    repairs = run_repairs(ctx, revision)
    write_bundle(output / "repairs", repairs, {"audit.csv": csv_text(repairs["audit"])})
    constructed = construction(ctx, repairs, plan, revision)
    for value in constructed:
        name = f"{value['dataset_id']}-{value['strategy']}-{value['condition']}"
        rows = [
            {
                "selection_rank": i + 1,
                "occurrence_id": r["occurrence_id"],
                "parent_occurrence_id": r["parent_occurrence_id"],
                **r["payload"],
            }
            for i, r in enumerate(value["selected_records"])
        ]
        write_bundle(
            output / "constructions" / name,
            value,
            {"dataset.csv": csv_text(rows), "trace.csv": csv_text(value["trace"])},
        )
    content = {
        "repairs": repairs["record_content_fingerprint"],
        "constructions": [v["fingerprint"] for v in constructed],
    }
    result = envelope(
        "m6-core-manifest-v1",
        {
            "implementation_revision": revision,
            "plan": plan,
            "plan_fingerprint": digest(plan),
            "repair_bundle_fingerprint": repairs["fingerprint"],
            "construction_count": len(constructed),
            "constructions": [
                {
                    "dataset_id": v["dataset_id"],
                    "strategy": v["strategy"],
                    "condition": v["condition"],
                    "fingerprint": v["fingerprint"],
                }
                for v in constructed
            ],
            "substantive_content_fingerprint": digest(content),
        },
    )
    write_bundle(output / "manifest", result)
    return result
