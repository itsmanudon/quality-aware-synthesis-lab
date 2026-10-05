from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rcqasyn.cli.app import app
from rcqasyn.experiments.human_audit import (
    IncompleteAnnotationsError,
    analyze_review,
    annotator_agreement,
    classify_b2_evidence,
    confusion_metrics,
    parse_failure_labels,
    review_status,
    score_distribution,
    support_distance_analysis,
)

REVIEW_COLUMNS = (
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
    "human_valid",
    "human_failure_type",
    "human_severity",
    "human_affected_fields",
    "human_notes",
)


def _row(index: int, **updates: str) -> dict[str, str]:
    row = {
        "run_id": "run-a",
        "dataset_id": "dataset-a",
        "record_id": f"record-{index}",
        "requested_class": "positive" if index % 2 else "negative",
        "role": "minority" if index % 2 else "majority",
        "canonical_hash": f"hash-{index}",
        "provider_call_id": f"call-{index}",
        "provider_seed": str(100 + index),
        "b2_status": "accepted",
        "b2_reason": "all configured deterministic checks passed",
        "b3_status": "accepted",
        "b3_score": "0.9",
        "exact_synthetic_duplicate": "false",
        "exact_reference_match": "false",
        "exact_nonreference_train_match": "false",
        "nearest_train_distance": "0.2",
        "nearest_same_class_train_distance": "0.3",
        "human_valid": "",
        "human_failure_type": "",
        "human_severity": "",
        "human_affected_fields": "",
        "human_notes": "",
    }
    row.update(updates)
    return row


def _write_review(path: Path, rows: list[dict[str, str]]) -> Path:
    for row in rows:
        source = path.parent / "artifacts" / "runs" / row["run_id"]
        source.mkdir(parents=True, exist_ok=True)
        manifest = source / "manifest.json"
        if not manifest.exists():
            manifest.write_text(json.dumps({"schema_version": "m1-run-v1", "status": "completed",
                                            "run_id": row["run_id"], "dataset_id": row["dataset_id"]}))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_parse_failure_labels_is_multilabel_and_preserves_unknown() -> None:
    assert parse_failure_labels("DUPLICATE; STATISTICAL_IMPLAUSIBILITY") == (
        "DUPLICATE",
        "STATISTICAL_IMPLAUSIBILITY",
    )
    assert parse_failure_labels("SCHEMA|ALIEN_LABEL,SCHEMA") == ("SCHEMA", "ALIEN_LABEL")
    assert parse_failure_labels("") == ()


def test_review_status_never_infers_blank_labels(tmp_path: Path) -> None:
    path = _write_review(tmp_path / "review.csv", [_row(1), _row(2), _row(3)])

    result = review_status(path)

    assert result["rows"] == 3
    assert result["labelled"] == 0
    assert result["unlabelled"] == 3
    assert result["valid"] == result["invalid"] == 0
    assert result["analysis_ready"] is False
    assert result["dataset_counts"] == {"dataset-a": 3}
    assert result["class_counts"] == {"negative": 1, "positive": 2}
    assert result["role_counts"] == {"majority": 1, "minority": 2}


def test_review_status_does_not_mark_an_empty_file_ready(tmp_path: Path) -> None:
    path = _write_review(tmp_path / "review.csv", [])

    result = review_status(path)

    assert result["rows"] == 0
    assert result["analysis_ready"] is False


def test_review_status_reports_unknown_taxonomy_without_dropping_it(tmp_path: Path) -> None:
    path = _write_review(
        tmp_path / "review.csv",
        [
            _row(1, human_valid="true", human_failure_type="DUPLICATE;ALIEN_LABEL"),
            _row(2, human_valid="false", human_failure_type="SCHEMA"),
        ],
    )

    result = review_status(path)

    assert result["labelled"] == 2
    assert result["valid"] == result["invalid"] == 1
    assert result["taxonomy_counts"] == {"ALIEN_LABEL": 1, "DUPLICATE": 1, "SCHEMA": 1}
    assert result["unknown_taxonomy_labels"] == {"ALIEN_LABEL": 1}
    assert result["analysis_ready"] is False


