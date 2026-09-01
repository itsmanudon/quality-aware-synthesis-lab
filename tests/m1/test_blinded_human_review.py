from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rcqasyn.cli.app import app
from rcqasyn.experiments.human_audit import (
    HumanAuditError,
    annotator_agreement,
    export_blinded_reviews,
    import_blinded_review,
)

MASTER_COLUMNS = (
    "run_id",
    "dataset_id",
    "record_id",
    "requested_class",
    "role",
    "canonical_hash",
    "provider_call_id",
    "provider_seed",
    "b1_status",
    "b2_status",
    "b2_reason",
    "b3_status",
    "b3_score",
    "exact_synthetic_duplicate",
    "exact_reference_match",
    "exact_nonreference_train_match",
    "nearest_train_distance",
    "nearest_same_class_train_distance",
    "candidate_json",
    "human_valid",
    "human_failure_type",
    "human_severity",
    "human_affected_fields",
    "human_notes",
)
BLIND_COLUMNS = (
    "annotation_id",
    "record_id",
    "dataset_id",
    "requested_class",
    "candidate_json",
    "human_valid",
    "human_failure_type",
    "human_severity",
    "human_affected_fields",
    "human_notes",
)


def _master_row(index: int, dataset: str, role: str) -> dict[str, str]:
    return {
        "run_id": f"run-{dataset}",
        "dataset_id": dataset,
        "record_id": f"record-{index:03d}",
        "requested_class": "positive" if role == "minority" else "negative",
        "role": role,
        "canonical_hash": f"master-hash-{index:03d}",
        "provider_call_id": f"private-call-{index}",
        "provider_seed": str(9000 + index),
        "b1_status": "accepted",
        "b2_status": "rejected" if index % 3 == 0 else "accepted",
        "b2_reason": "private automated reason",
        "b3_status": "rejected" if index % 5 == 0 else "accepted",
        "b3_score": "0.42",
        "exact_synthetic_duplicate": "false",
        "exact_reference_match": "true" if index % 7 == 0 else "false",
        "exact_nonreference_train_match": "false",
        "nearest_train_distance": "0.123",
        "nearest_same_class_train_distance": "0.234",
        "candidate_json": json.dumps(
            {"feature_a": index, "feature_b": dataset, "class": "positive"},
            sort_keys=True,
            separators=(",", ":"),
        ),
        "human_valid": "",
        "human_failure_type": "",
        "human_severity": "",
        "human_affected_fields": "",
        "human_notes": "",
    }


def _write_master(path: Path, *, per_stratum: int = 3) -> Path:
    rows: list[dict[str, str]] = []
    index = 0
    for dataset in ("alpha", "beta", "gamma"):
        for role in ("majority", "minority"):
            for _ in range(per_stratum):
                index += 1
                rows.append(_master_row(index, dataset, role))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=MASTER_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: list[dict[str, str]], columns: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def test_blinded_export_excludes_every_automated_diagnostic_column(tmp_path: Path) -> None:
    master = _write_master(tmp_path / "master.csv")

    outputs = export_blinded_reviews(master, tmp_path / "blind", overlap=6, seed=42)
    with outputs["reviewer_a"].open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)

    assert tuple(reader.fieldnames or ()) == BLIND_COLUMNS
    assert len(rows) == 18
    serialized_header = ",".join(reader.fieldnames or ())
    for forbidden in (
        "b1_status",
        "b2_status",
        "b2_reason",
        "b3_status",
        "b3_score",
        "duplicate",
        "reference",
        "distance",
        "provider",
        "verdict",
        "canonical_hash",
    ):
        assert forbidden not in serialized_header.lower()
    assert all(
        row["candidate_json"] and not any(row[column] for column in BLIND_COLUMNS[-5:])
        for row in rows
    )


def test_reviewer_a_export_is_deterministic_and_preserves_master_bytes(tmp_path: Path) -> None:
    master = _write_master(tmp_path / "master.csv")
    before = master.read_bytes()
    before_hash = hashlib.sha256(before).hexdigest()

    first = export_blinded_reviews(master, tmp_path / "first", overlap=6, seed=17)
    second = export_blinded_reviews(master, tmp_path / "second", overlap=6, seed=17)

    assert first["reviewer_a"].read_bytes() == second["reviewer_a"].read_bytes()
    assert first["reviewer_a_manifest"].read_bytes() == second["reviewer_a_manifest"].read_bytes()
    assert master.read_bytes() == before
    manifest = json.loads(first["reviewer_a_manifest"].read_text(encoding="utf-8"))
    assert manifest["master_sha256"] == before_hash
    assert len(manifest["records"]) == 18
    assert all(len(item["canonical_record_sha256"]) == 64 for item in manifest["records"])


