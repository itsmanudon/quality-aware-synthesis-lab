# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportCallIssue=false, reportGeneralTypeIssues=false, reportOperatorIssue=false, reportIndexIssue=false, reportOptionalMemberAccess=false
"""M1.5 diagnostic-only analysis over a completed run directory.

Nothing here changes B1/B2/B3 acceptance.  Two families of read-only measurement:

* **Copying diagnostics** - for every raw candidate, three independent booleans:
  ``exact_synthetic_duplicate`` (a repeat of an earlier record in the same raw
  pool), ``exact_reference_match`` (byte-equal to a TRAIN reference example that
  was shown in the generation prompt) and ``exact_nonreference_train_match``
  (byte-equal to a TRAIN row that was *not* shown as a reference).  These are
  copying diagnostics, not privacy claims.

* **TRAIN-support distances** - a deterministic, learning-free nearest-neighbour
  distance from each candidate to the REAL TRAIN split, after TRAIN-only
  standardisation.  These are exploratory only: no thresholds, no acceptance
  effect, and the numbers are not validity probabilities.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from rcqasyn.datasets import DatasetRegistry, load_dataset
from rcqasyn.datasets.split import SplitManifest, _subset_fingerprint, validate_partition
from rcqasyn.storage.artifacts import immutable_text_stream, write_json, write_text
from rcqasyn.storage.ownership import file_hash, seal_bundle
from rcqasyn.utils.hashing import sha256_text

from .readers import derived_directory, read_bundle, validate_source

_MISSING = "<NULL>"


def _canonical(data: dict[str, Any], columns: list[str]) -> str:
    """Canonical hash of a record projected onto ``columns`` (order-independent)."""

    projected = {}
    for column in columns:
        value = data.get(column, _MISSING)
        if isinstance(value, float) and math.isnan(value):
            value = _MISSING
        if value is None:
            value = _MISSING
        projected[str(column)] = value
    return sha256_text(json.dumps(projected, sort_keys=True, separators=(",", ":"), default=str))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def _load_context(run_dir: Path, project_root: Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    manifest = validate_source(run_dir)
    profile = json.loads((run_dir / "dataset" / "profile.json").read_text(encoding="utf-8"))
    registry = DatasetRegistry(project_root=project_root)
    spec = registry.get(str(manifest["dataset_id"]))
    dataset = load_dataset(spec, registry)
    recorded = json.loads((run_dir / "dataset" / "split_manifest.json").read_text(encoding="utf-8"))
    split = SplitManifest(**{key: tuple(value) if key.endswith("_indices") else value
                             for key, value in recorded.items() if key != "split_fingerprint"})
    try:
        validate_partition(dataset, split)
    except ValueError as error:
        raise ValueError(f"diagnostic source provenance error: {error}") from error
    if (dataset.fingerprint != recorded["dataset_fingerprint"]
            or manifest.get("dataset_fingerprint") != dataset.fingerprint
            or split.train_fingerprint != _subset_fingerprint(dataset.frame, list(split.train_indices))
            or split.test_fingerprint != _subset_fingerprint(dataset.frame, list(split.test_indices))
            or split.to_dict()["split_fingerprint"] != recorded.get("split_fingerprint")
            or profile.get("split_fingerprint") != recorded.get("split_fingerprint")
            or tuple(profile.get("train_indices", [])) != split.train_indices):
        raise ValueError("diagnostic source provenance does not match recorded dataset/split")
    columns = [*spec.feature_columns, spec.target_column]
    if list(profile["feature_columns"]) != list(spec.feature_columns) or profile["target_column"] != spec.target_column:
        raise ValueError("diagnostic source provenance does not match feature schema")
    if manifest.get("schema_version") == "m1-run-v2":
        saved = json.loads((run_dir / "scientific_specification.json").read_text(encoding="utf-8"))
        definition = spec.model_dump(mode="json", exclude={"raw_path", "accepted_filenames", "display_name"})
        if (saved["specification"]["dataset"]["definition"] != definition
                or saved["specification"]["dataset"]["raw_source_sha256"] != file_hash(dataset.path)):
            raise ValueError("diagnostic source provenance does not match dataset specification")
    train = dataset.frame.loc[list(split.train_indices)]
    columns = [*spec.feature_columns, spec.target_column]
    reference_indices = set(profile.get("reference_indices") or [])
    reference_hashes = {_canonical(row, columns) for row in profile.get("reference_examples", [])}
    train_hashes: dict[str, bool] = {}  # hash -> is_reference
    for idx, (_, row) in zip(split.train_indices, train[columns].iterrows()):
        h = _canonical({c: row[c] for c in columns}, columns)
        train_hashes[h] = train_hashes.get(h, False) or (idx in reference_indices)
    return {
        "run_dir": run_dir, "manifest": manifest, "profile": profile, "spec": spec,
        "dataset": dataset, "split": split, "train": train, "columns": columns,
        "reference_hashes": reference_hashes, "train_hashes": train_hashes,
        "target_column": spec.target_column,
        "numerical_columns": list(spec.numerical_columns),
        "categorical_columns": list(spec.categorical_columns),
    }


# --------------------------------------------------------------------------- #
# Copying diagnostics
# --------------------------------------------------------------------------- #

def copying_diagnostics(run_dir: Path, project_root: Path, *, write: bool = True, output_dir: Path | None = None) -> dict[str, Any]:
    ctx = _load_context(Path(run_dir), Path(project_root))
    columns = ctx["columns"]
    target = ctx["target_column"]
    reference_hashes: set[str] = ctx["reference_hashes"]
    train_hashes: dict[str, bool] = ctx["train_hashes"]
    raw = _read_jsonl(Path(run_dir) / "candidates_raw.jsonl")

    seen: set[str] = set()
    per_record: list[dict[str, Any]] = []
    for candidate in raw:
        data = candidate.get("data", {})
        h = _canonical(data, columns)
        is_dup = h in seen
        seen.add(h)
        in_train = h in train_hashes
        per_record.append({
            "record_id": candidate["record_id"],
            "requested_class": candidate.get("metadata", {}).get("requested_class"),
            "target_class": str(data.get(target)) if data.get(target) is not None else None,
            "canonical_hash": h,
            "exact_synthetic_duplicate": is_dup,
            "exact_reference_match": h in reference_hashes,
            "exact_nonreference_train_match": in_train and h not in reference_hashes,
        })

    def _agg(rows: list[dict[str, Any]]) -> dict[str, Any]:
        n = len(rows)
        uniq = len({r["canonical_hash"] for r in rows})
        return {
            "records": n,
            "unique_records": uniq,
            "exact_synthetic_duplicate": sum(r["exact_synthetic_duplicate"] for r in rows),
            "exact_synthetic_duplicate_rate": (n - uniq) / n if n else None,
            "exact_reference_match": sum(r["exact_reference_match"] for r in rows),
            "exact_reference_match_rate": (sum(r["exact_reference_match"] for r in rows) / n) if n else None,
            "exact_nonreference_train_match": sum(r["exact_nonreference_train_match"] for r in rows),
            "exact_nonreference_train_match_rate": (sum(r["exact_nonreference_train_match"] for r in rows) / n) if n else None,
        }

    by_target = {lbl: _agg([r for r in per_record if r["target_class"] == lbl])
                 for lbl in sorted({r["target_class"] for r in per_record if r["target_class"] is not None})}
    by_requested = {lbl: _agg([r for r in per_record if r["requested_class"] == lbl])
                    for lbl in sorted({r["requested_class"] for r in per_record if r["requested_class"] is not None})}
    result = {
        "schema_version": "m1-5-copying-diagnostics-v1",
        "run_id": ctx["manifest"].get("run_id"),
        "dataset_id": ctx["manifest"].get("dataset_id"),
        "note": "copying diagnostics only; not a privacy or disclosure claim",
        "reference_examples_shown": len(ctx["profile"].get("reference_examples", [])),
        "overall": _agg(per_record),
        "by_target_class": by_target,
        "by_requested_class": by_requested,
        "records": per_record,
    }
    if write:
        directory = derived_directory(Path(run_dir), "copying", output_dir)
        result["artifact_dir"] = str(directory)
        write_json(directory / "copying_diagnostics.json", result)
        seal_bundle(directory)
    return result


# --------------------------------------------------------------------------- #
# TRAIN-support nearest-neighbour distances (diagnostic only)
# --------------------------------------------------------------------------- #

def _encode(frame: pd.DataFrame, numerical: list[str], categorical: list[str],
            means: dict[str, float], stds: dict[str, float],
            cat_levels: dict[str, list[str]]) -> np.ndarray:
    parts: list[np.ndarray] = []
    for column in numerical:
        values = pd.to_numeric(frame.get(column), errors="coerce").to_numpy(dtype=float)
        std = stds[column]
        parts.append((values - means[column]) / std if std > 0 else np.zeros_like(values))
    for column in categorical:
        series = frame.get(column)
        col_values = series.astype("string").to_numpy() if series is not None else np.array([None] * len(frame))
        for level in cat_levels[column]:
            parts.append((col_values == level).astype(float))
    if not parts:
        return np.zeros((len(frame), 0))
    return np.nan_to_num(np.column_stack(parts), nan=0.0)


def support_diagnostics(run_dir: Path, project_root: Path, *, write: bool = True, output_dir: Path | None = None) -> dict[str, Any]:
    ctx = _load_context(Path(run_dir), Path(project_root))
    target = ctx["target_column"]
    numerical: list[str] = ctx["numerical_columns"]
    categorical: list[str] = ctx["categorical_columns"]
    train: pd.DataFrame = ctx["train"]

    means = {c: float(pd.to_numeric(train[c], errors="coerce").mean()) for c in numerical}
    stds = {c: float(pd.to_numeric(train[c], errors="coerce").std(ddof=0)) for c in numerical}
    cat_levels = {c: sorted(map(str, ctx["profile"].get("domains", {}).get(c, [])
                                or pd.Series(train[c]).dropna().astype(str).unique().tolist()))
                  for c in categorical}

    train_vec = _encode(train, numerical, categorical, means, stds, cat_levels)
    train_labels = train[target].astype(str).to_numpy()

    raw = _read_jsonl(Path(run_dir) / "candidates_raw.jsonl")
    cand_frame = pd.DataFrame([c.get("data", {}) for c in raw])
    cand_vec = _encode(cand_frame, numerical, categorical, means, stds, cat_levels)

    rows: list[dict[str, Any]] = []
    for i, candidate in enumerate(raw):
        diff = train_vec - cand_vec[i]
        dist = np.sqrt(np.einsum("ij,ij->i", diff, diff))
        label = str(cand_frame.iloc[i].get(target))
        same = train_labels == label
        other = ~same
        rows.append({
            "record_id": candidate["record_id"],
            "requested_class": candidate.get("metadata", {}).get("requested_class"),
            "target_class": label,
            "nearest_train_distance": float(dist.min()) if len(dist) else None,
            "nearest_same_class_train_distance": float(dist[same].min()) if same.any() else None,
            "nearest_other_class_train_distance": float(dist[other].min()) if other.any() else None,
        })

    def _summ(values: list[float]) -> dict[str, Any]:
        arr = np.array([v for v in values if v is not None], dtype=float)
        if not len(arr):
            return {"count": 0}
        return {
            "count": len(arr), "min": float(arr.min()), "p10": float(np.percentile(arr, 10)),
            "median": float(np.median(arr)), "mean": float(arr.mean()),
            "p90": float(np.percentile(arr, 90)), "max": float(arr.max()),
        }

    labels = sorted({r["target_class"] for r in rows})
    summary = {
        "schema_version": "m1-5-support-diagnostics-v1",
        "run_id": ctx["manifest"].get("run_id"),
        "dataset_id": ctx["manifest"].get("dataset_id"),
        "note": "diagnostic only: learning-free standardized Euclidean NN distance to REAL TRAIN; "
                "no thresholds, not a validity probability",
        "distance_representation": {
            "numerical": "z-score standardized with TRAIN mean/std (ddof=0); zero-variance columns dropped",
            "categorical": "one-hot over TRAIN domain levels, unit weight; a nominal mismatch "
                           "contributes sqrt(2) to the Euclidean distance (conservative, learning-free)",
            "categorical_columns": categorical,
        },
        "overall": {
            "nearest_train_distance": _summ([r["nearest_train_distance"] for r in rows]),
            "nearest_same_class_train_distance": _summ([r["nearest_same_class_train_distance"] for r in rows]),
            "nearest_other_class_train_distance": _summ([r["nearest_other_class_train_distance"] for r in rows]),
        },
        "by_target_class": {
            lbl: {
                "nearest_train_distance": _summ([r["nearest_train_distance"] for r in rows if r["target_class"] == lbl]),
                "nearest_same_class_train_distance": _summ([r["nearest_same_class_train_distance"] for r in rows if r["target_class"] == lbl]),
            }
            for lbl in labels
        },
        "exact_train_contact_count": sum(1 for r in rows if (r["nearest_train_distance"] or 1.0) == 0.0),
        "train_rows": len(train),
    }
    if write:
        directory = derived_directory(Path(run_dir), "support", output_dir)
        summary["artifact_dir"] = str(directory)
        write_text(directory / "support_diagnostics.jsonl", "\n".join(json.dumps(r, sort_keys=True, allow_nan=False) for r in rows) + ("\n" if rows else ""))
        write_json(directory / "support_summary.json", summary)
        seal_bundle(directory)
    summary["records"] = rows
    return summary


def classify_b2_reason(reason: str, reasons: str = "") -> str:
    """dataset redundancy vs structural/domain failure (M1.5 §15)."""

    blob = f"{reason} {reasons}".lower()
    if "duplicate" in blob or "redundan" in blob:
        return "dataset_redundancy"
    if any(tok in blob for tok in ("schema", "missing", "categor", "domain", "target", "range", "type")):
        return "structural_domain_failure"
    return "other"


# --------------------------------------------------------------------------- #
# Cross-run roll-ups
# --------------------------------------------------------------------------- #

def _dup_block(comparison: dict[str, Any]) -> dict[str, Any]:
    b1 = comparison.get("baselines", {}).get("b1", {})
    raw = b1.get("raw_pool_count") or comparison.get("raw_pool_count")
    dup = b1.get("exact_duplicate_count")
    by_class = b1.get("exact_duplicate_by_class", {})
    minority = comparison.get("minority_analysis", {})
    return {
        "requested": comparison.get("requested"),
        "raw_pool_count": raw,
        "unique_count": b1.get("unique_count"),
        "exact_duplicate_count": dup,
        "exact_duplicate_rate": (dup / raw) if raw else None,
        "exact_duplicate_by_class": by_class,
        "minority_label": minority.get("requested_minority_label"),
        "minority_duplicate_count": minority.get("minority_duplicate_count"),
        "minority_duplicate_rate": minority.get("minority_duplicate_rate"),
    }


def diversity_scaling(prior_run_dirs: list[Path], p1_run_dirs: list[Path]) -> dict[str, Any]:
    """Compare exact-duplicate behaviour between the prior pilot and P1 (M1.5 §21)."""

    def _index(dirs: list[Path]) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for run_dir in dirs:
            cmp = read_bundle(Path(run_dir))
            dataset_id = str(cmp.get("dataset_id"))
            if dataset_id in out:
                raise ValueError("diversity_scaling requires one explicit execution per dataset on each side")
            out[dataset_id] = _dup_block(cmp)
        return out

    prior = _index(prior_run_dirs)
    p1 = _index(p1_run_dirs)
    rows = []
    for dataset_id in sorted(set(prior) | set(p1)):
        a, b = prior.get(dataset_id, {}), p1.get(dataset_id, {})
        rows.append({
            "dataset_id": dataset_id,
            "prior_requested": a.get("requested"), "p1_requested": b.get("requested"),
            "prior_unique": a.get("unique_count"), "p1_unique": b.get("unique_count"),
            "prior_duplicate_rate": a.get("exact_duplicate_rate"),
            "p1_duplicate_rate": b.get("exact_duplicate_rate"),
            "prior_duplicate_by_class": a.get("exact_duplicate_by_class"),
            "p1_duplicate_by_class": b.get("exact_duplicate_by_class"),
            "prior_minority_duplicate_rate": a.get("minority_duplicate_rate"),
            "p1_minority_duplicate_rate": b.get("minority_duplicate_rate"),
        })
    return {"schema_version": "m1-5-diversity-scaling-v1", "no_significance_claim": True, "datasets": rows}


# --------------------------------------------------------------------------- #
# P1 cross-dataset human-review sample
# --------------------------------------------------------------------------- #

_HUMAN_COLUMNS = ("human_valid", "human_failure_type", "human_severity",
                  "human_affected_fields", "human_notes")


def _run_candidate_table(run_dir: Path, project_root: Path) -> list[dict[str, Any]]:
    run_dir = Path(run_dir)
    manifest = validate_source(run_dir)
    raw = _read_jsonl(run_dir / "candidates_raw.jsonl")
    b2 = {r["candidate_id"]: r for r in _read_jsonl(run_dir / "baselines" / "b2" / "decisions.jsonl")}
    b3 = {r["candidate_id"]: r for r in _read_jsonl(run_dir / "baselines" / "b3" / "decisions.jsonl")}
    judge = {str(r.get("candidate_id")): r for r in _read_jsonl(run_dir / "baselines" / "b3" / "judge_results.jsonl")}
    traces = {t.get("call_id"): t for t in _read_jsonl(run_dir / "provider_calls.jsonl") if t.get("role") == "generation"}
    copying = {r["record_id"]: r for r in copying_diagnostics(run_dir, project_root, write=False)["records"]}
    support = {r["record_id"]: r for r in support_diagnostics(run_dir, project_root, write=False)["records"]}

    dists = sorted(v["nearest_train_distance"] for v in support.values() if v["nearest_train_distance"] is not None)
    low_cut = dists[len(dists) // 3] if dists else 0.0
    high_cut = dists[(2 * len(dists)) // 3] if dists else 0.0
    minority_label = str(manifest.get("minority_label") or "positive")

    seen_hash: set[str] = set()
    rows: list[dict[str, Any]] = []
    for candidate in raw:
        rid = str(candidate["record_id"])
        cp = copying.get(rid, {})
        h = cp.get("canonical_hash", "")
        first_occurrence = h not in seen_hash
        seen_hash.add(h)
        sup = support.get(rid, {})
        b2d = b2.get(rid, {"accepted": False, "reason": ""})
        b3d = b3.get(rid, {"accepted": False, "reason": ""})
        call_id = candidate.get("metadata", {}).get("provider_call_id")
        trace = traces.get(call_id, {})
        req_class = candidate.get("metadata", {}).get("requested_class")
        dist = sup.get("nearest_train_distance")
        rows.append({
            "run_id": manifest.get("run_id"), "dataset_id": manifest.get("dataset_id"),
            "record_id": rid, "candidate_version": candidate.get("version"),
            "requested_class": req_class,
            "target_class": cp.get("target_class"),
            "role": "minority" if req_class == minority_label else "majority",
            "canonical_hash": h, "first_occurrence": first_occurrence,
            "provider_call_id": call_id,
            "batch_index": trace.get("metadata", {}).get("batch_index"),
            "provider_seed": trace.get("seed"),
            "b1_status": "accepted",
            "b2_status": "accepted" if b2d.get("accepted") else "rejected",
            "b2_reason": str(b2d.get("reason", "")),
            "b2_reason_class": classify_b2_reason(str(b2d.get("reason", ""))),
            "b3_status": "accepted" if b3d.get("accepted") else "rejected",
            "b3_score": judge.get(rid, {}).get("score"),
            "exact_synthetic_duplicate": bool(cp.get("exact_synthetic_duplicate")),
            "exact_reference_match": bool(cp.get("exact_reference_match")),
            "exact_nonreference_train_match": bool(cp.get("exact_nonreference_train_match")),
            "nearest_train_distance": dist,
            "nearest_same_class_train_distance": sup.get("nearest_same_class_train_distance"),
            "distance_band": (
                "low" if dist is not None and dist <= low_cut
                else "high" if dist is not None and dist >= high_cut
                else "mid"
            ),
            "candidate_json": json.dumps(candidate.get("data", {}), sort_keys=True, separators=(",", ":")),
            "raw_output": str(candidate.get("raw_output") or ""),
        })
    return rows


def p1_human_review_sample(
    run_dirs: list[Path], project_root: Path, out_path: Path, *, target: int = 120, seed: int = 42,
) -> dict[str, Any]:
    """Deterministic, stratified sample of UNIQUE P1 candidates with blank human fields."""

    import csv

    tables = {Path(d).name: _run_candidate_table(d, project_root) for d in run_dirs}
    datasets = sorted(tables)
    per_dataset_quota = max(1, target // max(1, len(datasets)))

    def strata(row: dict[str, Any]) -> list[str]:
        tags = [row["role"]]
        if row["b2_status"] == "rejected":
            tags.append("b2_rejected")
        if row["b3_status"] == "rejected":
            tags.append("b3_rejected")
        if (row["b2_status"] == "accepted") != (row["b3_status"] == "accepted"):
            tags.append("b2_b3_disagreement")
        if row["b2_status"] == "accepted" and row["b3_status"] == "accepted":
            tags.append("b1_b2_b3_accepted")
        if row["exact_reference_match"]:
            tags.append("reference_copy")
        elif row["exact_nonreference_train_match"]:
            tags.append("nonreference_train_copy")
        else:
            tags.append("non_copy")
        if row["distance_band"] == "low":
            tags.append("low_train_distance")
        elif row["distance_band"] == "high":
            tags.append("high_train_distance")
        return tags

    def order_key(stratum: str, row: dict[str, Any]) -> str:
        return hashlib.sha256(
            f"{seed}:{stratum}:{row['run_id']}:{row['record_id']}".encode()).hexdigest()

    selected: dict[tuple[str, str], dict[str, Any]] = {}
    strata_hits: dict[str, int] = {}
    for name in datasets:
        eligible = [r for r in tables[name] if r["first_occurrence"]]
        buckets: dict[str, list[dict[str, Any]]] = {}
        for row in eligible:
            for stratum in strata(row):
                buckets.setdefault(stratum, []).append(row)
        for stratum, bucket in buckets.items():
            bucket.sort(key=lambda r, s=stratum: order_key(s, r))
        cursors = dict.fromkeys(buckets, 0)
        picked = 0
        stratum_cycle = sorted(buckets)
        progressed = True
        while picked < per_dataset_quota and progressed:
            progressed = False
            for stratum in stratum_cycle:
                if picked >= per_dataset_quota:
                    break
                bucket = buckets[stratum]
                while cursors[stratum] < len(bucket):
                    row = bucket[cursors[stratum]]
                    cursors[stratum] += 1
                    key = (name, row["record_id"])
                    if key in selected:
                        continue
                    selected[key] = row
                    strata_hits[stratum] = strata_hits.get(stratum, 0) + 1
                    picked += 1
                    progressed = True
                    break

    rows = sorted(selected.values(), key=lambda r: (str(r["dataset_id"]), r["role"], r["record_id"]))
    by_dataset: dict[str, int] = {}
    for row in rows:
        by_dataset[str(row["dataset_id"])] = by_dataset.get(str(row["dataset_id"]), 0) + 1
    fieldnames = [
        "run_id", "dataset_id", "record_id", "candidate_version", "requested_class", "target_class",
        "role", "canonical_hash", "provider_call_id", "batch_index", "provider_seed",
        "b1_status", "b2_status", "b2_reason", "b2_reason_class", "b3_status", "b3_score",
        "exact_synthetic_duplicate", "exact_reference_match", "exact_nonreference_train_match",
        "nearest_train_distance", "nearest_same_class_train_distance", "distance_band",
        "candidate_json", "raw_output", *_HUMAN_COLUMNS,
    ]
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with immutable_text_stream(out_path) as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({**{k: row.get(k, "") for k in fieldnames}, **dict.fromkeys(_HUMAN_COLUMNS, "")})
    return {
        "schema_version": "m1-5-p1-human-review-v1",
        "path": str(out_path), "row_count": len(rows),
        "unique_canonical_hashes": len({r["canonical_hash"] for r in rows}),
        "by_dataset": by_dataset,
        "strata_hits": strata_hits,
        "human_columns_blank": True,
    }

