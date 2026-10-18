from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from rcqasyn.storage.ownership import bundle_lock

from .annotations import gate_a, review_history
from .approval import authenticate_review
from .common import digest, envelope
from .contracts import HumanDecision
from .fixture_approval import FixtureTrustAnchor


def _confusion(rows: list[dict[str, Any]], baseline: str) -> dict[str, Any]:
    determinate = [r for r in rows if r["label"] != "INDETERMINATE"]
    tp = sum(r["label"] == "INVALID" and not r[baseline] for r in determinate)
    fp = sum(r["label"] == "VALID" and not r[baseline] for r in determinate)
    fn = sum(r["label"] == "INVALID" and r[baseline] for r in determinate)
    tn = sum(r["label"] == "VALID" and r[baseline] for r in determinate)
    def ratio(n: int, d: int) -> float | None:
        return n / d if d else None
    return {"positive_class": "INVALID", "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "false_acceptance": fn, "false_rejection": fp,
            "false_acceptance_rate": ratio(fn, fn + tp),
            "false_rejection_rate": ratio(fp, fp + tn),
            "binary_denominator": len(determinate),
            "indeterminate": len(rows) - len(determinate)}


def analyze(root: Path, cohort: dict[str, Any], crosswalks: list[dict[str, Any]],
            protocol: dict[str, Any], approval: dict[str, Any],
            proposals: list[dict[str, Any]], history: Path,
            *, fixture_only: bool = False,
            supervisor_attestation: dict[str, Any] | None = None,
            trust_config: Path | None = None) -> dict[str, Any]:
    # No per-call policy or fixture flag can establish production authority.
    if fixture_only:
        raise ValueError("use the separate untrusted fixture analysis API")
    authenticate_review(root, cohort, crosswalks, protocol, approval, proposals,
                        history, supervisor_attestation, trust_config)
    raise ValueError("protected supervisor approval unavailable")


def diagnose_fixture_analysis(root: Path, cohort: dict[str, Any],
                               crosswalks: list[dict[str, Any]], protocol: dict[str, Any],
                               approval: dict[str, Any], proposals: list[dict[str, Any]],
                               history: Path, *, supervisor_attestation: dict[str, Any] | None,
                               fixture_anchor: FixtureTrustAnchor | None = None) -> dict[str, Any]:
    from .fixture_approval import diagnose_fixture_review

    if cohort.get("population_kind") != "synthetic_fixture":
        raise ValueError("fixture diagnostics refuse research populations")
    attestation = gate_a(root, cohort, crosswalks, protocol, approval)
    with bundle_lock(history):
        authenticated = diagnose_fixture_review(root, cohort, crosswalks, protocol, approval,
                                                 proposals, history, supervisor_attestation,
                                                 fixture_anchor)
        events = review_history(history)
    byrow = {r["review_row_id"]: r for r in cohort["records"]}
    proposed = {r["review_row_id"]: r for r in proposals}
    final = {d["review_row_id"]: HumanDecision.model_validate_json(json.dumps(d))
             for d in authenticated["approved_decisions"]}
    rows = []
    for key, source in byrow.items():
        proposal, decision = proposed[key], final[key]
        if any(proposal[k] != source[k] for k in ("occurrence_id", "payload_sha256", "dataset_id")):
            raise ValueError("proposal has foreign occurrence metadata")
        if (decision.occurrence_id != source["occurrence_id"]
                or decision.payload_sha256 != source["payload_sha256"]):
            raise ValueError("approved label has foreign occurrence binding")
        rows.append({"review_row_id": key, "occurrence_id": source["occurrence_id"],
                     "payload_sha256": source["payload_sha256"],
                     "dataset_id": source["dataset_id"], "requested_class": source["requested_class"],
                     "label": decision.human_final_label,
                     "b2": source["controls"]["b2"]["decision"]["accepted"],
                     "b3": source["controls"]["b3"]["decision"]["accepted"],
                     "b3_recorded_verdict": source["controls"]["b3"]["result"]["verdict"]})
    return envelope("untrusted-fixture-analysis-v1", {
        "official": False, "production_approval": False,
        "population_kind": "synthetic_fixture",
        "cohort_fingerprint": cohort["fingerprint"], "protocol_fingerprint": protocol["fingerprint"],
        "crosswalk_fingerprints": cohort["crosswalk_fingerprints"],
        "gate_a_approval_fingerprint": digest(attestation.model_dump(mode="json")),
        "proposal_set_fingerprint": digest([proposed[k] for k in sorted(proposed)]),
        "review_event_fingerprints": [e["fingerprint"] for e in events],
        "approved_ledger_fingerprint": digest([final[k].model_dump(mode="json") for k in sorted(final)]),
        "approved_decisions": [final[k].model_dump(mode="json") for k in sorted(final)],
        "validation_status": "UNTRUSTED_FIXTURE_LABELS_DIAGNOSTIC",
        "supervisor_attestation_fingerprint": digest(authenticated["attestation"]),
        "trusted_supervisor_key_id": authenticated["trusted_key_id"],
        "trust_configuration_fingerprint": authenticated["trust_configuration_fingerprint"],
        **comparison_metrics(rows, sampling_limitation=cohort["selection_limitations"]),
    })