def test_review_status_rejects_duplicate_canonical_hashes(tmp_path: Path) -> None:
    path = _write_review(
        tmp_path / "review.csv",
        [_row(1), _row(2, canonical_hash="hash-1")],
    )

    with pytest.raises(ValueError, match="canonical hash"):
        review_status(path)


def test_confusion_metrics_detects_human_invalid() -> None:
    result = confusion_metrics(
        human_valid=[False, False, True, True],
        predicted_accept=[False, True, False, True],
    )

    assert {key: result[key] for key in ("tp", "fp", "tn", "fn")} == {
        "tp": 1,
        "fp": 1,
        "tn": 1,
        "fn": 1,
    }
    assert result["precision"] == result["recall"] == result["f1"] == 0.5
    assert result["specificity"] == result["balanced_accuracy"] == 0.5
    assert result["false_accept_rate"] == result["false_reject_rate"] == 0.5


def test_score_distribution_splits_scores_and_uses_invalidity_direction() -> None:
    rows = [
        {"human_valid": False, "b3_score": 0.1, "dataset_id": "a", "requested_class": "minority"},
        {"human_valid": False, "b3_score": 0.4, "dataset_id": "a", "requested_class": "minority"},
        {"human_valid": True, "b3_score": 0.7, "dataset_id": "b", "requested_class": "majority"},
        {"human_valid": True, "b3_score": 1.0, "dataset_id": "b", "requested_class": "majority"},
    ]

    result = score_distribution(rows)

    assert result["overall"]["min"] == 0.1
    assert result["overall"]["median"] == pytest.approx(0.55)
    assert result["overall"]["mean"] == pytest.approx(0.55)
    assert result["by_human_valid"]["invalid"]["median"] == pytest.approx(0.25)
    assert result["by_human_valid"]["valid"]["median"] == pytest.approx(0.85)
    assert sum(result["overall"]["histogram"]["counts"]) == 4
    assert result["invalid_detection"] == {
        "score_transform": "1 - b3_score",
        "roc_auc": 1.0,
        "pr_auc": 1.0,
    }
    assert "brier_score" not in result


def test_support_distance_analysis_reports_distributions_effect_and_auc() -> None:
    rows = [
        {"human_valid": True, "nearest_train_distance": 0.1},
        {"human_valid": True, "nearest_train_distance": 0.2},
        {"human_valid": False, "nearest_train_distance": 0.7},
        {"human_valid": False, "nearest_train_distance": 0.9},
    ]

    result = support_distance_analysis(rows)
    distance = result["nearest_train_distance"]

    assert distance["human_valid"]["median"] == pytest.approx(0.15)
    assert distance["human_valid"]["iqr"] == pytest.approx(0.05)
    assert distance["human_invalid"]["median"] == pytest.approx(0.8)
    assert distance["rank_biserial"] == 1.0
    assert distance["roc_auc"] == 1.0
    assert result["nearest_same_class_train_distance"]["available"] is False


def test_annotator_agreement_uses_only_shared_labelled_rows() -> None:
    annotation_sets = {
        "alice": [
            {**_row(1), "human_valid": "true"},
            {**_row(2), "human_valid": "false"},
            {**_row(3), "human_valid": "true"},
        ],
        "bob": [
            {**_row(1), "human_valid": "true"},
            {**_row(2), "human_valid": "true"},
            {**_row(4), "human_valid": "false"},
        ],
    }

    result = annotator_agreement(annotation_sets)
    pair = result["pairs"][0]

    assert pair["annotators"] == ["alice", "bob"]
    assert pair["overlap"] == 2
    assert pair["raw_agreement"] == 0.5
    assert pair["cohen_kappa"] == 0.0


def test_annotator_agreement_reports_constant_label_kappa_as_not_computable() -> None:
    shared = [{**_row(1), "human_valid": "true"}, {**_row(2), "human_valid": "true"}]

    pair = annotator_agreement({"alice": shared, "bob": shared})["pairs"][0]

    assert pair["raw_agreement"] == 1.0
    assert pair["cohen_kappa"] is None
    assert pair["kappa_status"] == "not_computable_constant_labels"


