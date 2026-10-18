from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from rcqasyn.phase2.annotations import annotation_protocol
from rcqasyn.phase2.cohort import BLIND, MASTER, build_cohort
from rcqasyn.phase2.common import csv_text, envelope, jsonl
from rcqasyn.phase2.provenance import extract_crosswalk

ROOT = Path(os.environ.get("P2_SOURCE_ROOT", str(Path(__file__).resolve().parents[2])))
PAGE = ROOT / "artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829"


@pytest.fixture(scope="session")
def actual_crosswalks():
    return [extract_crosswalk(ROOT, ROOT / "artifacts/runs" / name) for name in (
        "m1-p1-real-page-blocks0-gemma4-e4b-20260829",
        "m1-p1-real-Ecoli4-gemma4-e4b-20260829",
        "m1-p1-real-Abalone19-gemma4-e4b-20260829")]


@pytest.fixture
def fixture_workflow(tmp_path):
    """Two synthetic-population records, never an approved research label ledger."""
    root = tmp_path / "source"
    run = root / "artifacts/runs/fixture-run"
    shutil.copytree(ROOT / "configs/datasets", root / "configs/datasets")
    run.mkdir(parents=True)
    indices = (0, 40)

    def write(relative, value):
        path = run / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def lines(relative, values):
        path = run / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(v) + "\n" for v in values), encoding="utf-8")

    write("manifest.json", {"schema_version": "m1-run-v1", "status": "completed",
                            "run_id": "fixture-run", "dataset_id": "page-blocks0"})
    raw = jsonl(PAGE / "candidates_raw.jsonl")
    selected = [raw[i] for i in indices]
    lines("candidates_raw.jsonl", selected)
    traces = jsonl(PAGE / "provider_calls.jsonl")
    lines("provider_calls.jsonl", [traces[1], traces[9]])
    copying = json.loads((PAGE / "copying_diagnostics.json").read_text())["records"]
    write("copying_diagnostics.json", {"records": [copying[i] for i in indices]})
    support = jsonl(PAGE / "support_diagnostics.jsonl")
    lines("support_diagnostics.jsonl", [support[i] for i in indices])
    evidence = jsonl(PAGE / "baselines/b2/evidence.jsonl")
    for b in ("b1", "b2", "b3"):
        decisions = jsonl(PAGE / f"baselines/{b}/decisions.jsonl")
        chosen = [decisions[i] for i in indices]
        lines(f"baselines/{b}/decisions.jsonl", chosen)
        lines(f"baselines/{b}/candidates.jsonl",
              [r for r, d in zip(selected, chosen, strict=True) if d["accepted"]])
        if b == "b2":
            wanted = {e for d in chosen for e in d["evidence_ids"]}
            lines("baselines/b2/evidence.jsonl",
                  [e for e in evidence if e["evidence_id"] in wanted])
    for artifact in ("judge_results.jsonl", "provider_calls.jsonl"):
        values = jsonl(PAGE / "baselines/b3" / artifact)
        lines("baselines/b3/" + artifact, [values[i] for i in indices])
    old = [{"run_id": "fixture-run", "record_id": r["record_id"],
            "dataset_id": "page-blocks0", "candidate_json": json.dumps(r["data"]),
            "raw_output": r["raw_output"], "requested_class": "positive", "role": "majority",
            "canonical_hash": copying[i]["canonical_hash"]}
           for r, i in zip(selected, indices, strict=True)]
    (root / MASTER).parent.mkdir(parents=True)
    (root / MASTER).write_text(csv_text(old), encoding="utf-8", newline="")
    (root / "artifacts/reports/p1/p1_human_review_manifest.json").write_text(json.dumps({
        "row_count": 2, "population_kind": "synthetic_fixture"}), encoding="utf-8")
    packet = [{**r, "annotation_id": f"fixture-{i}"} for i, r in enumerate(old)]
    (root / BLIND).mkdir(parents=True)
    (root / BLIND / "reviewer_a_blind.csv").write_text(csv_text(packet), encoding="utf-8")
    (root / BLIND / "reviewer_b_blind.csv").write_text(csv_text(packet[:1]), encoding="utf-8")
    cw = extract_crosswalk(root, run)
    cohort = build_cohort(root, [cw])
    spec = envelope("dataset-specification-v1", {
        "specification": {"dataset_id": "page-blocks0", "features": [{"name": "height"}],
                          "target_semantics": {"target_column": "class",
                                               "literal_labels": ["positive", "negative"]},
                          "ambiguity": ["fixture only"],
                          "rules": [{"rule_id": "page-blocks0:schema", "authority": "AUTHORITATIVE",
                                     "statement": "Fixture source declarations", "evidence": ["fixture"],
                                     "hard_rejection_allowed": True}]},
        "source_files": {}})
    protocol = annotation_protocol(envelope("dataset-specifications-v1", {
        "specifications": [spec]}))
    approval = {"cohort_fingerprint": cohort["fingerprint"],
                "crosswalk_fingerprints": [cw["fingerprint"]],
                "protocol_fingerprint": protocol["fingerprint"],
                "supervisor_reference": "SYNTHETIC_TEST_SUPERVISOR",
                "supervisor_approval_provenance": "SYNTHETIC_TEST_ONLY",
                "independent_verifier_reference": "SYNTHETIC_TEST_VERIFIER",
                "independent_verification_provenance": "SYNTHETIC_TEST_ONLY",
                "implementation_owner_reference": "SYNTHETIC_TEST_OWNER",
                "decision": "APPROVED", "personnel_independent": True}
    return root, [cw], cohort, protocol, approval


@pytest.fixture
def supervisor_signer(tmp_path_factory):
    """Disposable test credential; never provisions an actual supervisor key."""
    from hashlib import sha256
    from types import SimpleNamespace

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from rcqasyn.phase2.approval import build_approval_ledger, signing_bytes

    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes_raw()
    key_id = sha256(public).hexdigest()
    directory = tmp_path_factory.mktemp("synthetic-supervisor-trust")
    trust = directory / "trust.json"
    trust.write_text(json.dumps({
        "schema_version": "supervisor-trust-v1",
        "reviewer_reference": "SYNTHETIC_TEST_SUPERVISOR",
        "key_id": key_id, "public_key_hex": public.hex()}), encoding="utf-8")

    def sign(ledger):
        return {"schema_version": "supervisor-attestation-v1", "ledger": ledger,
                "signature": {"schema_version": "supervisor-signature-v1", "key_id": key_id,
                              "signature_hex": key.sign(signing_bytes(ledger)).hex()}}

    def attest(workflow, proposals, history):
        root, cws, cohort, protocol, approval = workflow
        ledger = build_approval_ledger(root, cohort, cws, protocol, approval, proposals,
                                       history, "SYNTHETIC_TEST_SUPERVISOR")
        return sign(ledger)

    return SimpleNamespace(key=key, key_id=key_id, trust=trust, sign=sign, attest=attest,
                           directory=directory)
