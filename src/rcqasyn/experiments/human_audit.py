"""External human-annotation validation and M1.6 audit analysis.

This module is deliberately read-only with respect to annotation inputs.  It never
infers human labels from machine decisions or diagnostics.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import mannwhitneyu
from sklearn.metrics import average_precision_score, cohen_kappa_score, roc_auc_score

HUMAN_FAILURE_TAXONOMY = frozenset(
    {
        "NONE",
        "PARSE",
        "SCHEMA",
        "MISSING_FIELD",
        "INVALID_CATEGORY",
        "TARGET_MISMATCH",
        "NUMERIC_OUTLIER",
        "LOGICAL_INCONSISTENCY",
        "STATISTICAL_IMPLAUSIBILITY",
        "SEMANTIC_IMPLAUSIBILITY",
        "DUPLICATE",
        "OTHER",
    }
)
HUMAN_COLUMNS = (
    "human_valid",
    "human_failure_type",
    "human_severity",
    "human_affected_fields",
    "human_notes",
)
REQUIRED_REVIEW_COLUMNS = frozenset(
    {
        "run_id",
        "dataset_id",
        "record_id",
        "requested_class",
        "role",
        "canonical_hash",
        "provider_call_id",
        "provider_seed",
        "b2_status",
        "b2_reason",
        "b3_status",
        "b3_score",
        "exact_synthetic_duplicate",
        "exact_reference_match",
        "exact_nonreference_train_match",
        "nearest_train_distance",
        "nearest_same_class_train_distance",
        *HUMAN_COLUMNS,
    }
)


class HumanAuditError(ValueError):
    """Raised when a review input violates the audit contract."""


class IncompleteAnnotationsError(HumanAuditError):
    """Raised when evaluation is requested before human labels are complete."""


def parse_failure_labels(value: str) -> tuple[str, ...]:
    """Parse multi-label taxonomy text without rewriting or dropping unknown labels."""

    labels: list[str] = []
    for token in re.split(r"[;|,]", value):
        label = token.strip().upper()
        if label and label not in labels:
            labels.append(label)
    return tuple(labels)


def _explicit_bool(value: str, *, field: str, allow_blank: bool = False) -> bool | None:
    normalized = str(value).strip().lower()
    if allow_blank and not normalized:
        return None
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    expected = "blank, true, or false" if allow_blank else "true or false"
    raise HumanAuditError(f"{field} must be {expected}; got {value!r}")


def load_review(path: Path) -> list[dict[str, str]]:
    """Load and structurally validate a human-review CSV."""

    source = Path(path)
    try:
        with source.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            columns = set(reader.fieldnames or ())
            missing = sorted(REQUIRED_REVIEW_COLUMNS - columns)
            if missing:
                raise HumanAuditError(f"missing required review columns: {', '.join(missing)}")
            rows = [{key: str(value or "") for key, value in row.items()} for row in reader]
    except OSError as error:
        raise HumanAuditError(f"cannot read review CSV {source}: {error}") from error

    identities: set[tuple[str, str, str]] = set()
    hashes: set[str] = set()
    for line, row in enumerate(rows, start=2):
        identity = (row["run_id"].strip(), row["dataset_id"].strip(), row["record_id"].strip())
        if not all(identity):
            raise HumanAuditError(f"blank row identity at CSV line {line}")
        if identity in identities:
            raise HumanAuditError(f"duplicate row identity at CSV line {line}: {identity}")
        identities.add(identity)
        canonical_hash = row["canonical_hash"].strip()
        if not canonical_hash:
            raise HumanAuditError(f"blank canonical hash at CSV line {line}")
        if canonical_hash in hashes:
            raise HumanAuditError(f"duplicate canonical hash at CSV line {line}: {canonical_hash}")
        hashes.add(canonical_hash)
        _explicit_bool(
            row["human_valid"], field=f"human_valid at CSV line {line}", allow_blank=True
        )
    return rows


def _counts(rows: list[dict[str, str]], column: str) -> dict[str, int]:
    return dict(sorted(Counter(row[column].strip() or "<blank>" for row in rows).items()))


def _flag_coverage(rows: list[dict[str, str]], column: str) -> dict[str, int]:
    counts = Counter()
    for line, row in enumerate(rows, start=2):
        value = _explicit_bool(row[column], field=f"{column} at CSV line {line}")
        counts[str(value).lower()] += 1
    return dict(sorted(counts.items()))


def review_status(path: Path) -> dict[str, Any]:
    """Return annotation completeness and P1 review coverage without inference."""

    rows = load_review(path)
    human_valid = [
        _explicit_bool(row["human_valid"], field="human_valid", allow_blank=True) for row in rows
    ]
    taxonomy = Counter(
        label for row in rows for label in parse_failure_labels(row["human_failure_type"])
    )
    unknown = Counter(
        {label: count for label, count in taxonomy.items() if label not in HUMAN_FAILURE_TAXONOMY}
    )
    labelled = sum(value is not None for value in human_valid)
    diagnostic_coverage = {
        field: sum(bool(row.get(field, "").strip()) for row in rows)
        for field in (
            "nearest_train_distance",
            "nearest_same_class_train_distance",
            "nearest_other_class_train_distance",
        )
        if any(field in row for row in rows)
    }
    provider_lineage = {
        "provider_call_id": sum(bool(row["provider_call_id"].strip()) for row in rows),
        "provider_seed": sum(bool(row["provider_seed"].strip()) for row in rows),
    }
    return {
        "source": str(Path(path)),
        "rows": len(rows),
        "unique_canonical_hashes": len({row["canonical_hash"] for row in rows}),
        "labelled": labelled,
        "unlabelled": len(rows) - labelled,
        "valid": sum(value is True for value in human_valid),
        "invalid": sum(value is False for value in human_valid),
        "human_fields_blank": all(
            not row[column].strip() for row in rows for column in HUMAN_COLUMNS
        ),
        "taxonomy_counts": dict(sorted(taxonomy.items())),
        "unknown_taxonomy_labels": dict(sorted(unknown.items())),
        "dataset_counts": _counts(rows, "dataset_id"),
        "class_counts": _counts(rows, "requested_class"),
        "role_counts": _counts(rows, "role"),
        "b2_counts": _counts(rows, "b2_status"),
        "b3_counts": _counts(rows, "b3_status"),
        "copying_flag_counts": {
            field: _flag_coverage(rows, field)
            for field in (
                "exact_synthetic_duplicate",
                "exact_reference_match",
                "exact_nonreference_train_match",
            )
        },
        "support_distance_coverage": diagnostic_coverage,
        "provider_lineage_coverage": provider_lineage,
        "analysis_ready": bool(rows) and labelled == len(rows) and not unknown,
    }


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def confusion_metrics(
    human_valid: Sequence[bool], predicted_accept: Sequence[bool]
) -> dict[str, Any]:
    """Evaluate rejection as detection of the positive human-invalid class."""

    pairs = [
        (not valid, not accepted)
        for valid, accepted in zip(human_valid, predicted_accept, strict=True)
    ]
    tp = sum(actual and predicted for actual, predicted in pairs)
    fp = sum(not actual and predicted for actual, predicted in pairs)
    tn = sum(not actual and not predicted for actual, predicted in pairs)
    fn = sum(actual and not predicted for actual, predicted in pairs)
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    specificity = _ratio(tn, tn + fp)
    return {
        "positive_class": "human_invalid",
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": _ratio(2 * tp, 2 * tp + fp + fn),
        "specificity": specificity,
        "balanced_accuracy": (
            (recall + specificity) / 2 if recall is not None and specificity is not None else None
        ),
        "false_accept_rate": _ratio(fn, tp + fn),
        "false_reject_rate": _ratio(fp, tn + fp),
    }


def _human_valid_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return _explicit_bool(str(value), field="human_valid", allow_blank=True)


def _numeric(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise HumanAuditError(f"expected numeric diagnostic value; got {value!r}") from error
    if not np.isfinite(result):
        raise HumanAuditError(f"diagnostic value must be finite; got {value!r}")
    return result


def _distribution(values: Sequence[float], *, histogram: bool = False) -> dict[str, Any]:
    if not values:
        return {"available": False, "count": 0}
    array = np.asarray(values, dtype=float)
    result: dict[str, Any] = {
        "available": True,
        "count": int(array.size),
        "min": float(np.min(array)),
        "p10": float(np.quantile(array, 0.10)),
        "p25": float(np.quantile(array, 0.25)),
        "median": float(np.median(array)),
        "mean": float(np.mean(array)),
        "p75": float(np.quantile(array, 0.75)),
        "p90": float(np.quantile(array, 0.90)),
        "max": float(np.max(array)),
    }
    result["iqr"] = result["p75"] - result["p25"]
    if histogram:
        counts, edges = np.histogram(array, bins=np.linspace(0.0, 1.0, 11))
        result["histogram"] = {
            "bin_edges": [float(value) for value in edges],
            "counts": [int(value) for value in counts],
        }
    return result


def score_distribution(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize uncalibrated B3 validity scores without tuning their threshold."""

    prepared: list[tuple[bool, float, str, str]] = []
    for row in rows:
        valid = _human_valid_value(row.get("human_valid"))
        score = _numeric(row.get("b3_score"))
        if valid is None or score is None:
            continue
        if not 0.0 <= score <= 1.0:
            raise HumanAuditError(f"b3_score must be in [0, 1]; got {score}")
        prepared.append(
            (valid, score, str(row.get("dataset_id", "")), str(row.get("requested_class", "")))
        )

    def grouped(index: int) -> dict[str, Any]:
        names = sorted({str(item[index]) for item in prepared})
        return {
            name: _distribution(
                [item[1] for item in prepared if str(item[index]) == name], histogram=True
            )
            for name in names
        }

    labels = [not item[0] for item in prepared]
    invalidity_scores = [1.0 - item[1] for item in prepared]
    detection: dict[str, Any] = {"score_transform": "1 - b3_score"}
    if len(set(labels)) == 2:
        detection["roc_auc"] = float(roc_auc_score(labels, invalidity_scores))
        detection["pr_auc"] = float(average_precision_score(labels, invalidity_scores))
    else:
        detection.update({"roc_auc": None, "pr_auc": None, "reason": "both human classes required"})
    return {
        "score_semantics": "uncalibrated validity score",
        "threshold_tuned": False,
        "overall": _distribution([item[1] for item in prepared], histogram=True),
        "by_human_valid": {
            "valid": _distribution([item[1] for item in prepared if item[0]], histogram=True),
            "invalid": _distribution([item[1] for item in prepared if not item[0]], histogram=True),
        },
        "by_dataset": grouped(2),
        "by_requested_class": grouped(3),
        "invalid_detection": detection,
    }


