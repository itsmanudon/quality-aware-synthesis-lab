# pyright: reportArgumentType=false
"""Machine-only pilot analysis and human-review export helpers.

Automated failure categories and human adjudication are intentionally kept in
separate fields.  In particular, this module never infers a human-validity
label from a B2/B3 decision.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

HUMAN_FAILURE_TAXONOMY = (
    "NONE",
    "PARSE",
    "SCHEMA",
    "MISSING_FIELD",
    "INVALID_CATEGORY",
    "TARGET_MISMATCH",
    "NUMERIC_OUTLIER",
    "LOGICAL_INCONSISTENCY",
    "STATISTICAL_IMPLAUSIBILITY",
    "DUPLICATE",
    "SEMANTIC_IMPLAUSIBILITY",
    "OTHER",
)
HUMAN_COLUMNS = (
    "human_valid",
    "human_failure_type",
    "human_severity",
    "human_affected_fields",
    "human_notes",
)
REVIEW_COLUMNS = (
    "run_id",
    "dataset_id",
    "record_id",
    "candidate_version",
    "target_class",
    "b1_status",
    "b2_status",
    "b2_reasons",
    "b3_status",
    "b3_score",
    "b3_reasons",
    # Compatibility columns retained for consumers of the first pilot export.
    "candidate_id",
    "category",
    "candidate_json",
    "raw_output",
    "b2_accepted",
    "b2_reason",
    "b3_accepted",
    "b3_reason",
    *HUMAN_COLUMNS,
)


REVIEW_CATEGORIES = (
    "B1 accepted",
    "B2 rejected",
    "B3 rejected",
    "B2 accepted+B3 rejected",
    "B2 rejected+B3 accepted",
)

# This export is intentionally machine-only.  It contains every parseable
# candidate for which deterministic B2 and single-judge B3 disagree, without
# adjudication or an inferred validity label.
DISAGREEMENT_COLUMNS = (
    "run_id",
    "dataset_id",
    "record_id",
    "candidate_version",
    "target_class",
    "b2_status",
    "b2_reasons",
    "b3_status",
    "b3_score",
    "b3_reasons",
    "candidate_json",
    "raw_output",
)


def export_human_review(run_dir: Path, *, overwrite: bool = False, seed: int = 42, cap_per_category: int = 5) -> Path:
    """Export a deterministic, bounded review sample for each available category."""

    run_dir = Path(run_dir)
    if cap_per_category < 0:
        raise ValueError("cap_per_category must be non-negative")
    manifest = _read_json(run_dir / "manifest.json")
    raw = _read_jsonl(run_dir / "candidates_raw.jsonl")
    b2 = {item["candidate_id"]: item for item in _read_jsonl(run_dir / "baselines" / "b2" / "decisions.jsonl")}
    b3 = {item["candidate_id"]: item for item in _read_jsonl(run_dir / "baselines" / "b3" / "decisions.jsonl")}
    evidence_by_candidate: dict[str, list[dict[str, Any]]] = {}
    for item in _read_jsonl(run_dir / "baselines" / "b2" / "evidence.jsonl"):
        evidence_by_candidate.setdefault(str(item.get("candidate_id", "")), []).append(item)
    judge_results = {str(item.get("candidate_id", "")): item for item in _read_jsonl(run_dir / "baselines" / "b3" / "judge_results.jsonl")}
    candidates_by_category: dict[str, list[dict[str, str]]] = {category: [] for category in REVIEW_CATEGORIES}
    for candidate in raw:
        candidate_id = str(candidate["record_id"])
        b2_decision = b2.get(candidate_id, {"accepted": False, "reason": "missing decision"})
        b3_decision = b3.get(candidate_id, {"accepted": False, "reason": "missing decision"})
        b2_ok = bool(b2_decision.get("accepted"))
        b3_ok = bool(b3_decision.get("accepted"))
        categories = ["B1 accepted"]
        if not b2_ok:
            categories.append("B2 rejected")
        if not b3_ok:
            categories.append("B3 rejected")
        if b2_ok and not b3_ok:
            categories.append("B2 accepted+B3 rejected")
        if not b2_ok and b3_ok:
            categories.append("B2 rejected+B3 accepted")
        b2_reasons = _b2_reasons(evidence_by_candidate.get(candidate_id, []), str(b2_decision.get("reason", "")))
        judge_result = judge_results.get(candidate_id, {})
        b3_reasons = _join_reasons(judge_result.get("reasons")) or str(b3_decision.get("reason", ""))
        b3_score = judge_result.get("score")
        target_class = _target_class(candidate.get("data", {}))
        row = {
            "run_id": str(manifest.get("run_id", run_dir.name)),
            "dataset_id": str(manifest.get("dataset_id", "")),
            "record_id": candidate_id,
            "candidate_version": str(candidate.get("version", "")),
            "target_class": target_class,
            "b1_status": "accepted",
            "b2_status": "accepted" if b2_ok else "rejected",
            "b2_reasons": b2_reasons,
            "b3_status": "accepted" if b3_ok else "rejected",
            "b3_score": "" if b3_score is None else str(b3_score),
            "b3_reasons": b3_reasons,
            "candidate_id": candidate_id,
            "category": "",
            "candidate_json": json.dumps(candidate.get("data", {}), sort_keys=True, separators=(",", ":")),
            "raw_output": str(candidate.get("raw_output") or ""),
            "b2_accepted": str(b2_ok).lower(),
            "b2_reason": str(b2_decision.get("reason", "")),
            "b3_accepted": str(b3_ok).lower(),
            "b3_reason": str(b3_decision.get("reason", "")),
            **{column: "" for column in HUMAN_COLUMNS},
        }
        for category in categories:
            selected = dict(row)
            selected["category"] = category
            candidates_by_category[category].append(selected)
    rows: list[dict[str, str]] = []
    for category, category_rows in candidates_by_category.items():
        category_rows.sort(key=lambda row: hashlib.sha256(f"{seed}:{category}:{row['record_id']}".encode()).hexdigest())
        rows.extend(category_rows[:cap_per_category])
    rows.sort(key=lambda row: (row["category"], row["record_id"]))
    destination = run_dir / "human_review.csv"
    if destination.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing artifact: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(REVIEW_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    return destination


def export_disagreements(run_dir: Path, *, overwrite: bool = False) -> Path:
    """Export all B2/B3 status disagreements without adjudication."""

    run_dir = Path(run_dir)
    manifest = _read_json(run_dir / "manifest.json")
    raw = _read_jsonl(run_dir / "candidates_raw.jsonl")
    b2 = {item["candidate_id"]: item for item in _read_jsonl(run_dir / "baselines" / "b2" / "decisions.jsonl")}
    b3 = {item["candidate_id"]: item for item in _read_jsonl(run_dir / "baselines" / "b3" / "decisions.jsonl")}
    evidence_by_candidate: dict[str, list[dict[str, Any]]] = {}
    for item in _read_jsonl(run_dir / "baselines" / "b2" / "evidence.jsonl"):
        evidence_by_candidate.setdefault(str(item.get("candidate_id", "")), []).append(item)
    judge_results = {str(item.get("candidate_id", "")): item for item in _read_jsonl(run_dir / "baselines" / "b3" / "judge_results.jsonl")}
    rows: list[dict[str, str]] = []
    for candidate in raw:
        candidate_id = str(candidate["record_id"])
        b2_decision = b2.get(candidate_id, {"accepted": False, "reason": "missing decision"})
        b3_decision = b3.get(candidate_id, {"accepted": False, "reason": "missing decision"})
        b2_ok = bool(b2_decision.get("accepted"))
        b3_ok = bool(b3_decision.get("accepted"))
        if b2_ok == b3_ok:
            continue
        judge_result = judge_results.get(candidate_id, {})
        rows.append({
            "run_id": str(manifest.get("run_id", run_dir.name)),
            "dataset_id": str(manifest.get("dataset_id", "")),
            "record_id": candidate_id,
            "candidate_version": str(candidate.get("version", "")),
            "target_class": _target_class(candidate.get("data", {})),
            "b2_status": "accepted" if b2_ok else "rejected",
            "b2_reasons": _b2_reasons(evidence_by_candidate.get(candidate_id, []), str(b2_decision.get("reason", ""))),
            "b3_status": "accepted" if b3_ok else "rejected",
            "b3_score": "" if judge_result.get("score") is None else str(judge_result.get("score")),
            "b3_reasons": _join_reasons(judge_result.get("reasons")) or str(b3_decision.get("reason", "")),
            "candidate_json": json.dumps(candidate.get("data", {}), sort_keys=True, separators=(",", ":")),
            "raw_output": str(candidate.get("raw_output") or ""),
        })
    rows.sort(key=lambda row: row["record_id"])
    destination = run_dir / "b2_b3_disagreements.csv"
    if destination.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing artifact: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(DISAGREEMENT_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    return destination


def analyze_human_review(path: Path) -> dict[str, Any]:
    """Compute B3 false accepts/rejects only from populated human fields."""

    with Path(path).open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    populated = [row for row in rows if any(str(row.get(column, "")).strip() for column in HUMAN_COLUMNS)]
    adjudicated = [row for row in populated if _bool_or_none(row.get("human_valid", "")) is not None]
    partial = len(adjudicated) != len(populated)
    if not populated:
        return {
            "status": "not_evaluable",
            "reason": "human adjudication fields are empty",
            "review_rows": len(rows),
            "b3_false_accepts": None,
            "b3_false_rejects": None,
        }
    if not adjudicated:
        return {
            "status": "partial",
            "reason": "review fields exist but human_valid is not explicitly true/false",
            "review_rows": len(rows),
            "adjudicated_rows": 0,
            "b3_false_accepts": None,
            "b3_false_rejects": None,
        }
    false_accepts = 0
    false_rejects = 0
    invalid_taxonomy = 0
    for row in populated:
        human_valid = _bool_or_none(row.get("human_valid", ""))
        b3_accepted = _bool_or_none(row.get("b3_accepted", ""))
        if human_valid is None or b3_accepted is None:
            continue
        if b3_accepted and not human_valid:
            false_accepts += 1
        if not b3_accepted and human_valid:
            false_rejects += 1
        # Multi-label is permitted: separate labels with '|', ';' or ','.
        failure_type = str(row.get("human_failure_type", "")).strip()
        labels = [token.strip() for token in re.split(r"[|;,]", failure_type) if token.strip()]
        if labels and any(label not in HUMAN_FAILURE_TAXONOMY for label in labels):
            invalid_taxonomy += 1
    return {
        "status": "partial" if partial else "ok",
        "review_rows": len(rows),
        "adjudicated_rows": len(adjudicated),
        "b3_false_accepts": false_accepts,
        "b3_false_rejects": false_rejects,
        "invalid_failure_taxonomy": invalid_taxonomy,
    }


def machine_failure_report(comparison: dict[str, Any]) -> dict[str, Any]:
    """Return automated failure evidence without adding human conclusions."""

    return {
        "schema_version": "m1-machine-failure-v1",
        "status": "machine_only",
        "failure_aggregation": comparison.get("failure_aggregation", {}),
        "failure_matrix": comparison.get("failure_aggregation", {}),
        "minority_analysis": comparison.get("minority_analysis", {}),
        "metadata": comparison.get("metadata", {}),
        "failure_categories": comparison.get("failure_categories", ()),
        "baseline_comparison": comparison.get("baseline_comparison", []),
        "baselines": {
            name: {
                "requested": value.get("requested"),
                "accepted": value.get("accepted"),
                "acceptance_rate": value.get("acceptance_rate"),
                "failure_counts": value.get("failure_counts", {}),
            }
            for name, value in comparison.get("baselines", {}).items()
        },
        "human_review": {"status": "not_evaluable", "source": "human_review.csv"},
    }


def cross_dataset_comparison(comparisons: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Build a machine-only comparison table from completed run comparisons."""

    rows: list[dict[str, Any]] = []
    failure_matrix: dict[str, dict[str, Any]] = {}
    baseline_tables: dict[str, list[dict[str, Any]]] = {}
    categories = (
        "PARSE", "SCHEMA", "MISSING_FIELD", "INVALID_CATEGORY", "TARGET_MISMATCH",
        "OBSERVED_RANGE_WARNING", "EXACT_DUPLICATE", "B2_REJECTED", "B3_REJECTED",
        "B3_MALFORMED", "PROVIDER_ERROR",
    )
    for comparison in comparisons:
        row_failure_matrix = comparison.get("failure_aggregation", {})
        tstr_pr_auc = {
            name: {
                classifier: {
                    "pr_auc": value.get("utility", {}).get("TSTR", {}).get(classifier, {}).get("pr_auc"),
                    "status": value.get("utility", {}).get("TSTR", {}).get(classifier, {}).get("status", "not_available"),
                }
                for classifier in ("logistic_regression", "random_forest")
            }
            for name, value in comparison.get("baselines", {}).items()
        }
        rows.append({
            "dataset_id": comparison.get("dataset_id"),
            "requested": comparison.get("requested"),
            "raw_pool_count": comparison.get("raw_pool_count"),
            "parse_success_rate": comparison.get("parse_success_rate"),
            "failure_aggregation": comparison.get("failure_aggregation", {}),
            "failure_matrix": row_failure_matrix,
            "tstr_pr_auc": tstr_pr_auc,
            "minority_analysis": comparison.get("minority_analysis", {}),
            "baselines": {
                name: {"accepted": value.get("accepted"), "acceptance_rate": value.get("acceptance_rate")}
                for name, value in comparison.get("baselines", {}).items()
            },
            "human_review": "separate/not_evaluable_until_adjudicated",
        })
        dataset_id = str(comparison.get("dataset_id", ""))
        aggregation = comparison.get("failure_aggregation", {})
        global_failures = aggregation.get("global", {})
        if not global_failures:
            aliases = {
                "PARSE": "parse_failure", "SCHEMA": "schema_failure", "MISSING_FIELD": "missing_field",
                "INVALID_CATEGORY": "invalid_category", "TARGET_MISMATCH": "target_mismatch",
                "OBSERVED_RANGE_WARNING": "range_warning", "EXACT_DUPLICATE": "duplicate",
                "B2_REJECTED": "b2_rejection", "B3_REJECTED": "judge_rejection",
                "B3_MALFORMED": "judge_malformed", "PROVIDER_ERROR": "judge_provider_failure",
            }
            global_failures = {
                category: {
                    "occurrences": int(aggregation.get(alias, 0)),
                    "unique_affected_record_count": int(aggregation.get(alias, 0)),
                    "denominator": comparison.get("requested"),
                    "rate": (int(aggregation.get(alias, 0)) / comparison["requested"] if comparison.get("requested") else None),
                }
                for category, alias in aliases.items()
            }
        for category in categories:
            failure_matrix.setdefault(category, {})[dataset_id] = global_failures.get(category, {})
        baseline_tables[dataset_id] = comparison.get("baseline_comparison", [])
    rows.sort(key=lambda row: str(row.get("dataset_id", "")))
    return {
        "schema_version": "m1-cross-dataset-v1", "status": "machine_only", "no_significance_claim": True,
        "failure_categories": list(categories), "failure_matrix": failure_matrix,
        "baseline_comparison_tables": baseline_tables, "datasets": rows,
    }


def _b2_reasons(evidence: list[dict[str, Any]], fallback: str) -> str:
    reasons = [str(item.get("message", "")) for item in evidence if str(item.get("verdict", "")).lower() in {"fail", "warn"} and item.get("message")]
    return "; ".join(dict.fromkeys(reasons)) or fallback


def _join_reasons(value: object) -> str:
    if isinstance(value, list | tuple):
        return "; ".join(str(item) for item in value)
    return str(value) if value else ""


def _target_class(data: object) -> str:
    if not isinstance(data, dict):
        return ""
    for key in ("class", "label", "target"):
        if key in data and data[key] is not None:
            return str(data[key])
    return ""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _bool_or_none(value: object) -> bool | None:
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    return None
