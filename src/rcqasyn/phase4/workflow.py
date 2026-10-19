from __future__ import annotations

import json
import platform
import subprocess
import time
from collections import Counter
from importlib.metadata import version
from pathlib import Path
from typing import Any

from rcqasyn.phase2.common import (
    csv_text,
    digest,
    envelope,
    read_bundle,
    verify_envelope,
    write_bundle,
)
from rcqasyn.phase2.workflow import load_preparation, validate_preparation
from rcqasyn.phase3.workflow import read_results

from .calibration import pending_status
from .contracts import ACTIONS, PARENT, EvidenceVector, Policy
from .fusion import decide, dependence, harmonize, verify_vector


def validate_input(m2: dict[str, Any], source: Path, preparation: Path) -> list[dict[str, Any]]:
    cohort, cws, _, specs = load_preparation(preparation)
    occurrences = [r for cw in cws for r in cw["records"]]
    expected = [{k: r[k] for k in ("occurrence_id", "payload_sha256", "dataset_id")} for r in occurrences]
    if (m2["candidate_bindings"] != expected or m2["cohort_fingerprint"] != cohort["fingerprint"]
            or m2["crosswalk_fingerprints"] != [cw["fingerprint"] for cw in cws]
            or m2["specifications_fingerprint"] != specs["fingerprint"]):
        raise ValueError("M2 population differs from source-bound preparation")
    specmap = {s["specification"]["dataset_id"]: s for s in specs["specifications"]}
    for d, ref in m2["reference_populations"].items():
        split = json.loads((source/f"data/manifests/{d}/split_manifest.json").read_text())
        if (ref["train_indices"] != split["train_indices"]
                or ref["recorded_train_fingerprint"] != split["train_fingerprint"]
                or ref["specification_fingerprint"] != specmap[d]["fingerprint"]
                or ref["statistical_fit_uses_test"] is not False):
            raise ValueError("foreign reference or REAL TEST leakage")
    if set(m2["reference_populations"]) != set(specmap):
        raise ValueError("missing/foreign dataset reference")
    return occurrences


