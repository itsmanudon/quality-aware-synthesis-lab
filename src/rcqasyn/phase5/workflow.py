from __future__ import annotations

import copy
import json
import platform
import subprocess
import time
from collections import Counter
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any

from rcqasyn.datasets.loader import load_dataset
from rcqasyn.datasets.registry import DatasetRegistry
from rcqasyn.phase2.common import (
    csv_text,
    digest,
    envelope,
    read_bundle,
    verify_envelope,
    write_bundle,
)
from rcqasyn.phase2.workflow import DEFAULT_OUTPUT, load_preparation, validate_preparation
from rcqasyn.phase3.workflow import read_results
from rcqasyn.phase4.workflow import read_shadow, validate_input

from .contracts import PARENT, SelectionConfig
from .geometry import Geometry, complete_record, reference_from_frame
from .selection import select


@dataclass
class Context:
    root: Path
    source: Path
    shadow: dict[str, Any]
    m2: dict[str, Any]
    crosswalks: list[dict[str, Any]]
    geometries: dict[str, Geometry]
    specifications: dict[str, dict[str, Any]]
    code_fingerprints: dict[str, str]


def load_context(root: Path, source: Path, shadow_relative: str = "artifacts/reports/phase4/shadow-v1") -> Context:
    preparation = root/DEFAULT_OUTPUT
    validate_preparation(source, preparation)
    _, cws, _, specs = load_preparation(preparation)
    shadow = read_shadow(root/shadow_relative)
    m2 = read_results(root/shadow["m2_input"])
    shadow = read_shadow(root/shadow_relative, root/shadow["m2_input"])
    occurrences = validate_input(m2, source, preparation)
    expected = {r["occurrence_id"]: r for r in occurrences}
    actual = shadow["harmonized"]["vectors"]
    if len(actual) != len(expected) or any(v["occurrence_id"] not in expected or any(
            v[k] != expected[v["occurrence_id"]][k] for k in ("payload_sha256", "dataset_id")) for v in actual):
        raise ValueError("Phase-4 source population mismatch")
    registry = DatasetRegistry(project_root=source)
    geometries, specifications = {}, {}
    for specification in specs["specifications"]:
        d = specification["specification"]["dataset_id"]
        loaded = load_dataset(registry.get(d), registry)
        split = json.loads((source/f"data/manifests/{d}/split_manifest.json").read_text())
        reference = reference_from_frame(specification, loaded.frame, split, m2["model_parameters"][d])
        if reference["m2_train_reference_fingerprint"] != m2["reference_populations"][d]["train_reference_fingerprint"]:
            raise ValueError("derived TRAIN reference differs from frozen M2")
        spec = specification["specification"]
        geometries[d] = Geometry(reference, [o for o in occurrences if o["dataset_id"] == d],
                                 spec["features"], spec["target_semantics"]["target_column"])
        specifications[d] = specification
    codes = {p.relative_to(root).as_posix(): digest(p.read_text(encoding="utf-8-sig")) for p in sorted((root/"src/rcqasyn/phase5").glob("*.py"))}
    return Context(root, source, shadow, m2, cws, geometries, specifications, codes)


def pool(ctx: Context, dataset: str, config: SelectionConfig) -> tuple[list[int], dict[int, float], list[dict[str, Any]]]:
    g = ctx.geometries[dataset]
    decisions = {r["occurrence_id"]: r for r in ctx.shadow["decisions"]
                 if r["dataset_id"] == dataset and r["policy"]["name"] == config.policy_name}
    if set(decisions) != {o["occurrence_id"] for o in g.occurrences}:
        raise ValueError("missing or foreign Phase-4 policy decisions")
    vectors = {v["occurrence_id"]: v for v in ctx.shadow["harmonized"]["vectors"]}
    eligible, concern, ledger = [], {}, []
    for i, o in enumerate(g.occurrences):
        row = decisions[o["occurrence_id"]]
        if row["payload_sha256"] != o["payload_sha256"] or digest(o["payload"]) != o["payload_sha256"]:
            raise ValueError("candidate payload/source mismatch")
        reason = None
        if row["structural_judgment"] == "INVALID": reason = "DEFER_STRUCTURAL_REJECT"
        elif row["action"] != "PROVISIONAL_PASS": reason = "DEFER_PHASE4_" + row["action"]
        elif not complete_record(o["payload"], ctx.specifications[dataset]["specification"]): reason = "DEFER_INCOMPLETE_OR_UNSUPPORTED_LABELED_RECORD"
        elif config.control_intersection and not o["controls"][config.control_intersection]["decision"]["accepted"]: reason = "DEFER_RECORDED_B2_INTERSECTION"
        value = vectors[o["occurrence_id"]]["fusion"]["uncalibrated_max"]
        if reason is None and value is None: reason = "DEFER_UNAVAILABLE_STATISTICAL_VECTOR"
        if reason is None:
            eligible.append(i); concern[i] = value
        ledger.append({"occurrence_id": o["occurrence_id"], "payload_sha256": o["payload_sha256"],
            "source_occurrence_ordinal": o["source_occurrence_ordinal"], "phase4_action": row["action"],
            "phase4_decision_fingerprint": row["fingerprint"], "eligible": reason is None,
            "selected": False, "selection_rank": None, "reason": reason or "ELIGIBLE_BUDGET_DEFERRED"})
    return eligible, concern, ledger


