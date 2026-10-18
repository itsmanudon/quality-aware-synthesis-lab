from __future__ import annotations

import json
import platform
import subprocess
import time
from collections import Counter
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from rcqasyn.datasets.loader import load_dataset
from rcqasyn.datasets.registry import DatasetRegistry
from rcqasyn.datasets.split import _subset_fingerprint
from rcqasyn.phase2.common import (
    csv_text,
    digest,
    envelope,
    read_bundle,
    verify_envelope,
    write_bundle,
)
from rcqasyn.phase2.workflow import load_preparation, validate_preparation

from .contracts import PARENT, M2Config, M2Evidence
from .registry import REGISTRY, run_validators
from .validators import TrainEvidenceModel


def fit_train_only(specification: dict[str, Any], frame: pd.DataFrame,
                   split: dict[str, Any], config: M2Config) -> TrainEvidenceModel:
    verify_envelope(specification, "dataset-specification-v1")
    train, test = split["train_indices"], split["test_indices"]
    if (not train or len(set(train)) != len(train) or len(set(test)) != len(test)
            or set(train) & set(test) or set(train) | set(test) != set(frame.index)):
        raise ValueError("invalid frozen TRAIN/TEST membership")
    if split["dataset_id"] != specification["specification"]["dataset_id"]:
        raise ValueError("foreign reference dataset")
    if _subset_fingerprint(frame, train) != split["train_fingerprint"]:
        raise ValueError("TRAIN values differ from frozen reference")
    selected = frame.loc[train].astype(object)
    selected = selected.where(pd.notna(selected), None)
    # No TEST value, class or statistic is accessed beyond partition identity checks.
    records = selected.to_dict(orient="records")
    return TrainEvidenceModel(specification, tuple(train), records, config)


def read_results(path: Path) -> dict[str, Any]:
    value = read_bundle(path)
    verify_envelope(value, "m2-offline-evidence-v1")
    config = M2Config.model_validate_json(json.dumps(value["configuration"]))
    seen = set()
    references = value["reference_populations"]
    expected = {(r["occurrence_id"], family) for r in value["candidate_bindings"] for family in REGISTRY}
    bindings = {r["occurrence_id"]: r for r in value["candidate_bindings"]}
    if len(bindings) != len(value["candidate_bindings"]):
        raise ValueError("duplicate candidate identity")
    for raw in value["evidence"]:
        row = M2Evidence.model_validate_json(json.dumps(raw))
        key = (row.occurrence_id, row.validator_family)
        if key in seen or key not in expected:
            raise ValueError("duplicate or foreign evidence identity")
        seen.add(key)
        binding = bindings[row.occurrence_id]
        reference = references[row.dataset_id]
        if (row.payload_sha256 != binding["payload_sha256"]
                or row.dataset_id != binding["dataset_id"]
                or row.reference_fingerprint != reference["train_reference_fingerprint"]
                or row.specification_fingerprint != reference["specification_fingerprint"]
                or row.configuration_fingerprint != digest(config.model_dump(mode="json"))):
            raise ValueError("stale or substituted evidence binding")
    if seen != expected:
        raise ValueError("incomplete validator evidence population")
    return value


