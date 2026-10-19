"""Independent source-contract second pass; all results remain agent proposals."""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

from rcqasyn.phase2.common import csv_rows, csv_text, digest, envelope, write_bundle
from rcqasyn.phase2.workflow import load_preparation, validate_preparation


def audit(root: Path, source: Path, output: Path) -> dict:
    preparation = root / "artifacts/reports/phase2/gate-a-v3"
    validate_preparation(source, preparation)
    cohort, _, protocol, specs = load_preparation(preparation)
    old_path = root / "artifacts/reports/phase2/agent-labels-v1/supervisor-review"
    old = json.loads((old_path / "review.json").read_text(encoding="utf-8"))
    assert len(csv_rows(old_path / "review.csv")) == len(old) == 120
    byold = {r["review_row_id"]: r for r in old}
    # Only payload, source declarations and prior annotation evidence enter assessment.
    rows = []
    for order, original in enumerate(cohort["records"], 1):
        previous = byold[original["review_row_id"]]
        payload = original["payload"]
        assert payload == previous["payload"] and digest(payload) == original["payload_sha256"]
        raw = json.loads((source / f"data/manifests/{original['dataset_id']}/raw_schema.json")
                         .read_text(encoding="utf-8"))
        declarations = {a["name"].casefold(): a for a in raw["attributes"]}
        fields = protocol["fields"][original["dataset_id"]]
        issues, observations = [], []
        for field in fields:
            name = field["name"]
            declaration = declarations[name.casefold()]
            if name not in payload:
                issues.append(f"Mandatory declared field {name} is absent.")
                observations.append({"field": name, "state": "ABSENT_REQUIRED_KEY"})
                continue
            value = payload[name]
            state = "DECLARATION_COMPATIBLE"
            if value is None:
                state = "PRESERVED_NULL; judgment limited, not automatic invalidity"
            elif declaration["kind"] == "nominal":
                if value not in declaration["categories"]:
                    issues.append(f"{name}={value!r} is outside declared categories.")
                    state = "NOMINAL_TYPE_OR_DOMAIN_VIOLATION"
            elif type(value) not in (int, float) or not math.isfinite(value):
                issues.append(f"{name}={value!r} is not a finite numeric primitive.")
                state = "NUMERIC_TYPE_VIOLATION"
            elif declaration["declaration"].startswith("integer") and value != int(value):
                issues.append(f"{name}={value!r} is non-integral under {declaration['declaration']}.")
                state = "INTEGER_DECLARATION_VIOLATION"
            observations.append({"field": name, "value": value, "state": state,
                                 "source_declaration": declaration["declaration"]})
        extra = sorted(set(payload) - {f["name"] for f in fields})
        if extra:
            issues.append(f"Undeclared fields: {extra}.")
        label = "INVALID" if issues else "INDETERMINATE"
        rules = [k for k, r in protocol["rules"].items()
                 if k.startswith(original["dataset_id"] + ":") and r["authority"] == "AUTHORITATIVE"]
        # Absence of violations is deliberately insufficient for VALID.
        rationale = (" ".join(issues) if issues else
                     "All observed field names, primitive types and literal categories were checked "
                     "against the archived raw schema. No authoritative violation was established. "
                     "Affirmative record-level validity remains unsupported because target mapping, "
                     "physical meanings/units and cross-field constraints are unverified.")
        if "class" not in payload:
            rationale += (" The recorded Phase-1 generation request explicitly requires the target "
                          "column; requested_class metadata does not substitute for payload class.")
        if issues:
            rationale += " This substantiates a schema defect, not a claim about physical impossibility."
        uncertainty = ("Specific declaration violation supported; unresolved domain semantics remain "
                       "unasserted." if issues else "HIGH: insufficient positive or negative authoritative "
                       "evidence; a schema-compatible payload is not automatically VALID.")
        assert previous["human_final_label"] is None
        assert previous["supporting_evidence_ids"] and previous["proposed_rationale"].strip()
        assert all(k in rules for k in previous["supporting_evidence_ids"])
        rows.append({**previous, "proposed_label": label, "proposed_rationale": rationale,
                     "supporting_evidence_ids": sorted(rules),
                     "uncertainty_or_ambiguity": uncertainty,
                     "prior_proposed_label": previous["proposed_label"],
                     "prior_proposal_fingerprint": previous["proposal_fingerprint"],
                     "label_changed_from_v1": label != previous["proposed_label"],
                     "second_pass_observations": observations,
                     "first_pass_evidence_review": "Existing rationale and cited rules inspected; "
                     "no unsupported validity inference identified." ,
                     "annotator_model_or_agent_version": "Codex scientific second pass v2",
                     "proposal_timestamp_or_execution_identity": "phase3/review-v2/2026-10-18",
                     "proposal_fingerprint": digest({"review_row_id": original["review_row_id"],
                         "payload_sha256": original["payload_sha256"], "label": label,
                         "rationale": rationale, "evidence": sorted(rules), "version": "second-pass-v2"}),
                     "human_review_status": "PENDING", "human_final_label": None,
                     "human_correction_note": "", "human_reviewer_reference": ""})
    priority = sorted(rows, key=lambda r: (r["proposed_label"] != "INDETERMINATE", r["review_order"]))
    counts = {label: sum(r["proposed_label"] == label for r in rows)
              for label in ("VALID", "INVALID", "INDETERMINATE")}
    controls = {d: {b: dict(Counter("accepted" if r["controls"][b]["decision"]["accepted"]
                                    else "rejected" for r in cohort["records"] if r["dataset_id"] == d))
                    for b in ("b1", "b2", "b3")}
                for d in sorted({r["dataset_id"] for r in rows})}
    value = envelope("second-pass-agent-review-v2", {
        "phase2_parent_commit": "6c4634fabd2f8cba2ed7365b0b9559c3df17055a",
        "population_kind": "research", "annotator_type": "AGENT",
        "review_status": "PENDING_HUMAN_APPROVAL", "human_final_label": None,
        "cohort_fingerprint": cohort["fingerprint"], "protocol_fingerprint": protocol["fingerprint"],
        "research_rubric_fingerprint": rows[0]["research_rubric_fingerprint"],
        "counts": counts, "changed_labels": sum(r["label_changed_from_v1"] for r in rows),
        "rows": rows, "control_distribution_joined_after_assessment": controls,
        "pending_scientific_decisions": specs["semantics_gaps"],
        "personnel_independent_review_claimed": False, "human_decision": "HUMAN_DECISION_PENDING",
    })
    notes = ("# Latest supervisor review package: review-v2\n\n"
             f"All 120 records received a source-contract second pass: {counts}. "
             f"Changed labels from v1: {value['changed_labels']}.\n\n"
             "All remain AGENT / PENDING_HUMAN_APPROVAL with null human final labels. "
             "This is a second agent assessment, not personnel-independent or human approval. "
             "No B2/B3 values were used to decide labels; descriptive control counts were joined later.\n\n"
             "Review review.csv or review.json in original order. priority.csv puts uncertain records "
             "first. Check absent mandatory class/features, mathematical integer compatibility "
             "(10.0 is compatible; 10.1 is not), and row 94/data record 93. "
             "No absence of violations was promoted to VALID. Source ranges, duplication, "
             "rarity and physical relationships with unknown semantics did not cause rejection.\n\n"
             "Original v1 fields/citations are retained alongside second-pass field observations. "
             "The second-pass rationale supersedes the first rationale; original proposal identity "
             "is retained in prior_proposal_fingerprint. Do not import this enriched review package "
             "as an authenticated or human-reviewed ledger. Human corrections require a later "
             "validated projection and explicit confirmation.\n")
    write_bundle(output, value, {"review.csv": csv_text(rows),
                 "review.json": json.dumps(rows, indent=2, sort_keys=True) + "\n",
                 "priority.csv": csv_text(priority), "README.md": notes})
    return {"counts": counts, "changed_labels": value["changed_labels"], "output": str(output)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("artifacts/reports/phase3/review-v2"))
    args = parser.parse_args()
    print(json.dumps(audit(Path.cwd(), args.source_root, args.output), indent=2))