def construct(ctx: Context, dataset: str, config: SelectionConfig, revision: str) -> dict[str, Any]:
    g = ctx.geometries[dataset]
    eligible, concerns, ledger = pool(ctx, dataset, config)
    recipe = select(g, eligible, concerns, config)
    selected = recipe.pop("selected_indices")
    trace = {r["occurrence_id"]: r for r in recipe["trace"]}
    used_features = {g.feature_ids[i] for i in selected}
    for i, row in enumerate(ledger):
        if row["occurrence_id"] in trace:
            row.update(selected=True, selection_rank=trace[row["occurrence_id"]]["selection_rank"], reason=trace[row["occurrence_id"]]["selection_reason"])
        elif row["eligible"] and config.strategy == "quality-coverage" and g.feature_ids[i] in used_features:
            row["reason"] = "DEFER_REPEATED_FEATURE_PAYLOAD"
    records = [{"occurrence_id": g.occurrences[i]["occurrence_id"],
        "payload_sha256": g.occurrences[i]["payload_sha256"], "payload": copy.deepcopy(g.occurrences[i]["payload"]),
        "source_artifact": g.occurrences[i]["source_artifact"],
        "source_artifact_sha256": g.occurrences[i]["source_artifact_sha256"],
        "source_occurrence_ordinal": g.occurrences[i]["source_occurrence_ordinal"]} for i in selected]
    policy = next(r["policy"] for r in ctx.shadow["decisions"] if r["policy"]["name"] == config.policy_name)
    population = [{k: g.occurrences[i][k] for k in ("occurrence_id", "payload_sha256")} for i in eligible]
    return envelope("m7-constructed-dataset-v1", {
        "dataset_id": dataset, "scientific_status": "EXPLORATORY_PROVISIONAL_NOT_HUMAN_VALIDATED",
        "human_validity_approval": "PENDING_SUPERVISOR_REVIEW", "calibration_status": "NOT_ELIGIBLE_UNAPPROVED_LABELS",
        "phase4_parent": PARENT, "implementation_revision": revision,
        "implementation_source_fingerprints": ctx.code_fingerprints,
        "implementation_fingerprint_definition": "Canonical JSON digest of UTF-8 source text with universal newlines",
        "configuration": config.model_dump(mode="json"), "configuration_fingerprint": digest(config.model_dump(mode="json")),
        "strategy_version": "m7-"+config.strategy+"-v1", "seed_usage": "No stochastic operations; seed is provenance only",
        "phase4_bundle_fingerprint": ctx.shadow["fingerprint"], "phase4_policy": policy,
        "phase4_policy_fingerprint": digest(policy), "m2_bundle_fingerprint": ctx.m2["fingerprint"],
        "source_crosswalk_fingerprint": next(cw["fingerprint"] for cw in ctx.crosswalks if cw["records"][0]["dataset_id"] == dataset),
        "specification_fingerprint": ctx.specifications[dataset]["fingerprint"],
        "source_files": ctx.specifications[dataset]["source_files"],
        "reference_fingerprint": g.reference["fingerprint"],
        "recorded_train_fingerprint": g.reference["recorded_train_fingerprint"],
        "candidate_pool": population, "candidate_pool_fingerprint": digest(population),
        "raw_occurrences_n": len(g.occurrences), "eligible_n": len(eligible),
        "selected_records": records, "selected_content_fingerprint": digest(records),
        "selection_ledger": ledger, **recipe,
        "test_values_used_for_selection": False, "agent_labels_used": False, "provider_calls": False})


def audit(ctx: Context, value: dict[str, Any]) -> dict[str, Any]:
    verify_envelope(value, "m7-constructed-dataset-v1")
    config = SelectionConfig.model_validate_json(json.dumps(value["configuration"]))
    keys = [r["occurrence_id"] for r in value["selected_records"]]
    if len(set(keys)) != len(keys): raise ValueError("duplicate selected occurrence")
    rebuilt = construct(ctx, value["dataset_id"], config, value["implementation_revision"])
    if value != rebuilt:
        raise ValueError("dataset audit contradiction: source, order, budget, quota, metric, selection or provenance differs")
    return {"schema_version": "m7-dataset-audit-v1", "status": "PASS",
            "constructed_dataset_fingerprint": value["fingerprint"],
            "selected_n": len(keys), "shortfall": value["shortfall"],
            "human_validity_approval": "PENDING_SUPERVISOR_REVIEW", "no_repair_performed": True}