def support_distance_analysis(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Compare TRAIN-support diagnostics without defining acceptance thresholds."""

    result: dict[str, Any] = {
        "diagnostic_only": True,
        "thresholds_established": False,
    }
    for field in (
        "nearest_train_distance",
        "nearest_same_class_train_distance",
        "nearest_other_class_train_distance",
    ):
        valid_values: list[float] = []
        invalid_values: list[float] = []
        for row in rows:
            valid = _human_valid_value(row.get("human_valid"))
            value = _numeric(row.get(field))
            if valid is None or value is None:
                continue
            (valid_values if valid else invalid_values).append(value)
        block: dict[str, Any] = {
            "available": bool(valid_values or invalid_values),
            "human_valid": _distribution(valid_values),
            "human_invalid": _distribution(invalid_values),
            "rank_biserial": None,
            "mann_whitney_u": None,
            "mann_whitney_p_value": None,
            "roc_auc": None,
        }
        if valid_values and invalid_values:
            test = mannwhitneyu(invalid_values, valid_values, alternative="two-sided")
            block["mann_whitney_u"] = float(test.statistic)
            block["mann_whitney_p_value"] = float(test.pvalue)
            block["rank_biserial"] = float(
                (2 * test.statistic) / (len(invalid_values) * len(valid_values)) - 1
            )
            labels = [False] * len(valid_values) + [True] * len(invalid_values)
            block["roc_auc"] = float(roc_auc_score(labels, valid_values + invalid_values))
        result[field] = block
    return result


def _annotation_index(rows: Sequence[Mapping[str, str]]) -> dict[tuple[str, str, str], bool]:
    index: dict[tuple[str, str, str], bool] = {}
    for row in rows:
        valid = _explicit_bool(row.get("human_valid", ""), field="human_valid", allow_blank=True)
        if valid is None:
            continue
        identity = (row.get("run_id", ""), row.get("record_id", ""), row.get("canonical_hash", ""))
        if identity in index:
            raise HumanAuditError(f"duplicate annotation identity: {identity}")
        index[identity] = valid
    return index


def annotator_agreement(
    annotation_sets: Mapping[str, Sequence[Mapping[str, str]]],
) -> dict[str, Any]:
    """Calculate pairwise agreement on explicitly labelled overlapping rows."""

    indexed = {name: _annotation_index(rows) for name, rows in sorted(annotation_sets.items())}
    pairs: list[dict[str, Any]] = []
    for left, right in combinations(indexed, 2):
        shared = sorted(set(indexed[left]) & set(indexed[right]))
        left_labels = [indexed[left][identity] for identity in shared]
        right_labels = [indexed[right][identity] for identity in shared]
        pair: dict[str, Any] = {
            "annotators": [left, right],
            "overlap": len(shared),
            "raw_agreement": (
                sum(a == b for a, b in zip(left_labels, right_labels, strict=True)) / len(shared)
                if shared
                else None
            ),
            "cohen_kappa": None,
        }
        if not shared:
            pair["kappa_status"] = "not_computable_no_overlap"
        elif len(set(left_labels + right_labels)) == 1:
            pair["kappa_status"] = "not_computable_constant_labels"
        else:
            pair["cohen_kappa"] = float(cohen_kappa_score(left_labels, right_labels))
            pair["kappa_status"] = "ok"
        pairs.append(pair)
    return {"pairs": pairs, "disagreements_merged": False}


_REDUNDANCY_TOKENS = ("duplicate", "redundan")
_STRUCTURAL_TOKENS = (
    "schema",
    "missing",
    "categor",
    "domain",
    "target",
    "range",
    "numeric",
    "type",
    "constraint",
    "logical",
)


def classify_b2_evidence(evidence: Sequence[Mapping[str, Any]]) -> str:
    """Classify the failing B2 evidence used by the record-validity view."""

    failing: list[str] = []
    for item in evidence:
        verdict = str(item.get("verdict", "")).strip().lower()
        severity = str(item.get("severity", "")).strip().lower()
        if verdict == "fail" or severity == "fail":
            failing.append(
                " ".join(
                    str(item.get(key, ""))
                    for key in ("validator_id", "validator", "dimension", "message")
                ).lower()
            )
    if not failing:
        return "ambiguous"
    has_redundancy = any(any(token in blob for token in _REDUNDANCY_TOKENS) for blob in failing)
    has_structural = any(any(token in blob for token in _STRUCTURAL_TOKENS) for blob in failing)
    if has_structural:
        return "structural_domain"
    if has_redundancy and all(
        any(token in blob for token in _REDUNDANCY_TOKENS) for blob in failing
    ):
        return "redundancy_only"
    return "ambiguous"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as error:
        raise HumanAuditError(f"cannot read B2 evidence {path}: {error}") from error


def _b2_evidence_view(
    rows: Sequence[Mapping[str, str]], project_root: Path
) -> tuple[dict[tuple[str, str], str], list[dict[str, str]]]:
    rejected = [row for row in rows if row["b2_status"].strip().lower() == "rejected"]
    by_key: dict[tuple[str, str], str] = {}
    sources: list[dict[str, str]] = []
    for run_id in sorted({row["run_id"] for row in rejected}):
        path = (
            Path(project_root)
            / "artifacts"
            / "runs"
            / run_id
            / "baselines"
            / "b2"
            / "evidence.jsonl"
        )
        records = _read_jsonl(path)
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in records:
            grouped.setdefault(str(item.get("candidate_id", "")), []).append(item)
        sources.append({"path": str(path), "sha256": _sha256(path)})
        for row in (item for item in rejected if item["run_id"] == run_id):
            key = (run_id, row["record_id"])
            classification = classify_b2_evidence(grouped.get(row["record_id"], []))
            if classification == "ambiguous":
                raise HumanAuditError(
                    f"ambiguous or missing B2 evidence for {run_id}/{row['record_id']}"
                )
            by_key[key] = classification
    return by_key, sources


def _decision_accept(value: str, *, field: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "accepted":
        return True
    if normalized == "rejected":
        return False
    raise HumanAuditError(f"{field} must be accepted or rejected; got {value!r}")


def _source_file(path: Path) -> dict[str, str]:
    return {"path": str(Path(path)), "sha256": _sha256(Path(path))}


def _trace_payload(payload: Mapping[str, Any], trace: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "m1-6-human-audit-v1",
        "source_files": dict(trace),
        **payload,
    }


def _rate_block(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    invalid = sum(not bool(row["human_valid"]) for row in rows)
    return {
        "labelled": total,
        "human_invalid": invalid,
        "human_invalid_rate": invalid / total if total else None,
    }


def _dataset_class_rates(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_dataset = {
        name: _rate_block([row for row in rows if row["dataset_id"] == name])
        for name in sorted({str(row["dataset_id"]) for row in rows})
    }
    by_class = {
        name: _rate_block([row for row in rows if row["requested_class"] == name])
        for name in sorted({str(row["requested_class"]) for row in rows})
    }
    by_dataset_class: dict[str, dict[str, Any]] = {}
    for dataset in by_dataset:
        by_dataset_class[dataset] = {
            class_name: _rate_block(
                [
                    row
                    for row in rows
                    if row["dataset_id"] == dataset and row["requested_class"] == class_name
                ]
            )
            for class_name in sorted(
                {str(row["requested_class"]) for row in rows if row["dataset_id"] == dataset}
            )
        }
    return {
        "by_dataset": by_dataset,
        "by_requested_class": by_class,
        "by_dataset_and_requested_class": by_dataset_class,
    }


_RECORD_FAILURES = (
    "SCHEMA",
    "MISSING_FIELD",
    "INVALID_CATEGORY",
    "TARGET_MISMATCH",
    "NUMERIC_OUTLIER",
    "LOGICAL_INCONSISTENCY",
    "STATISTICAL_IMPLAUSIBILITY",
    "SEMANTIC_IMPLAUSIBILITY",
    "OTHER",
)


def _failure_taxonomy(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    def block(selected: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        counts = Counter(label for row in selected for label in row["human_failure_labels"])
        return {
            "record_level": {label: counts[label] for label in _RECORD_FAILURES},
            "dataset_level": {"DUPLICATE": counts["DUPLICATE"]},
            "legacy": {label: counts[label] for label in ("NONE", "PARSE")},
            "unknown": {
                label: count
                for label, count in sorted(counts.items())
                if label not in HUMAN_FAILURE_TAXONOMY
            },
        }

    overall = block(rows)
    return {
        **overall,
        "by_dataset": {
            dataset: block([row for row in rows if row["dataset_id"] == dataset])
            for dataset in sorted({str(row["dataset_id"]) for row in rows})
        },
        "multi_label_rows": sum(len(row["human_failure_labels"]) > 1 for row in rows),
    }


def _copying_analysis(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "interpretation": "copying is a dataset-quality/diversity diagnostic, not a privacy claim",
        "flags": {},
    }
    for field in (
        "exact_synthetic_duplicate",
        "exact_reference_match",
        "exact_nonreference_train_match",
    ):
        flagged = [row for row in rows if row[field]]
        invalid = sum(not row["human_valid"] for row in flagged)
        result["flags"][field] = {
            "flagged": len(flagged),
            "human_valid": len(flagged) - invalid,
            "human_invalid": invalid,
            "p_human_invalid_given_flag": invalid / len(flagged) if flagged else None,
        }
    references = [row for row in rows if row["exact_reference_match"]]
    result["reference_copy_analysis"] = {
        "records": len(references),
        "human_valid": sum(row["human_valid"] for row in references),
        "human_invalid": sum(not row["human_valid"] for row in references),
        "duplicate_label": sum("DUPLICATE" in row["human_failure_labels"] for row in references),
        "additional_defect_records": sum(
            bool(set(row["human_failure_labels"]) - {"DUPLICATE", "NONE"}) for row in references
        ),
    }
    return result


def _disagreement_rows(
    rows: Sequence[Mapping[str, Any]],
    primary_hash: str,
    evidence_sources: Sequence[Mapping[str, str]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for b2_accept, b3_accept in ((True, True), (True, False), (False, True), (False, False)):
        selected = [
            row
            for row in rows
            if row["b2_accepted"] is b2_accept and row["b3_accepted"] is b3_accept
        ]
        reject_counts = Counter(
            row["b2_reject_class"] for row in selected if not row["b2_accepted"]
        )
        output.append(
            {
                "decision_cell": (
                    f"B2 {'ACCEPT' if b2_accept else 'REJECT'} / "
                    f"B3 {'ACCEPT' if b3_accept else 'REJECT'}"
                ),
                "records": len(selected),
                "human_valid": sum(row["human_valid"] for row in selected),
                "human_invalid": sum(not row["human_valid"] for row in selected),
                "redundancy_only_rejects": reject_counts["redundancy_only"],
                "structural_domain_rejects": reject_counts["structural_domain"],
                "ambiguous_rejects": reject_counts["ambiguous"],
                "source_primary_sha256": primary_hash,
                "source_evidence_hashes": ";".join(source["sha256"] for source in evidence_sources),
            }
        )
    return output


def _markdown_summary(result: Mapping[str, Any]) -> str:
    summary = result["human_summary"]
    b2 = result["b2_human_confusion"]["record_validity_view"]
    b3 = result["b3_human_confusion"]
    sources = summary["source_files"]
    lines = [
        "# M1.6 Human Audit Summary",
        "",
        f"Primary annotation SHA-256: `{sources['primary']['sha256']}`",
    ]
    if "adjudicated" in sources:
        lines.append(f"Adjudicated annotation SHA-256: `{sources['adjudicated']['sha256']}`")
    for name, source in sources.get("annotators", {}).items():
        lines.append(f"Annotator {name} SHA-256: `{source['sha256']}`")
    for source in sources["b2_evidence"]:
        lines.append(f"B2 evidence SHA-256: `{source['sha256']}` ({source['path']})")
    lines.extend(
        [
            "",
            f"Labelled records: {summary['labelled']} / {summary['rows']}",
            f"Human-invalid records: {summary['human_invalid']} ({summary['human_invalid_rate']:.6f})",
            "",
            "## B2 record-validity view",
            "",
            f"TP={b2['tp']}, FP={b2['fp']}, TN={b2['tn']}, FN={b2['fn']}",
            "",
            "## B3 single-judge view",
            "",
            f"TP={b3['tp']}, FP={b3['fp']}, TN={b3['tn']}, FN={b3['fn']}",
            "",
            "B3 remains uncalibrated; no threshold was tuned and no Brier score was calculated.",
            "Support distances remain diagnostic-only and copying is not described as privacy leakage.",
            "",
        ]
    )
    return "\n".join(lines)


_JSON_OUTPUTS = {
    "human_summary": "human_summary.json",
    "b2_human_confusion": "b2_human_confusion.json",
    "b3_human_confusion": "b3_human_confusion.json",
    "b3_score_distribution": "b3_score_distribution.json",
    "copying_vs_human": "copying_vs_human.json",
    "support_distance_vs_human": "support_distance_vs_human.json",
    "failure_taxonomy": "failure_taxonomy.json",
    "dataset_class_human_rates": "dataset_class_human_rates.json",
}


def _prepare_output(output_dir: Path, primary_hash: str, *, overwrite: bool) -> None:
    if not output_dir.exists():
        return
    existing = output_dir / "human_summary.json"
    if not any(output_dir.iterdir()):
        return
    same_source = False
    if existing.is_file():
        try:
            value = json.loads(existing.read_text(encoding="utf-8"))
            same_source = value["source_files"]["primary"]["sha256"] == primary_hash
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            same_source = False
    if not same_source and not overwrite:
        raise HumanAuditError(
            f"output directory contains results from another source; use --overwrite: {output_dir}"
        )


def write_human_audit_reports(
    result: Mapping[str, Any], output_dir: Path, *, overwrite: bool = False
) -> tuple[Path, ...]:
    """Write the deterministic M1.6 report bundle."""

    destination = Path(output_dir)
    primary_hash = result["human_summary"]["source_files"]["primary"]["sha256"]
    _prepare_output(destination, primary_hash, overwrite=overwrite)
    destination.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for key, filename in _JSON_OUTPUTS.items():
        path = destination / filename
        path.write_text(json.dumps(result[key], indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
    disagreement_path = destination / "b2_b3_human_disagreement.csv"
    rows = result["b2_b3_human_disagreement"]
    with disagreement_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    written.append(disagreement_path)
    markdown_path = destination / "human_audit_summary.md"
    markdown_path.write_text(_markdown_summary(result), encoding="utf-8")
    written.append(markdown_path)
    return tuple(written)


def analyze_review(
    path: Path,
    *,
    project_root: Path,
    output_dir: Path,
    annotators: Mapping[str, Path] | None = None,
    adjudicated: Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Analyze complete external annotations and write the M1.6 report bundle."""

    primary_path = Path(path)
    primary_rows = load_review(primary_path)
    label_path = Path(adjudicated) if adjudicated else primary_path
    status = review_status(label_path)
    if not status["analysis_ready"]:
        raise IncompleteAnnotationsError(
            "human annotation is incomplete or contains unknown taxonomy labels: "
            f"labelled={status['labelled']}/{status['rows']}, "
            f"unknown={status['unknown_taxonomy_labels']}"
        )
    if adjudicated:
        adjudicated_rows = load_review(label_path)
        adjudicated_by_identity = {
            (row["run_id"], row["record_id"], row["canonical_hash"]): row
            for row in adjudicated_rows
        }
        primary_identities = {
            (row["run_id"], row["record_id"], row["canonical_hash"]) for row in primary_rows
        }
        if set(adjudicated_by_identity) != primary_identities:
            raise HumanAuditError("adjudicated row identities do not match the primary review file")
        rows = []
        for primary in primary_rows:
            identity = (primary["run_id"], primary["record_id"], primary["canonical_hash"])
            labels = adjudicated_by_identity[identity]
            rows.append({**primary, **{column: labels[column] for column in HUMAN_COLUMNS}})
    else:
        rows = primary_rows

    b2_classes, evidence_sources = _b2_evidence_view(rows, Path(project_root))
    prepared: list[dict[str, Any]] = []
    for row in rows:
        human_valid = _explicit_bool(row["human_valid"], field="human_valid")
        assert human_valid is not None
        b2_accepted = _decision_accept(row["b2_status"], field="b2_status")
        b3_accepted = _decision_accept(row["b3_status"], field="b3_status")
        b2_class = "accepted" if b2_accepted else b2_classes[(row["run_id"], row["record_id"])]
        prepared.append(
            {
                **row,
                "human_valid": human_valid,
                "human_failure_labels": parse_failure_labels(row["human_failure_type"]),
                "b2_accepted": b2_accepted,
                "b3_accepted": b3_accepted,
                "b2_reject_class": b2_class,
                "b3_score": _numeric(row["b3_score"]),
                "exact_synthetic_duplicate": _explicit_bool(
                    row["exact_synthetic_duplicate"], field="exact_synthetic_duplicate"
                ),
                "exact_reference_match": _explicit_bool(
                    row["exact_reference_match"], field="exact_reference_match"
                ),
                "exact_nonreference_train_match": _explicit_bool(
                    row["exact_nonreference_train_match"], field="exact_nonreference_train_match"
                ),
            }
        )

    annotation_sets: dict[str, Sequence[Mapping[str, str]]] = {"primary": primary_rows}
    source_annotators: dict[str, dict[str, str]] = {}
    for name, annotation_path in sorted((annotators or {}).items()):
        loaded = load_review(annotation_path)
        annotation_sets[name] = loaded
        source_annotators[name] = _source_file(annotation_path)
    trace: dict[str, Any] = {
        "primary": _source_file(primary_path),
        "b2_evidence": evidence_sources,
        "annotators": source_annotators,
    }
    if adjudicated:
        trace["adjudicated"] = _source_file(label_path)
    agreement = annotator_agreement(annotation_sets) if len(annotation_sets) > 1 else {"pairs": []}
    human_valid_values = [bool(row["human_valid"]) for row in prepared]
    b2_record_accept = [
        bool(row["b2_accepted"]) or row["b2_reject_class"] == "redundancy_only" for row in prepared
    ]
    b2_counts = Counter(row["b2_reject_class"] for row in prepared if not row["b2_accepted"])
    summary_payload = {
        "status": "complete",
        "human_valid_definition": (
            "conforms to known schema/domain semantics and is a plausible member "
            "of the requested target class"
        ),
        "redundancy_distinct_from_record_validity": True,
        "rows": len(prepared),
        "labelled": len(prepared),
        "unlabelled": 0,
        "human_valid": sum(human_valid_values),
        "human_invalid": sum(not value for value in human_valid_values),
        "human_invalid_rate": sum(not value for value in human_valid_values) / len(prepared),
        "annotator_agreement": agreement,
        "label_source": "adjudicated" if adjudicated else "primary",
    }
    result: dict[str, Any] = {
        "human_summary": _trace_payload(summary_payload, trace),
        "b2_human_confusion": _trace_payload(
            {
                "record_validity_view": confusion_metrics(human_valid_values, b2_record_accept),
                "b2_reject_classes": dict(sorted(b2_counts.items())),
                "duplicate_only_counts_as_invalid_detection": False,
            },
            trace,
        ),
        "b3_human_confusion": _trace_payload(
            confusion_metrics(human_valid_values, [bool(row["b3_accepted"]) for row in prepared]),
            trace,
        ),
        "b3_score_distribution": _trace_payload(score_distribution(prepared), trace),
        "copying_vs_human": _trace_payload(_copying_analysis(prepared), trace),
        "support_distance_vs_human": _trace_payload(support_distance_analysis(prepared), trace),
        "failure_taxonomy": _trace_payload(_failure_taxonomy(prepared), trace),
        "dataset_class_human_rates": _trace_payload(_dataset_class_rates(prepared), trace),
        "b2_b3_human_disagreement": _disagreement_rows(
            prepared, trace["primary"]["sha256"], evidence_sources
        ),
    }
    write_human_audit_reports(result, Path(output_dir), overwrite=overwrite)
    return result


BLINDED_RECORD_TAXONOMY = frozenset(
    {
        "NONE",
        "SCHEMA",
        "MISSING_FIELD",
        "INVALID_CATEGORY",
        "TARGET_MISMATCH",
        "NUMERIC_OUTLIER",
        "LOGICAL_INCONSISTENCY",
        "STATISTICAL_IMPLAUSIBILITY",
        "SEMANTIC_IMPLAUSIBILITY",
        "OTHER",
    }
)
BLINDED_REVIEW_COLUMNS = (
    "annotation_id",
    "record_id",
    "dataset_id",
    "requested_class",
    "candidate_json",
    *HUMAN_COLUMNS,
)


def _canonical_record_hash(candidate_json: str) -> str:
    try:
        record = json.loads(candidate_json)
    except json.JSONDecodeError as error:
        raise HumanAuditError(f"generated record is not valid JSON: {error}") from error
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _annotation_id(record_id: str, canonical_record_sha256: str) -> str:
    digest = hashlib.sha256(
        f"m1.6-blind-v1:{record_id}:{canonical_record_sha256}".encode()
    ).hexdigest()
    return f"ann-{digest[:20]}"


def _blind_row(row: Mapping[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    candidate_json = row.get("candidate_json", "")
    if not candidate_json.strip():
        raise HumanAuditError(f"missing generated record for {row.get('record_id', '<unknown>')}")
    record_hash = _canonical_record_hash(candidate_json)
    annotation_id = _annotation_id(row["record_id"], record_hash)
    blind = {
        "annotation_id": annotation_id,
        "record_id": row["record_id"],
        "dataset_id": row["dataset_id"],
        "requested_class": row["requested_class"],
        "candidate_json": candidate_json,
        **{column: "" for column in HUMAN_COLUMNS},
    }
    metadata = {
        "annotation_id": annotation_id,
        "record_id": row["record_id"],
        "dataset_id": row["dataset_id"],
        "requested_class": row["requested_class"],
        "canonical_record_sha256": record_hash,
    }
    return blind, metadata


def _stratified_overlap(
    rows: Sequence[Mapping[str, str]], *, overlap: int, seed: int
) -> list[Mapping[str, str]]:
    if overlap < 0 or overlap > len(rows):
        raise HumanAuditError(f"overlap must be between 0 and {len(rows)}; got {overlap}")
    if overlap == 0:
        return []
    buckets: dict[tuple[str, str], list[Mapping[str, str]]] = {}
    for row in rows:
        dataset = row.get("dataset_id", "").strip()
        role = row.get("role", "").strip().lower()
        if not dataset or role not in {"majority", "minority"}:
            raise HumanAuditError(
                "dataset_id and majority/minority role required for overlap selection: "
                f"{row.get('record_id', '<unknown>')}"
            )
        buckets.setdefault((dataset, role), []).append(row)
    if overlap < len(buckets):
        raise HumanAuditError(
            f"overlap={overlap} cannot represent all {len(buckets)} dataset/role strata"
        )
    for stratum, bucket in buckets.items():
        bucket.sort(
            key=lambda row, value=stratum: hashlib.sha256(
                f"{seed}:{value[0]}:{value[1]}:{row['record_id']}".encode()
            ).hexdigest()
        )
    selected: list[Mapping[str, str]] = []
    cursors = dict.fromkeys(buckets, 0)
    strata = sorted(buckets)
    while len(selected) < overlap:
        progressed = False
        for stratum in strata:
            if len(selected) == overlap:
                break
            cursor = cursors[stratum]
            bucket = buckets[stratum]
            if cursor < len(bucket):
                selected.append(bucket[cursor])
                cursors[stratum] += 1
                progressed = True
        if not progressed:
            raise HumanAuditError("insufficient rows to satisfy requested overlap")
    return selected


def _write_blind_csv(path: Path, rows: Sequence[Mapping[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        fieldnames: list[str] = list(BLINDED_REVIEW_COLUMNS)
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


def _blind_manifest(
    *, reviewer_id: str, master_path: Path, records: Sequence[Mapping[str, str]], seed: int
) -> dict[str, Any]:
    return {
        "schema_version": "m1-6-blinded-review-manifest-v1",
        "reviewer_id": reviewer_id,
        "master_sha256": _sha256(master_path),
        "selection_seed": seed,
        "record_count": len(records),
        "records": list(records),
    }


def export_blinded_reviews(
    master_path: Path,
    output_dir: Path,
    *,
    overlap: int = 40,
    seed: int = 42,
    overwrite: bool = False,
) -> dict[str, Path]:
    """Create deterministic reviewer A/all and reviewer B/overlap blinded exports."""

    master = Path(master_path)
    master_rows = load_review(master)
    reviewer_b_source = _stratified_overlap(master_rows, overlap=overlap, seed=seed)
    reviewer_a_pairs = [_blind_row(row) for row in master_rows]
    reviewer_b_pairs = [_blind_row(row) for row in reviewer_b_source]
    if len({blind["annotation_id"] for blind, _ in reviewer_a_pairs}) != len(reviewer_a_pairs):
        raise HumanAuditError("deterministic annotation ID collision")

    destination = Path(output_dir)
    outputs = {
        "reviewer_a": destination / "reviewer_a_blind.csv",
        "reviewer_a_manifest": destination / "reviewer_a_blind.manifest.json",
        "reviewer_b": destination / "reviewer_b_blind.csv",
        "reviewer_b_manifest": destination / "reviewer_b_blind.manifest.json",
    }
    existing = [path for path in outputs.values() if path.exists()]
    if existing and not overwrite:
        raise HumanAuditError(f"refusing to overwrite blinded export: {existing[0]}")
    destination.mkdir(parents=True, exist_ok=True)
    _write_blind_csv(outputs["reviewer_a"], [blind for blind, _ in reviewer_a_pairs])
    _write_blind_csv(outputs["reviewer_b"], [blind for blind, _ in reviewer_b_pairs])
    manifests = {
        "reviewer_a_manifest": _blind_manifest(
            reviewer_id="reviewer_a",
            master_path=master,
            records=[metadata for _, metadata in reviewer_a_pairs],
            seed=seed,
        ),
        "reviewer_b_manifest": _blind_manifest(
            reviewer_id="reviewer_b",
            master_path=master,
            records=[metadata for _, metadata in reviewer_b_pairs],
            seed=seed,
        ),
    }
    for key, manifest in manifests.items():
        outputs[key].write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return outputs


def _read_blinded_review(path: Path) -> list[dict[str, str]]:
    try:
        with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != BLINDED_REVIEW_COLUMNS:
                raise HumanAuditError(
                    "blinded review columns were added, removed, or reordered; "
                    f"expected {BLINDED_REVIEW_COLUMNS}"
                )
            return [{key: str(value or "") for key, value in row.items()} for row in reader]
    except OSError as error:
        raise HumanAuditError(f"cannot read blinded review {path}: {error}") from error


def _read_blind_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HumanAuditError(f"cannot read blinded manifest {path}: {error}") from error
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != "m1-6-blinded-review-manifest-v1"
    ):
        raise HumanAuditError("unsupported blinded review manifest")
    return value


def _validate_blind_labels(row: Mapping[str, str]) -> None:
    values = [row[column].strip() for column in HUMAN_COLUMNS]
    if not any(values):
        return
    if not row["human_valid"].strip() or not row["human_failure_type"].strip():
        raise HumanAuditError(
            "human_valid and human_failure_type are required once annotation starts: "
            f"{row.get('annotation_id', '<unknown>')}"
        )
    _explicit_bool(row["human_valid"], field="human_valid")
    labels = parse_failure_labels(row["human_failure_type"])
    if not labels or any(label not in BLINDED_RECORD_TAXONOMY for label in labels):
        raise HumanAuditError(
            "blinded human_failure_type must use the record-level taxonomy; "
            f"got {row['human_failure_type']!r}"
        )


def import_blinded_review(
    master_path: Path,
    reviewer_path: Path,
    manifest_path: Path,
    output_path: Path,
    *,
    annotator_id: str,
    overwrite: bool = False,
) -> Path:
    """Attach explicit blinded labels to a new master-format CSV without inference."""

    master = Path(master_path)
    output = Path(output_path)
    if not annotator_id.strip():
        raise HumanAuditError("annotator_id must not be blank")
    if output.resolve() == master.resolve():
        raise HumanAuditError("refusing to overwrite the master review CSV")
    if output.exists() and not overwrite:
        raise HumanAuditError(f"refusing to overwrite imported review: {output}")
    manifest = _read_blind_manifest(manifest_path)
    if manifest.get("reviewer_id") != annotator_id:
        raise HumanAuditError(
            f"manifest reviewer_id={manifest.get('reviewer_id')!r} does not match {annotator_id!r}"
        )
    if manifest.get("master_sha256") != _sha256(master):
        raise HumanAuditError("master review CSV differs from the manifest source")

    master_rows = load_review(master)
    master_by_id = {row["record_id"]: row for row in master_rows}
    reviewer_rows = _read_blinded_review(reviewer_path)
    annotation_ids = [row["annotation_id"].strip() for row in reviewer_rows]
    record_ids = [row["record_id"].strip() for row in reviewer_rows]
    if any(not value for value in annotation_ids) or len(set(annotation_ids)) != len(
        annotation_ids
    ):
        raise HumanAuditError("blank or duplicate annotation IDs in blinded review")
    if any(not value for value in record_ids) or len(set(record_ids)) != len(record_ids):
        raise HumanAuditError("missing or duplicate record IDs in blinded review")

    manifest_records = manifest.get("records")
    if not isinstance(manifest_records, list):
        raise HumanAuditError("manifest records must be a list")
    expected = {str(item.get("annotation_id", "")): item for item in manifest_records}
    if len(expected) != len(manifest_records):
        raise HumanAuditError("duplicate annotation IDs in manifest")
    if set(annotation_ids) != set(expected):
        missing = sorted(set(expected) - set(annotation_ids))
        extra = sorted(set(annotation_ids) - set(expected))
        raise HumanAuditError(
            f"blinded review has missing records={missing} or extra records={extra}"
        )

    labels_by_record: dict[str, dict[str, str]] = {}
    for row in reviewer_rows:
        metadata = expected[row["annotation_id"]]
        record_id = row["record_id"]
        if record_id != metadata.get("record_id") or record_id not in master_by_id:
            raise HumanAuditError(f"annotation/record identity mismatch: {row['annotation_id']}")
        master_row = master_by_id[record_id]
        expected_hash = str(metadata.get("canonical_record_sha256", ""))
        if _canonical_record_hash(master_row.get("candidate_json", "")) != expected_hash:
            raise HumanAuditError(f"master generated record changed for {record_id}")
        if _canonical_record_hash(row["candidate_json"]) != expected_hash:
            raise HumanAuditError(f"generated record was modified for {record_id}")
        for field in ("dataset_id", "requested_class"):
            if row[field] != metadata.get(field) or row[field] != master_row[field]:
                raise HumanAuditError(f"{field} was modified for {record_id}")
        _validate_blind_labels(row)
        labels_by_record[record_id] = {column: row[column] for column in HUMAN_COLUMNS}

    try:
        with master.open("r", encoding="utf-8-sig", newline="") as stream:
            fieldnames = tuple(csv.DictReader(stream).fieldnames or ())
    except OSError as error:
        raise HumanAuditError(f"cannot read master header: {error}") from error
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in master_rows:
            labels = labels_by_record.get(row["record_id"])
            writer.writerow({**row, **(labels or {})})
    return output


__all__ = [
    "BLINDED_RECORD_TAXONOMY",
    "BLINDED_REVIEW_COLUMNS",
    "HUMAN_FAILURE_TAXONOMY",
    "HumanAuditError",
    "IncompleteAnnotationsError",
    "analyze_review",
    "annotator_agreement",
    "classify_b2_evidence",
    "confusion_metrics",
    "export_blinded_reviews",
    "import_blinded_review",
    "load_review",
    "parse_failure_labels",
    "review_status",
    "score_distribution",
    "support_distance_analysis",
    "write_human_audit_reports",
]
