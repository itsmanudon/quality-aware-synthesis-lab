"""Future research calibration, gated through the existing confirmed review ledger.

Research provenance is not cryptographic authentication. Synthetic fixtures use a
separate entry point and never establish eligibility for a real population.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.isotonic import IsotonicRegression

from rcqasyn.phase2.common import digest
from rcqasyn.phase2.research import confirm_research_ledger
from rcqasyn.phase3.workflow import read_results

from .fusion import harmonize, verify_vector

METHOD = "isotonic-increasing-v1"
MINIMUM_PER_CLASS = 5


def pending_status(review_rows: list[dict[str, Any]], review_fingerprint: str) -> dict[str, Any]:
    if not review_rows or any(r.get("human_final_label") is not None
                             or r.get("annotator_type") != "AGENT"
                             or r.get("review_status") != "PENDING_HUMAN_APPROVAL"
                             for r in review_rows):
        raise ValueError("expected unapproved agent review package; use confirmed-ledger path otherwise")
    return {"status": "NOT_ELIGIBLE_UNAPPROVED_LABELS", "method": METHOD,
        "review_package_fingerprint": review_fingerprint, "rows": len(review_rows),
        "agent_labels_used_for_fit": False, "fitted": False, "calibrator": None,
        "reason": "No supervisor-reviewed, explicitly fingerprint-confirmed ledger supplied.",
        "cryptographically_authenticated": False}


def _fit(samples: list[dict[str, Any]], calibration_ids: list[str], evaluation_ids: list[str],
         provenance: dict[str, Any], fixture: bool) -> dict[str, Any]:
    ids = [r["occurrence_id"] for r in samples]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate calibration source identity")
    if (not calibration_ids or not evaluation_ids
            or len(set(calibration_ids)) != len(calibration_ids)
            or len(set(evaluation_ids)) != len(evaluation_ids)
            or set(calibration_ids) & set(evaluation_ids)
            or not (set(calibration_ids) | set(evaluation_ids)) <= set(ids)):
        raise ValueError("calibration/evaluation populations must be explicit, unique and disjoint")
    if len({r["dataset_id"] for r in samples}) != 1:
        raise ValueError("calibration is dataset-specific; pooled domains are unsupported")
    for r in samples:
        if r["label"] not in ("VALID", "INVALID", "INDETERMINATE"):
            raise ValueError("unknown label vocabulary")
        if r["population"] != ("synthetic_fixture" if fixture else "historical_generated_candidate"):
            raise ValueError("REAL TEST or foreign population is forbidden")
        score = r["score"]
        if score is not None and (not np.isfinite(score) or not 0 <= score <= 1):
            raise ValueError("invalid descriptive predictor")
    byid = {r["occurrence_id"]: r for r in samples}
    groups = {name: [byid[k] for k in selected] for name, selected in
              (("calibration", calibration_ids), ("evaluation", evaluation_ids))}
    kept = {name: [r for r in rows if r["label"] != "INDETERMINATE" and r["score"] is not None]
            for name, rows in groups.items()}
    counts = {name: dict(Counter(r["label"] for r in rows)) for name, rows in kept.items()}
    base = {"method": METHOD, "dataset_id": samples[0]["dataset_id"],
        "provenance": provenance, "source_sample_fingerprint": digest(samples),
        "partition_fingerprint": digest({"calibration": calibration_ids, "evaluation": evaluation_ids}),
        "minimum_per_class_per_partition": MINIMUM_PER_CLASS, "class_counts": counts,
        "excluded_indeterminate": {n: sum(r["label"] == "INDETERMINATE" for r in rows) for n, rows in groups.items()},
        "excluded_missing_predictor": {n: sum(r["score"] is None and r["label"] != "INDETERMINATE" for r in rows) for n, rows in groups.items()},
        "fixture_only": fixture, "real_test_used": False, "cryptographically_authenticated": False}
    if any(counts[n].get(label, 0) < MINIMUM_PER_CLASS for n in counts for label in ("VALID", "INVALID")):
        return {**base, "status": "NOT_ELIGIBLE_CLASS_SUPPORT", "fitted": False, "calibrator": None}
    train, test = kept["calibration"], kept["evaluation"]
    x = [r["score"] for r in train]; y = [float(r["label"] == "INVALID") for r in train]
    if len(set(x)) < 2:
        return {**base, "status": "NOT_ELIGIBLE_CONSTANT_PREDICTOR", "fitted": False, "calibrator": None}
    model = IsotonicRegression(increasing=True, out_of_bounds="clip").fit(x, y)
    probabilities = model.predict([r["score"] for r in test])
    observed = np.asarray([float(r["label"] == "INVALID") for r in test])
    bins = []
    for i in range(5):
        mask = (probabilities >= i/5) & ((probabilities < (i+1)/5) if i < 4 else (probabilities <= 1))
        bins.append({"bin_lower": i/5, "bin_upper": (i+1)/5, "n": int(np.sum(mask)),
                     "mean_prediction": float(np.mean(probabilities[mask])) if np.any(mask) else None,
                     "observed_invalid_fraction": float(np.mean(observed[mask])) if np.any(mask) else None})
    return {**base, "status": "FITTED_SYNTHETIC_FIXTURE_ONLY" if fixture else "FITTED_CONFIRMED_RESEARCH_ONLY",
        "fitted": True, "calibrator": {"x_thresholds": model.X_thresholds_.tolist(),
                                       "y_thresholds": model.y_thresholds_.tolist()},
        "evaluation_brier": float(np.mean((probabilities-observed)**2)),
        "evaluation_reliability_bins": bins,
        "interpretation": "Dataset/selected-cohort conditional mapping; no population guarantee or automatic policy activation."}


def fit_synthetic_fixture(samples: list[dict[str, Any]], calibration_ids: list[str],
                          evaluation_ids: list[str]) -> dict[str, Any]:
    if any(not r["occurrence_id"].startswith("fixture:") for r in samples):
        raise ValueError("synthetic entry point cannot consume real occurrence identities")
    return _fit(samples, calibration_ids, evaluation_ids, {"authority": "SYNTHETIC_FIXTURE_ONLY"}, True)


def fit_confirmed_research(source: Path, cohort: dict[str, Any], crosswalks: list[dict[str, Any]],
                           protocol: dict[str, Any], scope: dict[str, Any],
                           proposals: list[dict[str, Any]], ledger: dict[str, Any],
                           confirmation: dict[str, Any], vectors: list[dict[str, Any]],
                           calibration_ids: list[str], evaluation_ids: list[str],
                           dataset_id: str, *, m2_path: Path) -> dict[str, Any]:
    """No approval boolean: validate full existing source-bound research review protocol."""
    confirmed = confirm_research_ledger(source, cohort, crosswalks, protocol, scope,
                                        proposals, ledger, confirmation)
    if cohort["population_kind"] != "research":
        raise ValueError("fixture scope cannot approve a real research calibrator")
    m2 = read_results(m2_path)
    expected = [{k: r[k] for k in ("occurrence_id", "payload_sha256", "dataset_id")}
                for cw in crosswalks for r in cw["records"]]
    if (m2["candidate_bindings"] != expected or m2["cohort_fingerprint"] != cohort["fingerprint"]
            or m2["specifications_fingerprint"] != protocol["specifications_fingerprint"]
            or m2["crosswalk_fingerprints"] != [cw["fingerprint"] for cw in crosswalks]
            or harmonize(m2)["vectors"] != vectors):
        raise ValueError("review/evidence population or frozen predictor mismatch")
    if len({v["occurrence_id"] for v in vectors}) != len(vectors):
        raise ValueError("duplicate evidence vector")
    byid = {v["occurrence_id"]: verify_vector(v) for v in vectors}
    originals = {r["occurrence_id"]: r for cw in crosswalks for r in cw["records"]}
    samples = []
    for row in ledger["rows"]:
        key = row["occurrence_id"]
        if row["dataset_id"] != dataset_id:
            continue
        v = byid[key]; original = originals[key]
        if (v.payload_sha256 != row["payload_sha256"] or v.dataset_id != dataset_id
                or v.payload_sha256 != original["payload_sha256"]):
            raise ValueError("review/evidence/source mismatch")
        samples.append({"occurrence_id": key, "dataset_id": dataset_id,
            "label": row["human_final_label"], "score": v.fusion["uncalibrated_max"],
            "population": "historical_generated_candidate"})
    if not samples:
        raise ValueError("no reviewed source records for dataset")
    return _fit(samples, calibration_ids, evaluation_ids,
        {"reviewed_ledger_fingerprint": ledger["fingerprint"],
         "confirmation_fingerprint": digest(confirmed), "cohort_fingerprint": cohort["fingerprint"],
         "proposal_set_fingerprint": digest(proposals), "vectors_fingerprint": digest(vectors),
         "m2_bundle_fingerprint": m2["fingerprint"]}, False)
