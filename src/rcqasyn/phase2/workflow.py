from __future__ import annotations

from pathlib import Path
from typing import Any

from rcqasyn.storage.artifacts import create_run_dir, write_json
from rcqasyn.storage.ownership import bundle_lock, seal_bundle

from .annotations import annotation_protocol, packets
from .cohort import build_cohort, validate_cohort
from .common import csv_text, envelope, read_bundle, snapshot, verify_envelope, write_bundle
from .contracts import FREEZE
from .provenance import extract_crosswalk, validate_crosswalk
from .specifications import specifications, validate_specifications

RUNS = (
    "m1-p1-real-page-blocks0-gemma4-e4b-20260829",
    "m1-p1-real-Ecoli4-gemma4-e4b-20260829",
    "m1-p1-real-Abalone19-gemma4-e4b-20260829",
)
DEFAULT_OUTPUT = Path("artifacts/reports/phase2/gate-a-v1")


def historical_inventory(root: Path) -> dict[str, str]:
    """Snapshot original evidence only; Phase-2 derivatives have a separate namespace."""
    files = []
    for name in ("data", "artifacts/runs", "artifacts/reports", "test-results",
                 "configs", "prompts"):
        for path in (root / name).rglob("*"):
            if path.is_file() and "phase2" not in path.relative_to(root).parts:
                files.append(path)
    return snapshot(root, files)


def prepare(root: Path, output: Path, *, dry_run: bool = False) -> dict[str, Any]:
    namespace = (root / "artifacts/reports/phase2").resolve()
    if not output.resolve().is_relative_to(namespace) or output.resolve() == namespace:
        raise ValueError("preparation output must be a version under artifacts/reports/phase2")
    before = historical_inventory(root)
    crosswalks = [extract_crosswalk(root, root / "artifacts/runs" / run) for run in RUNS]
    page = crosswalks[0]["summary"]
    if (page["occurrences"], page["unique_occurrence_ids"], page["unique_legacy_ids"],
            page["different_content_collision_groups"], page["unresolved_occurrences"]) != (
                200, 200, 185, 15, 0):
        raise ValueError("historical source population contradicts approved reconciliation")
    cohort = build_cohort(root, crosswalks)
    specs = specifications(root)
    protocol = annotation_protocol(specs)
    public, private = packets(cohort, protocol)
    inventory = envelope("historical-integrity-v1", {
        "source_files": before, "file_count": len(before),
        "validation_status": "UNCHANGED", "comparison": "before preparation versus after preparation"})
    objects = {**{f"crosswalk-{i + 1}": cw for i, cw in enumerate(crosswalks)},
               "cohort": cohort, "specifications": specs, "protocol": protocol,
               "public-packets": public, "private-map": private, "historical-integrity": inventory}
    manifest = envelope("phase2-gate-a-preparation-v1", {
        "crosswalk_version": crosswalks[0]["crosswalk_version"],
        "cohort_version": cohort["cohort_version"],
        "validation_status": "PENDING_INDEPENDENT_VERIFICATION",
        "cohort_status": "PENDING_INDEPENDENT_VERIFICATION",
        "objects": {name: value["fingerprint"] for name, value in objects.items()},
        "source_inventory_fingerprint": inventory["fingerprint"],
        "real_agent_labels_generated": False, "human_labels_approved": False,
        "official_analysis_executed": False, "phase1_freeze_sha": FREEZE})
    if historical_inventory(root) != before:
        raise ValueError("historical file set/hash changed during preparation")
    if dry_run:
        return manifest
    with bundle_lock(output):
        if output.exists():
            if read_bundle(output) != manifest:
                raise FileExistsError("preparation differs; choose a new versioned namespace")
            validate_preparation(root, output)
            return manifest
        create_run_dir(output.parent, output.name)
        for name, value in objects.items():
            extras = {}
            if name.startswith("crosswalk-"):
                extras["crosswalk.csv"] = csv_text(value["records"])
                extras["reconciliation.md"] = (
                    "# Source occurrence reconciliation\n\n"
                    + value["source_execution_id"] + "\n\n"
                    + "\n".join(f"- {k}: {v}" for k, v in value["summary"].items())
                    + "\n\nLegacy IDs are aliases. Identity binds source manifest, raw artifact "
                    "checksum and physical occurrence ordinal. Equal content remains distinct. "
                    "Trace locators are recorded witnesses, not invented attempt IDs.\n")
            elif name == "cohort":
                extras = {"corrected-review.csv": csv_text(value["records"]),
                          "reconciliation-ledger.csv": csv_text(value["reconciliation_ledger"]),
                          "before-after.csv": csv_text(value["changes"]),
                          "row94.md": (
                              "# Row 94 source-backed reconciliation\n\n"
                              "Logical CSV row 94 (data record 93) retains its original payload. "
                              "It binds to page-blocks0 source occurrence 1, not occurrence 41. "
                              "The generation response, item position, source hash, diagnostics, "
                              "ordered B2 evidence and B3 candidate witness establish the binding. "
                              "The five corrected fields and complete conflicting original record "
                              "are retained in artifact.json/changes and before-after.csv. "
                              "Original files are unchanged. No labels or approvals are implied.\n")}
            elif name == "specifications":
                extras["semantics-gaps.md"] = (
                    "# Dataset semantics gaps\n\n"
                    "All three specifications are drafts. The exact KEEL source version, "
                    "primitive declarations, binary tokens, minority token, missing policy and "
                    "frozen split are verified locally. TRAIN profiles describe observations.\n\n"
                    + "\n".join("- " + g["dataset_id"] + ": RESEARCH_DECISION_REQUIRED — "
                                + ", ".join(g["gaps"]) for g in value["semantics_gaps"])
                    + "\n\nDo not infer original-class mappings from dataset names. Approve "
                    "task semantics and any new hard constraints only after authoritative evidence. "
                    "Optional datasets remain unavailable and inactive.\n")
            elif name == "public-packets":
                extras = {"primary-120.csv": csv_text(value["primary"]),
                          "overlap-40.csv": csv_text(value["overlap"])}
            write_bundle(output / name, value, extras)
        write_json(output / "artifact.json", manifest)
        seal_bundle(output)
    if historical_inventory(root) != before:
        raise ValueError("historical file set/hash changed after derivative writes")
    return manifest