def test_duplicate_only_b2_reject_is_accept_in_record_validity_view() -> None:
    assert classify_b2_evidence([{"validator_id": "duplicate", "severity": "FAIL"}]) == (
        "redundancy_only"
    )
    assert (
        classify_b2_evidence(
            [
                {"validator_id": "duplicate", "verdict": "fail"},
                {"validator_id": "schema", "verdict": "fail"},
            ]
        )
        == "structural_domain"
    )
    assert classify_b2_evidence([]) == "ambiguous"
    assert classify_b2_evidence([{"validator_id": "novel-check", "verdict": "fail"}]) == (
        "ambiguous"
    )


def test_incomplete_analysis_writes_no_evaluation_outputs(tmp_path: Path) -> None:
    review = _write_review(tmp_path / "review.csv", [_row(1), _row(2)])
    output = tmp_path / "human-audit"

    with pytest.raises(IncompleteAnnotationsError, match="incomplete"):
        analyze_review(review, project_root=tmp_path, output_dir=output)

    assert not output.exists()


def _write_evidence(project_root: Path) -> None:
    destination = project_root / "artifacts" / "runs" / "run-a" / "baselines" / "b2"
    destination.mkdir(parents=True)
    evidence = [
        {"candidate_id": "record-3", "validator_id": "duplicate", "verdict": "fail"},
        {"candidate_id": "record-4", "validator_id": "schema", "verdict": "fail"},
    ]
    (destination / "evidence.jsonl").write_text(
        "".join(json.dumps(item) + "\n" for item in evidence), encoding="utf-8"
    )


def test_complete_analysis_writes_traceable_measurement_only_bundle(tmp_path: Path) -> None:
    review = _write_review(
        tmp_path / "review.csv",
        [
            _row(
                1,
                human_valid="false",
                human_failure_type="SCHEMA",
                b2_status="accepted",
                b3_status="accepted",
                b3_score="0.8",
                nearest_train_distance="0.8",
            ),
            _row(
                2,
                human_valid="false",
                human_failure_type="TARGET_MISMATCH;STATISTICAL_IMPLAUSIBILITY",
                b2_status="accepted",
                b3_status="rejected",
                b3_score="0.2",
                nearest_train_distance="0.7",
            ),
            _row(
                3,
                human_valid="true",
                human_failure_type="DUPLICATE",
                b2_status="rejected",
                b3_status="accepted",
                b3_score="0.9",
                exact_reference_match="true",
                nearest_train_distance="0.1",
            ),
            _row(
                4,
                human_valid="true",
                human_failure_type="",
                b2_status="rejected",
                b3_status="rejected",
                b3_score="0.1",
                nearest_train_distance="0.2",
            ),
        ],
    )
    _write_evidence(tmp_path)
    output = tmp_path / "human-audit"

    result = analyze_review(review, project_root=tmp_path, output_dir=output)

    expected = {
        "FINALIZED.json",
        "human_summary.json",
        "b2_human_confusion.json",
        "b3_human_confusion.json",
        "b3_score_distribution.json",
        "b2_b3_human_disagreement.csv",
        "copying_vs_human.json",
        "support_distance_vs_human.json",
        "failure_taxonomy.json",
        "dataset_class_human_rates.json",
        "human_audit_summary.md",
    }
    assert {path.name for path in output.iterdir()} == expected
    assert result["human_summary"]["human_invalid"] == 2
    assert result["b2_human_confusion"]["record_validity_view"]["tp"] == 0
    assert result["b2_human_confusion"]["record_validity_view"]["fp"] == 1
    assert result["b2_human_confusion"]["b2_reject_classes"] == {
        "redundancy_only": 1,
        "structural_domain": 1,
    }
    assert result["failure_taxonomy"]["dataset_level"]["DUPLICATE"] == 1
    assert result["copying_vs_human"]["reference_copy_analysis"] == {
        "records": 1,
        "human_valid": 1,
        "human_invalid": 0,
        "duplicate_label": 1,
        "additional_defect_records": 0,
    }

    summary = json.loads((output / "human_summary.json").read_text(encoding="utf-8"))
    assert len(summary["source_files"]["primary"]["sha256"]) == 64
    assert summary["source_files"]["b2_evidence"]
    serialized = json.dumps(result, sort_keys=True)
    assert "brier_score" not in serialized
    assert "threshold_recommendation" not in serialized

    markdown = (output / "human_audit_summary.md").read_text(encoding="utf-8")
    assert "B2 evidence SHA-256" in markdown
    assert summary["source_files"]["b2_evidence"][0]["sha256"] in markdown

    with (output / "b2_b3_human_disagreement.csv").open(encoding="utf-8", newline="") as stream:
        disagreement_rows = list(csv.DictReader(stream))
    assert len(disagreement_rows) == 4
    assert {row["decision_cell"] for row in disagreement_rows} == {
        "B2 ACCEPT / B3 ACCEPT",
        "B2 ACCEPT / B3 REJECT",
        "B2 REJECT / B3 ACCEPT",
        "B2 REJECT / B3 REJECT",
    }
    assert all(row["source_primary_sha256"] for row in disagreement_rows)