def test_reviewer_b_overlap_is_deterministic_and_blindly_stratified(tmp_path: Path) -> None:
    master = _write_master(tmp_path / "master.csv", per_stratum=10)

    first = export_blinded_reviews(master, tmp_path / "first", overlap=40, seed=42)
    second = export_blinded_reviews(master, tmp_path / "second", overlap=40, seed=42)
    reviewer_a = _read_csv(first["reviewer_a"])
    reviewer_b = _read_csv(first["reviewer_b"])

    assert first["reviewer_b"].read_bytes() == second["reviewer_b"].read_bytes()
    assert len(reviewer_b) == 40
    assert {row["dataset_id"] for row in reviewer_b} == {"alpha", "beta", "gamma"}
    assert {row["requested_class"] for row in reviewer_b} == {"negative", "positive"}
    assert {row["annotation_id"] for row in reviewer_b} < {
        row["annotation_id"] for row in reviewer_a
    }


def test_import_attaches_only_human_fields_and_keeps_machine_fields_identical(
    tmp_path: Path,
) -> None:
    master = _write_master(tmp_path / "master.csv")
    outputs = export_blinded_reviews(master, tmp_path / "blind", overlap=6)
    reviewer = _read_csv(outputs["reviewer_a"])
    for index, row in enumerate(reviewer):
        row["human_valid"] = "true" if index % 2 == 0 else "false"
        row["human_failure_type"] = "NONE" if index % 2 == 0 else "SCHEMA"
    _write_csv(outputs["reviewer_a"], reviewer, BLIND_COLUMNS)

    imported = import_blinded_review(
        master,
        outputs["reviewer_a"],
        outputs["reviewer_a_manifest"],
        tmp_path / "reviewer_a_imported.csv",
        annotator_id="reviewer_a",
    )

    master_rows = _read_csv(master)
    imported_rows = _read_csv(imported)
    machine_columns = [column for column in MASTER_COLUMNS if not column.startswith("human_")]
    assert [[row[column] for column in machine_columns] for row in imported_rows] == [
        [row[column] for column in machine_columns] for row in master_rows
    ]
    assert sum(bool(row["human_valid"]) for row in imported_rows) == 18
    assert all(row["human_failure_type"] in {"NONE", "SCHEMA"} for row in imported_rows)


def test_import_detects_generated_record_tampering(tmp_path: Path) -> None:
    master = _write_master(tmp_path / "master.csv")
    outputs = export_blinded_reviews(master, tmp_path / "blind", overlap=6)
    reviewer = _read_csv(outputs["reviewer_a"])
    reviewer[0]["candidate_json"] = '{"feature_a":999}'
    _write_csv(outputs["reviewer_a"], reviewer, BLIND_COLUMNS)

    with pytest.raises(HumanAuditError, match="generated record.*modified"):
        import_blinded_review(
            master,
            outputs["reviewer_a"],
            outputs["reviewer_a_manifest"],
            tmp_path / "imported.csv",
            annotator_id="reviewer_a",
        )


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "extra"])
def test_import_rejects_duplicate_missing_and_extra_identities(
    tmp_path: Path, mutation: str
) -> None:
    master = _write_master(tmp_path / "master.csv")
    outputs = export_blinded_reviews(master, tmp_path / "blind", overlap=6)
    reviewer = _read_csv(outputs["reviewer_a"])
    if mutation == "duplicate":
        reviewer[1]["annotation_id"] = reviewer[0]["annotation_id"]
    elif mutation == "missing":
        reviewer.pop()
    else:
        reviewer.append({**reviewer[0], "annotation_id": "ann-extra", "record_id": "record-extra"})
    _write_csv(outputs["reviewer_a"], reviewer, BLIND_COLUMNS)

    with pytest.raises(HumanAuditError, match="duplicate annotation|missing records|extra records"):
        import_blinded_review(
            master,
            outputs["reviewer_a"],
            outputs["reviewer_a_manifest"],
            tmp_path / "imported.csv",
            annotator_id="reviewer_a",
        )


@pytest.mark.parametrize("failure_type", ["DUPLICATE", "ALIEN_LABEL"])
def test_import_rejects_non_record_level_taxonomy(tmp_path: Path, failure_type: str) -> None:
    master = _write_master(tmp_path / "master.csv")
    outputs = export_blinded_reviews(master, tmp_path / "blind", overlap=6)
    reviewer = _read_csv(outputs["reviewer_a"])
    reviewer[0]["human_valid"] = "true"
    reviewer[0]["human_failure_type"] = failure_type
    _write_csv(outputs["reviewer_a"], reviewer, BLIND_COLUMNS)

    with pytest.raises(HumanAuditError, match="record-level taxonomy"):
        import_blinded_review(
            master,
            outputs["reviewer_a"],
            outputs["reviewer_a_manifest"],
            tmp_path / "imported.csv",
            annotator_id="reviewer_a",
        )