def comparison_metrics(rows: list[dict[str, Any]], *, sampling_limitation: str = "") -> dict[str, Any]:
    determinate = [r for r in rows if r["label"] != "INDETERMINATE"]
    errors = {b: {r["occurrence_id"] for r in determinate
                  if r[b] != (r["label"] == "VALID")} for b in ("b2", "b3")}
    return {
        "label_counts": dict(Counter(r["label"] for r in rows)),
        "b3_recorded_verdict_counts": dict(Counter(r["b3_recorded_verdict"] for r in rows)),
        "controls_unchanged": True, "control_view": "original recorded admission decisions",
        "overall": {b: _confusion(rows, b) for b in ("b2", "b3")},
        "by_dataset": {d: {b: _confusion([r for r in rows if r["dataset_id"] == d], b)
                          for b in ("b2", "b3")} for d in sorted({r["dataset_id"] for r in rows})},
        "by_requested_class": {c: {b: _confusion([r for r in rows if r["requested_class"] == c], b)
                                  for b in ("b2", "b3")}
                               for c in sorted({r["requested_class"] for r in rows})},
        "machine_disagreements": [r for r in rows if r["b2"] != r["b3"]],
        "shared_error_occurrence_ids": sorted(errors["b2"] & errors["b3"]),
        "individual_failure_cases": [r for r in determinate if
                                     r["occurrence_id"] in errors["b2"] | errors["b3"]],
        "rows": rows, "sampling_limitation": sampling_limitation,
        "interpretation": "Exploratory selected-cohort audit; no population-wide accuracy claim.",
    }