def test_adjudicated_file_supplies_only_explicit_human_fields(tmp_path: Path) -> None:
    primary = _write_review(
        tmp_path / "primary.csv",
        [_row(1, b2_status="accepted", b3_status="accepted", b3_score="0.9")],
    )
    adjudicated = _write_review(
        tmp_path / "adjudicated.csv",
        [
            _row(
                1,
                human_valid="false",
                human_failure_type="SCHEMA",
                b2_status="rejected",
                b3_status="rejected",
                b3_score="0.1",
            )
        ],
    )

    result = analyze_review(
        primary,
        project_root=tmp_path,
        output_dir=tmp_path / "audit",
        adjudicated=adjudicated,
    )

    assert result["human_summary"]["label_source"] == "adjudicated"
    assert result["b2_human_confusion"]["record_validity_view"]["fn"] == 1
    assert result["b3_human_confusion"]["fn"] == 1
    assert result["human_summary"]["source_files"]["adjudicated"]["sha256"]


def test_human_review_status_cli_reports_blank_annotation_counts(tmp_path: Path) -> None:
    review = _write_review(tmp_path / "review.csv", [_row(1), _row(2), _row(3)])

    result = CliRunner().invoke(app, ["human-review", "status", str(review)])

    assert result.exit_code == 0
    assert "rows: 3" in result.stdout
    assert "labelled: 0" in result.stdout
    assert "unlabelled: 3" in result.stdout
    assert "valid: 0" in result.stdout
    assert "invalid: 0" in result.stdout
    assert "datasets: dataset-a=3" in result.stdout
    assert "classes: negative=1, positive=2" in result.stdout
    assert "human_fields_blank: true" in result.stdout
    assert "exact_reference_match: false=3" in result.stdout
    assert "nearest_train_distance: 3/3" in result.stdout
    assert "provider_call_id: 3/3" in result.stdout
    assert "analysis_ready: false" in result.stdout


def test_human_review_analyze_cli_refuses_incomplete_annotations(tmp_path: Path) -> None:
    review = _write_review(tmp_path / "review.csv", [_row(1)])
    output = tmp_path / "audit"

    result = CliRunner().invoke(
        app,
        [
            "human-review",
            "analyze",
            str(review),
            "--root",
            str(tmp_path),
            "--output-dir",
            str(output),
        ],
    )

    assert result.exit_code == 1
    assert "incomplete" in result.stdout.lower()
    assert not output.exists()


def test_human_review_analyze_cli_rejects_malformed_annotator_option(tmp_path: Path) -> None:
    review = _write_review(tmp_path / "review.csv", [_row(1)])

    result = CliRunner().invoke(
        app,
        ["human-review", "analyze", str(review), "--annotator", "missing-equals"],
    )

    assert result.exit_code == 1
    assert "ID=PATH" in result.stdout