def test_import_allows_fully_blank_rows_but_rejects_partial_labels(tmp_path: Path) -> None:
    master = _write_master(tmp_path / "master.csv")
    outputs = export_blinded_reviews(master, tmp_path / "blind", overlap=6)

    imported = import_blinded_review(
        master,
        outputs["reviewer_a"],
        outputs["reviewer_a_manifest"],
        tmp_path / "blank_import.csv",
        annotator_id="reviewer_a",
    )
    assert all(not row["human_valid"] for row in _read_csv(imported))

    reviewer = _read_csv(outputs["reviewer_a"])
    reviewer[0]["human_notes"] = "started but not completed"
    _write_csv(outputs["reviewer_a"], reviewer, BLIND_COLUMNS)
    with pytest.raises(HumanAuditError, match="human_valid.*human_failure_type"):
        import_blinded_review(
            master,
            outputs["reviewer_a"],
            outputs["reviewer_a_manifest"],
            tmp_path / "partial_import.csv",
            annotator_id="reviewer_a",
        )


def test_imported_overlap_supports_agreement_without_resolving_disagreement(tmp_path: Path) -> None:
    master = _write_master(tmp_path / "master.csv")
    outputs = export_blinded_reviews(master, tmp_path / "blind", overlap=6)
    reviewer_a = _read_csv(outputs["reviewer_a"])
    reviewer_b = _read_csv(outputs["reviewer_b"])
    for row in reviewer_a:
        row["human_valid"] = "true"
        row["human_failure_type"] = "NONE"
    for index, row in enumerate(reviewer_b):
        row["human_valid"] = "false" if index == 0 else "true"
        row["human_failure_type"] = "SCHEMA" if index == 0 else "NONE"
    disagreement_record_id = reviewer_b[0]["record_id"]
    _write_csv(outputs["reviewer_a"], reviewer_a, BLIND_COLUMNS)
    _write_csv(outputs["reviewer_b"], reviewer_b, BLIND_COLUMNS)
    imported_a = import_blinded_review(
        master,
        outputs["reviewer_a"],
        outputs["reviewer_a_manifest"],
        tmp_path / "a.csv",
        annotator_id="reviewer_a",
    )
    imported_b = import_blinded_review(
        master,
        outputs["reviewer_b"],
        outputs["reviewer_b_manifest"],
        tmp_path / "b.csv",
        annotator_id="reviewer_b",
    )

    agreement = annotator_agreement(
        {"reviewer_a": _read_csv(imported_a), "reviewer_b": _read_csv(imported_b)}
    )["pairs"][0]

    assert agreement["overlap"] == 6
    assert agreement["raw_agreement"] == pytest.approx(5 / 6)
    assert agreement["cohen_kappa"] == 0.0
    imported_a_by_id = {row["record_id"]: row for row in _read_csv(imported_a)}
    imported_b_by_id = {row["record_id"]: row for row in _read_csv(imported_b)}
    assert imported_a_by_id[disagreement_record_id]["human_valid"] == "true"
    assert imported_b_by_id[disagreement_record_id]["human_valid"] == "false"


def test_blinded_export_and_import_cli_round_trip_blank_labels(tmp_path: Path) -> None:
    master = _write_master(tmp_path / "master.csv")
    blind_dir = tmp_path / "blind"
    runner = CliRunner()

    exported = runner.invoke(
        app,
        [
            "human-review",
            "export-blind",
            str(master),
            "--output-dir",
            str(blind_dir),
            "--overlap",
            "6",
        ],
    )

    assert exported.exit_code == 0
    assert "reviewer_a_blind.csv: 18 rows" in exported.stdout
    assert "reviewer_b_blind.csv: 6 rows" in exported.stdout

    imported_path = tmp_path / "reviewer_a_imported.csv"
    imported = runner.invoke(
        app,
        [
            "human-review",
            "import-blind",
            str(master),
            str(blind_dir / "reviewer_a_blind.csv"),
            "--manifest",
            str(blind_dir / "reviewer_a_blind.manifest.json"),
            "--annotator-id",
            "reviewer_a",
            "--output",
            str(imported_path),
        ],
    )

    assert imported.exit_code == 0
    assert imported_path.is_file()
    assert "labelled: 0" in imported.stdout
    assert "unlabelled: 18" in imported.stdout