def summarize(decisions: list[dict[str, Any]], occurrences: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for policy in dict.fromkeys(r["policy"]["name"] for r in decisions):
        result[policy] = {}
        for d in sorted({r["dataset_id"] for r in occurrences}):
            selected = [r for r in decisions if r["dataset_id"] == d and r["policy"]["name"] == policy]
            original = {r["occurrence_id"]: r for r in occurrences if r["dataset_id"] == d}
            actions = {a: sum(r["action"] == a for r in selected) for a in ACTIONS}
            comparisons = {}
            for b in ("b1", "b2", "b3"):
                joint = Counter((r["action"], original[r["occurrence_id"]]["controls"][b]["decision"]["accepted"]) for r in selected)
                comparisons[b] = {"recorded_accepted": sum(o["controls"][b]["decision"]["accepted"] for o in original.values()),
                    "cross_table": [{"shadow_action": a, "recorded_accepted": accepted, "n": joint[a, accepted]}
                                    for a in ACTIONS for accepted in (True, False)],
                    "provisional_pass_symmetric_difference": sum(
                        (r["action"] == "PROVISIONAL_PASS") != original[r["occurrence_id"]]["controls"][b]["decision"]["accepted"] for r in selected)}
            classes = sorted({str(o["payload"].get("class", "<MISSING>")) for o in original.values()})
            result[policy][d] = {"n": len(selected), "actions": actions, "controls": comparisons,
                "literal_payload_class_breakdown": {c: dict(Counter(r["action"] for r in selected
                    if str(original[r["occurrence_id"]]["payload"].get("class", "<MISSING>")) == c)) for c in classes},
                "missing_required": sum(bool(r["missing_required_families"]) for r in selected)}
    return result


def stability(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    base = {r["occurrence_id"]: r for r in decisions if r["policy"]["name"] == "combined-review"}
    rows = []
    for p in ("combined-review-q80", "combined-review-q95"):
        for d in sorted({r["dataset_id"] for r in decisions}):
            selected = [r for r in decisions if r["policy"]["name"] == p and r["dataset_id"] == d]
            if selected and base:
                transitions = Counter((base[r["occurrence_id"]]["action"], r["action"]) for r in selected)
                rows.append({"dataset": d, "policy": p, "n": len(selected),
                    "changed": sum(a != b for a, b in transitions.elements()),
                    "transitions": [{"baseline": a, "sensitivity": b, "n": n} for (a, b), n in sorted(transitions.items())]})
    return rows


def run_shadow(source: Path, preparation: Path, m2_path: Path, review_path: Path,
               output: Path, plan: dict[str, Any], root: Path) -> dict[str, Any]:
    start = time.perf_counter()
    if (plan["schema_version"] != "phase4-experiment-plan-v1"
            or plan["normalization"] != "candidate-mid-ecdf-v1"
            or plan["calibration"] != "INACTIVE_PENDING_CONFIRMED_HUMAN_LEDGER"):
        raise ValueError("unsupported experimental contract")
    validate_preparation(source, preparation)
    m2 = read_results(m2_path)
    occurrences = validate_input(m2, source, preparation)
    review = read_bundle(review_path)
    # Enriched second-pass JSON is sealed by the existing package, not treated as ground truth.
    review_rows = json.loads((review_path/"review.json").read_text(encoding="utf-8"))
    calibration = pending_status(review_rows, review["fingerprint"])
    h = harmonize(m2, plan["minimum_reference_size"])
    policies = [Policy.model_validate_json(json.dumps(r)) for r in plan["policies"]]
    if len({p.name for p in policies}) != len(policies) or not policies:
        raise ValueError("duplicate or empty policy design")
    decisions = [decide(v, p) for p in policies for v in h["vectors"]]
    lookup = {r["occurrence_id"]: r for r in occurrences}
    for row in decisions:
        source_row = lookup[row["occurrence_id"]]
        row.update({k: source_row[k] for k in ("source_artifact", "source_artifact_sha256", "source_occurrence_ordinal")})
        row["fingerprint"] = digest(row)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    value = envelope("m4-m5-shadow-experiment-v1", {
        "phase3_parent": PARENT, "implementation_revision": revision,
        "scientific_status": "EXPLORATORY_SHADOW_ONLY_HUMAN_REVIEW_PENDING",
        "plan": plan, "plan_fingerprint": digest(plan), "m2_bundle_fingerprint": m2["fingerprint"],
        "m2_evidence_content_fingerprint": m2["evidence_content_fingerprint"],
        "m2_input": plan["m2_input"], "harmonized": h, "calibration": calibration,
        "decisions": decisions, "decision_content_fingerprint": digest(decisions),
        "dependence": dependence(h["vectors"]), "summary": summarize(decisions, occurrences),
        "sensitivity": stability(decisions), "real_test_used": False, "providers_used": False,
        "human_labels_used": False, "accepted_datasets_constructed": False,
        "python_version": platform.python_version(),
        "dependencies": {n: version(n) for n in ("numpy", "pandas", "scikit-learn", "pydantic")},
        "runtime_seconds": time.perf_counter()-start})
    write_bundle(output, value, {"decisions.csv": csv_text(decisions), "vectors.csv": csv_text(h["vectors"])})
    read_shadow(output, m2_path)
    return value


def read_shadow(path: Path, m2_path: Path | None = None) -> dict[str, Any]:
    value = read_bundle(path)
    verify_envelope(value, "m4-m5-shadow-experiment-v1")
    h = value["harmonized"]
    verify_envelope(h, "m4-harmonized-evidence-v1")
    if (value["plan_fingerprint"] != digest(value["plan"])
            or digest(h["vectors"]) != h["vector_content_fingerprint"]
            or digest(value["decisions"]) != value["decision_content_fingerprint"]
            or value["calibration"]["status"] != "NOT_ELIGIBLE_UNAPPROVED_LABELS"
            or value["calibration"]["fitted"] is not False
            or value["real_test_used"] is not False):
        raise ValueError("shadow provenance/content/calibration mismatch")
    policies = {p["name"]: Policy.model_validate_json(json.dumps(p)) for p in value["plan"]["policies"]}
    vectors = {}
    for raw in h["vectors"]:
        v: EvidenceVector = verify_vector(raw)
        if v.occurrence_id in vectors:
            raise ValueError("duplicate vector")
        vectors[v.occurrence_id] = raw
    expected = {(k, p) for k in vectors for p in policies}
    seen = set()
    for row in value["decisions"]:
        key = (row["occurrence_id"], row["policy"]["name"])
        if key not in expected or key in seen:
            raise ValueError("foreign/duplicate shadow decision")
        seen.add(key)
        if row["fingerprint"] != digest({k: v for k, v in row.items() if k != "fingerprint"}):
            raise ValueError("decision fingerprint mismatch")
        regenerated = decide(vectors[key[0]], policies[key[1]])
        if any(row[k] != v for k, v in regenerated.items()):
            raise ValueError("decision does not replay")
    if seen != expected:
        raise ValueError("incomplete shadow decision population")
    if m2_path is not None:
        m2 = read_results(m2_path)
        if h != harmonize(m2, value["plan"]["minimum_reference_size"]):
            raise ValueError("normalization does not replay from frozen M2")
    return value
