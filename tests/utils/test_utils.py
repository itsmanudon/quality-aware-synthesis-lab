from pathlib import Path

from rcqasyn.utils import (
    assessment_id,
    content_id,
    decision_id,
    derive_seed,
    evidence_id,
    record_id,
    run_id,
    sha256_bytes,
    sha256_file,
)


def test_hashes_and_content_ids_are_deterministic(tmp_path: Path) -> None:
    payload = b"hello"
    file = tmp_path / "payload.bin"
    file.write_bytes(payload)
    assert sha256_file(file) == sha256_bytes(payload)
    assert content_id(payload) == content_id(payload)


def test_seed_derivation_is_stable_and_namespaced() -> None:
    first = derive_seed(42, "generation", "record-1")
    assert first == derive_seed(42, "generation", "record-1")
    assert first != derive_seed(42, "validation", "record-1")
    assert 0 <= first < 2**63


def test_explicit_id_helpers_have_distinct_stable_prefixes() -> None:
    helpers = (
        (run_id, "run-"),
        (record_id, "record-"),
        (evidence_id, "evidence-"),
        (assessment_id, "assessment-"),
        (decision_id, "decision-"),
    )
    values = [helper() for helper, prefix in helpers]
    assert all(value.startswith(prefix) for value, (_, prefix) in zip(values, helpers, strict=True))
    assert len(set(values)) == len(values)
    assert not values[0].startswith("content-")