def write_constructed(ctx: Context, output: Path, value: dict[str, Any]) -> dict[str, Any]:
    result = audit(ctx, value)
    rows = [{"selection_rank": i+1, "occurrence_id": r["occurrence_id"], "payload_sha256": r["payload_sha256"], **r["payload"]} for i,r in enumerate(value["selected_records"])]
    extras = {"selection-ledger.csv": csv_text(value["selection_ledger"]),
              "audit.json": json.dumps(result, sort_keys=True, indent=2)+"\n"}
    if rows:
        extras["dataset.csv"] = csv_text(rows)
    else:
        extras["dataset.csv"] = "selection_rank,occurrence_id,payload_sha256\n"
    extras["dataset.json"] = json.dumps(value["selected_records"], sort_keys=True, indent=2)+"\n"
    write_bundle(output, value, extras)
    restored = read_bundle(output)
    return audit(ctx, restored)


def configurations(plan: dict[str, Any]) -> list[tuple[str, str, SelectionConfig]]:
    rows = []
    for d, budgets in plan["budgets"].items():
        common = {"coverage_radius": plan["coverage_radius"], "near_duplicate_tolerance": plan["near_duplicate_tolerance"], "minority_quota_fraction": plan["quality_minority_quota_fraction"], "seed": plan["seed"]}
        for budget in budgets:
            for strategy in plan["primary_strategies"]:
                rows.append((f"{d}-{strategy}-b{budget}",d,SelectionConfig(strategy=strategy, budget=budget, policy_name=plan["primary_policy"], **common)))
            rows.append((f"{d}-b2-intersection-b{budget}",d,SelectionConfig(strategy="source-order", budget=budget, policy_name=plan["primary_policy"], control_intersection="b2", **common)))
        for policy in ("combined-review-q80", "combined-review-q95"):
            rows.append((f"{d}-{policy}-b{budgets[1]}", d, SelectionConfig(strategy="quality-coverage", budget=budgets[1], policy_name=policy, **common)))
    return rows


def run_study(root: Path, source: Path, output: Path, plan: dict[str, Any]) -> dict[str, Any]:
    start = time.perf_counter()
    if plan["schema_version"] != "m7-plan-v1": raise ValueError("unsupported study plan")
    ctx = load_context(root, source, plan["phase4_input"])
    for d, g in ctx.geometries.items():
        primary = SelectionConfig(strategy="source-order", budget=0, policy_name=plan["primary_policy"])
        eligible, _, _ = pool(ctx, d, primary)
        actual = {"eligible": len(eligible),
                  "classes": dict(Counter(g.occurrences[i]["payload"][g.target] for i in eligible)),
                  "unique_features": len({g.feature_ids[i] for i in eligible})}
        if actual != plan["pool_availability"][d] or plan["budgets"][d] != [max(1,int(actual["unique_features"]*f)) for f in (.25,.5,.75)]:
            raise ValueError("predeclared availability or matched budget rule differs from input")
    if (output/"manifest").exists():
        previous = read_bundle(output/"manifest")
        verify_envelope(previous, "m7-experiment-manifest-v1")
        if previous["plan"] != plan or previous["phase4_bundle_fingerprint"] != ctx.shadow["fingerprint"]:
            raise ValueError("existing study is bound to a different design or source")
        for row in previous["runs"]:
            dataset = read_bundle(output/"datasets"/row["name"])
            if dataset["fingerprint"] != row["fingerprint"]:
                raise ValueError("study/dataset fingerprint mismatch")
            audit(ctx,dataset)
        return previous
    revision = subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()
    for d,g in ctx.geometries.items():
        write_bundle(output/"references"/d, g.reference)
    runs = []
    for name,d,config in configurations(plan):
        tick = time.perf_counter()
        value = construct(ctx,d,config,revision)
        audited = write_constructed(ctx,output/"datasets"/name,value)
        runs.append({"name": name, "dataset_id": d, "strategy": config.strategy,
            "policy": config.policy_name, "control_intersection": config.control_intersection,
            "budget": config.budget, "selected_n": value["budget_achieved"], "shortfall": value["shortfall"],
            "fingerprint": value["fingerprint"], "selected_content_fingerprint": value["selected_content_fingerprint"],
            "metrics": value["metrics"], "audit_status": audited["status"], "runtime_seconds": time.perf_counter()-tick})
    content = [{k:v for k,v in r.items() if k!="runtime_seconds"} for r in runs]
    value = envelope("m7-experiment-manifest-v1", {"phase4_parent": PARENT,
        "implementation_revision": revision, "plan": plan, "plan_fingerprint": digest(plan),
        "phase4_bundle_fingerprint": ctx.shadow["fingerprint"], "runs": runs,
        "construction_content_fingerprint": digest(content), "total_constructed_datasets":len(runs),
        "audit_status_counts": dict(Counter(r["audit_status"] for r in runs)),
        "python_version": platform.python_version(), "dependencies": {n:version(n) for n in ("numpy","pandas","pydantic")},
        "runtime_seconds":time.perf_counter()-start,"human_approved_labels_used":False,"real_test_used":False})
    write_bundle(output/"manifest",value,{"runs.csv":csv_text(runs)})
    return value