def analyze_research(root: Path, cohort: dict[str, Any], crosswalks: list[dict[str, Any]],
                     protocol: dict[str, Any], scope_approval: dict[str, Any],
                     proposals: list[dict[str, Any]], ledger: dict[str, Any],
                     confirmation: dict[str, Any], *, implementation_revision: str
                     ) -> dict[str, Any]:
    """Consume explicitly confirmed human research labels; never grant production approval."""
    import platform
    from importlib.metadata import version

    from .research import RESEARCH, confirm_research_ledger, research_rubric

    confirmed = confirm_research_ledger(root, cohort, crosswalks, protocol, scope_approval,
                                        proposals, ledger, confirmation)
    if (len(implementation_revision) != 40
            or any(c not in "0123456789abcdef" for c in implementation_revision)):
        raise ValueError("report requires the exact implementation commit")
    final = {r["review_row_id"]: r for r in ledger["rows"]}
    rows = [{"review_row_id": r["review_row_id"], "occurrence_id": r["occurrence_id"],
             "payload_sha256": r["payload_sha256"], "dataset_id": r["dataset_id"],
             "requested_class": r["requested_class"],
             "label": final[r["review_row_id"]]["human_final_label"],
             "b2": r["controls"]["b2"]["decision"]["accepted"],
             "b3": r["controls"]["b3"]["decision"]["accepted"],
             "b3_recorded_verdict": r["controls"]["b3"]["result"]["verdict"]}
            for r in cohort["records"]]
    return envelope("supervisor-reviewed-research-analysis-v1", {
        **RESEARCH, "official": False, "population_kind": cohort["population_kind"],
        "validation_status": "SUPERVISOR_CONFIRMED_RESEARCH_LABELS",
        "implementation_revision": implementation_revision, "python_version": platform.python_version(),
        "dependency_versions": {name: version(name) for name in
                                ("pydantic", "numpy", "pandas", "scipy", "scikit-learn")},
        "cohort_fingerprint": cohort["fingerprint"],
        "crosswalk_fingerprints": cohort["crosswalk_fingerprints"],
        "protocol_fingerprint": protocol["fingerprint"],
        "research_rubric": research_rubric(protocol), "scope_approval": scope_approval,
        "scope_approval_fingerprint": ledger["scope_approval_fingerprint"],
        "proposal_set_fingerprint": ledger["proposal_set_fingerprint"],
        "reviewed_ledger_fingerprint": ledger["fingerprint"],
        "supervisor_confirmation": confirmed,
        "source_files": {k: v for artifact in [*crosswalks, cohort, protocol]
                         for k, v in artifact["source_files"].items()},
        "controls_unchanged": True, "control_view": "original recorded admission decisions",
        "overlap_review_row_ids": cohort["overlap_review_row_ids"],
        "overlap_interpretation": "Historical overlap retained; one supervisor's review "
        "does not establish two independent raters or inter-rater agreement.",
        **comparison_metrics(rows, sampling_limitation=cohort["selection_limitations"]),
    })


def research_report(result: dict[str, Any]) -> str:
    """Render a durable report from the exact saved research result."""
    lines = ["# RC-QASyn Phase-2 supervisor-reviewed research results", "",
             ("This is a supervisor-confirmed academic research ledger. It is not "
             "cryptographically authenticated and confers no production approval."), "",
             f"Implementation: {result['implementation_revision']}",
             f"Result fingerprint: {result['fingerprint']}",
             f"Cohort fingerprint: {result['cohort_fingerprint']}",
             f"Reviewed ledger fingerprint: {result['reviewed_ledger_fingerprint']}", "",
             f"Labels: {json.dumps(result['label_counts'], sort_keys=True)}", "",
             ("INVALID is the positive class. False acceptance means accepting an INVALID "
             "record; false rejection means rejecting a VALID record. INDETERMINATE labels "
             "are counted separately and excluded from binary denominators. Original B3 "
             "verdicts and admission decisions are retained, including abstentions."), "",
             "| Group | Baseline | TP | FP | FN | TN | Binary n | Indeterminate | FA rate | FR rate |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    groups = {"overall": result["overall"], **result["by_dataset"]}
    for group, baselines in groups.items():
        for baseline, m in baselines.items():
            cells = [group, baseline.upper(), *(str(m[k]) for k in (
                "tp", "fp", "fn", "tn", "binary_denominator", "indeterminate",
                "false_acceptance_rate", "false_rejection_rate"))]
            lines.append("| " + " | ".join(cells) + " |")
    lines += ["", "## Interpretation and reproduction", "", result["sampling_limitation"],
              result["interpretation"], result["overlap_interpretation"], "",
              ("No B1/B2/B3 method, threshold, split or generation output was changed. "
              "The result artifact includes dataset/class breakdowns, B3 verdict counts, "
              "disagreements and individual/shared failures. Comparisons and reviewed labels "
              "are also exported as CSV/JSON."), "",
              ("Reproduce with the recorded implementation commit and dependency versions, "
              "the preserved source preparation bundle, proposal checkpoint, scope approval, "
              "reviewed ledger and exact explicit confirmation. Use phase2 research analyze "
              "with these same inputs and a new output version. The bundle includes the "
              "scope approval, proposals, reviewed ledger and confirmation used in this run."), "",
              ("Source fingerprints detect input mismatches; they do not authenticate human "
              "identity or resist a malicious agent with the same permissions."), ""]
    return "\n".join(lines)