def summarize(evidence: list[dict[str, Any]], occurrences: list[dict[str, Any]]) -> dict[str, Any]:
    byid = {r["occurrence_id"]: r for r in occurrences}
    summary = {}
    for dataset in sorted({r["dataset_id"] for r in occurrences}):
        rows = [r for r in evidence if r["dataset_id"] == dataset]
        families = {}
        for family in REGISTRY:
            selected = [r for r in rows if r["validator_family"] == family]
            scored = [r for r in selected if r["raw_score"] is not None]
            x = np.array([r["raw_score"] for r in scored])
            bycontrol = {}
            for baseline in ("b1", "b2", "b3"):
                bycontrol[baseline] = {}
                for accepted in (True, False):
                    group = [r["raw_score"] for r in scored
                             if byid[r["occurrence_id"]]["controls"][baseline]["decision"]["accepted"] == accepted]
                    bycontrol[baseline]["accepted" if accepted else "rejected"] = {
                        "n_scored": len(group), "median": float(np.median(group)) if group else None}
            families[family] = {"status_counts": dict(Counter(r["status"] for r in selected)),
                "authoritative_invalid": sum(r["authoritative_validity"] == "INVALID" for r in selected),
                "quantiles": dict(zip(("min", "q25", "median", "q75", "max"),
                                      [float(v) for v in np.percentile(x, [0, 25, 50, 75, 100])], strict=True)) if len(x) else {},
                "by_recorded_controls": bycontrol}
        local = {r["occurrence_id"]: r for r in rows if r["validator_family"] == "local_support" and r["raw_score"] is not None}
        global_ = {r["occurrence_id"]: r for r in rows if r["validator_family"] == "cross_feature" and r["raw_score"] is not None}
        shared = sorted(local.keys() & global_.keys())
        correlation = None
        if len(shared) > 1:
            a = pd.Series([local[k]["raw_score"] for k in shared]).rank().to_numpy()
            b = pd.Series([global_[k]["raw_score"] for k in shared]).rank().to_numpy()
            if np.std(a) and np.std(b):
                correlation = float(np.corrcoef(a, b)[0, 1])
        tails = {}
        for name, group in (("local", local), ("cross_feature", global_)):
            cutoff = float(np.quantile([r["raw_score"] for r in group.values()], 0.9)) if group else None
            tails[name] = {"candidate_q90_for_case_selection_only": cutoff,
                           "occurrence_ids": sorted(k for k, r in group.items() if cutoff is not None and r["raw_score"] >= cutoff)}
        a, b = set(tails["local"]["occurrence_ids"]), set(tails["cross_feature"]["occurrence_ids"])
        violations = {r["occurrence_id"] for r in rows if r["authoritative_validity"] == "INVALID"}
        b2rejects = {k for k, r in byid.items() if r["dataset_id"] == dataset and not r["controls"]["b2"]["decision"]["accepted"]}
        # These compare diagnostics/control behavior, never unapproved human truth.
        summary[dataset] = {"families": families, "local_cross_feature_spearman": correlation,
            "case_selection_tails": tails, "tail_intersection": sorted(a & b),
            "tail_disagreement": sorted(a ^ b),
            "structural_vs_b2_disagreement": sorted(violations ^ b2rejects),
            "structural_violations_with_local_score_zero": sorted(k for k in violations & local.keys() if local[k]["raw_score"] == 0)}
    return summary


def run_offline(source: Path, preparation: Path, output: Path, config: M2Config,
                 implementation_root: Path) -> dict[str, Any]:
    start = time.perf_counter()
    validate_preparation(source, preparation)
    cohort, crosswalks, _, specs = load_preparation(preparation)
    occurrences = [r for cw in crosswalks for r in cw["records"]]
    registry = DatasetRegistry(project_root=source)
    evidence, references, parameters = [], {}, {}
    for specification in specs["specifications"]:
        dataset = specification["specification"]["dataset_id"]
        loaded = load_dataset(registry.get(dataset), registry)
        split = json.loads((source / f"data/manifests/{dataset}/split_manifest.json").read_text(encoding="utf-8"))
        model = fit_train_only(specification, loaded.frame, split, config)
        references[dataset] = {"train_reference_fingerprint": model.reference,
            "recorded_train_fingerprint": split["train_fingerprint"],
            "specification_fingerprint": specification["fingerprint"],
            "train_rows": len(model.records), "eligible_train_rows": len(model.eligible),
            "train_indices": list(model.row_ids), "statistical_fit_uses_test": False}
        parameters[dataset] = {"numeric_fields": model.numeric, "categorical_fields": model.categorical,
            "gower_spans": model.spans.tolist(), "robust_medians": model.medians.tolist(),
            "robust_scales": model.scales.tolist(), "train_categories": model.categories,
            "cross_feature_center": model.center.tolist(), "cross_feature_precision": model.precision.tolist()}
        for occurrence in occurrences:
            if occurrence["dataset_id"] == dataset:
                evidence += [r.model_dump(mode="json") for r in run_validators(model, occurrence)]
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=implementation_root, text=True).strip()
    value = envelope("m2-offline-evidence-v1", {
        "phase2_parent_commit": PARENT, "implementation_revision": revision,
        "scientific_status": "EXPLORATORY_HUMAN_LABEL_EVALUATION_PENDING",
        "human_approved_labels_used": False, "fusion_or_admission_policy": None,
        "configuration": config.model_dump(mode="json"), "validator_registry": REGISTRY,
        "seed_usage": "No stochastic estimator or sampling; seed retained for experiment identity.",
        "python_version": platform.python_version(),
        "dependencies": {name: version(name) for name in ("numpy", "pandas", "scipy", "scikit-learn", "pydantic")},
        "cohort_fingerprint": cohort["fingerprint"], "specifications_fingerprint": specs["fingerprint"],
        "crosswalk_fingerprints": [cw["fingerprint"] for cw in crosswalks],
        "candidate_bindings": [{"occurrence_id": r["occurrence_id"], "payload_sha256": r["payload_sha256"], "dataset_id": r["dataset_id"]} for r in occurrences],
        "reference_populations": references, "model_parameters": parameters,
        "evidence": evidence, "summary": summarize(evidence, occurrences),
        "evidence_content_fingerprint": digest(evidence),
        "sampling_limitations": cohort["selection_limitations"],
        "runtime_seconds": time.perf_counter() - start,
    })
    write_bundle(output, value, {"evidence.csv": csv_text(evidence)})
    read_results(output)
    return value