def load_preparation(output: Path) -> tuple[dict[str, Any], list[dict[str, Any]],
                                           dict[str, Any], dict[str, Any]]:
    manifest = read_bundle(output)
    verify_envelope(manifest, "phase2-gate-a-preparation-v1")
    objects = {name: read_bundle(output / name) for name in manifest["objects"]}
    if {name: value["fingerprint"] for name, value in objects.items()} != manifest["objects"]:
        raise ValueError("preparation child fingerprint mismatch")
    return objects["cohort"], [objects[f"crosswalk-{i + 1}"] for i in range(3)], (
        objects["protocol"]), objects["specifications"]


def validate_preparation(root: Path, output: Path) -> dict[str, Any]:
    cohort, crosswalks, protocol, specs = load_preparation(output)
    for crosswalk in crosswalks:
        validate_crosswalk(root, crosswalk)
    result = validate_cohort(root, cohort, crosswalks)
    validate_specifications(root, specs)
    if annotation_protocol(specs) != protocol:
        raise ValueError("protocol differs from source-bound dataset specifications")
    public, private = packets(cohort, protocol)
    if (read_bundle(output / "public-packets") != public
            or read_bundle(output / "private-map") != private):
        raise ValueError("blinded packet membership/projection mismatch")
    inventory = read_bundle(output / "historical-integrity")
    verify_envelope(inventory, "historical-integrity-v1")
    if historical_inventory(root) != inventory["source_files"]:
        raise ValueError("original historical file set or checksums changed")
    return {**result, "historical_files": inventory["file_count"],
            "dataset_specifications": len(specs["specifications"]),
            "cohort_status": "PENDING_INDEPENDENT_VERIFICATION",
            "external_verification_or_supervisor_approval": False}
