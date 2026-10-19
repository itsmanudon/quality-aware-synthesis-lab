"""Render a source-backed M2 report/figures from saved diagnostics; never refit."""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from rcqasyn.phase2.common import csv_text, envelope, read_bundle
from rcqasyn.phase2.workflow import load_preparation
from rcqasyn.phase3.workflow import read_results
from rcqasyn.storage.artifacts import create_run_dir, write_json, write_text
from rcqasyn.storage.ownership import seal_bundle, write_scope


def table(headers: list[str], rows: list[list[Any]]) -> str:
    def cell(value: Any) -> str:
        return "n/a" if value is None else f"{value:.4g}" if isinstance(value, float) else str(value)
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |",
                       *["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]])


def save(fig: Any, output: Path, name: str) -> None:
    for extension in ("png", "svg"):
        stream = io.BytesIO()
        options = {"metadata": {"Date": None}} if extension == "svg" else {}
        fig.savefig(stream, format=extension, dpi=220, bbox_inches="tight", **options)
        path = output / f"{name}.{extension}"
        with write_scope(path), path.open("xb") as target:
            target.write(stream.getvalue())
    plt.close(fig)


def render(root: Path, experiments: Path, output: Path) -> dict[str, Any]:
    manifest = read_bundle(experiments / "manifest")
    runs = {r["name"]: read_results(experiments / r["name"]) for r in manifest["runs"]}
    baseline = runs["baseline-k5-a10"]
    _, crosswalks, _, _ = load_preparation(root / "artifacts/reports/phase2/gate-a-v3")
    occurrences = {r["occurrence_id"]: r for cw in crosswalks for r in cw["records"]}
    datasets = sorted(baseline["summary"])
    data = {d: {f: {r["occurrence_id"]: r for r in baseline["evidence"]
                    if r["dataset_id"] == d and r["validator_family"] == f}
                for f in ("authoritative_structure", "local_support", "cross_feature")} for d in datasets}
    rows, controls, cases, sensitivity, availability, predicates = [], [], [], [], [], []
    for d in datasets:
        s = baseline["summary"][d]; f = s["families"]
        ref = baseline["reference_populations"][d]
        rows.append([d, len(data[d]["authoritative_structure"]), ref["train_rows"],
            f["authoritative_structure"]["authoritative_invalid"],
            f["local_support"]["status_counts"].get("AVAILABLE", 0),
            f["cross_feature"]["status_counts"].get("AVAILABLE", 0),
            f["local_support"]["quantiles"].get("median"),
            f["cross_feature"]["quantiles"].get("median"), s["local_cross_feature_spearman"],
            len(s["tail_intersection"]), len(s["tail_disagreement"]), len(s["structural_vs_b2_disagreement"])])
        for family, stats in f.items():
            status = stats["status_counts"]
            availability.append([d, family, status.get("AVAILABLE", 0), status.get("PARTIAL", 0), status.get("UNAVAILABLE", 0)])
        selected = [r for r in occurrences.values() if r["dataset_id"] == d]
        flagged = {k for k, row in data[d]["authoritative_structure"].items() if row["authoritative_validity"] == "INVALID"}
        rejected = {r["occurrence_id"] for r in selected if not r["controls"]["b2"]["decision"]["accepted"]}
        predicates.append([d, len(flagged - rejected), len(rejected - flagged), len(flagged & rejected)])
        for b in ("b1", "b2", "b3"):
            local = f["local_support"]["by_recorded_controls"][b]
            global_ = f["cross_feature"]["by_recorded_controls"][b]
            controls.append([d, b.upper(), sum(r["controls"][b]["decision"]["accepted"] for r in selected), sum(not r["controls"][b]["decision"]["accepted"] for r in selected), local["accepted"]["n_scored"], local["rejected"]["n_scored"],
                local["accepted"]["median"], local["rejected"]["median"], global_["accepted"]["median"], global_["rejected"]["median"]])
        chosen = list(dict.fromkeys(s["tail_disagreement"][:3] + s["structural_violations_with_local_score_zero"][:2]
                                   + s["structural_vs_b2_disagreement"][:2] + [k for k, row in data[d]["local_support"].items() if row["status"] == "UNAVAILABLE"]))
        for key in chosen:
            original = occurrences[key]
            cases.append({"dataset_id": d, "occurrence_id": key,
                "source_ordinal": original["source_occurrence_ordinal"],
                "source_artifact": original["source_artifact"], "payload_sha256": original["payload_sha256"],
                "payload": original["payload"], "structure": data[d]["authoritative_structure"][key]["authoritative_validity"],
                "structural_violations": data[d]["authoritative_structure"][key]["quantities"]["violations"],
                "local_score": data[d]["local_support"][key]["raw_score"],
                "cross_feature_score": data[d]["cross_feature"][key]["raw_score"],
                "recorded_b2_accepted": original["controls"]["b2"]["decision"]["accepted"],
                "recorded_b3_accepted": original["controls"]["b3"]["decision"]["accepted"],
                "selection": "Exploratory family-tail or structural/control-disagreement case; no human truth claim."})
        for name, run in runs.items():
            rs = run["summary"][d]
            sensitivity.append({"dataset": d, "configuration": name,
                "k": run["configuration"]["k"], "shrinkage": run["configuration"]["shrinkage"],
                "local_median": rs["families"]["local_support"]["quantiles"].get("median"),
                "cross_feature_median": rs["families"]["cross_feature"]["quantiles"].get("median"),
                "spearman": rs["local_cross_feature_spearman"],
                "tail_disagreement_count": len(rs["tail_disagreement"])})
    decision_rows = [
        {"task": "Accept/correct 120 labels", "status": "HUMAN_DECISION_PENDING", "judgment": "Personal inspection and correction of every proposed label", "why": "Required before ground-truth performance evaluation", "evidence": "review-v2 original values, declarations, per-field findings and uncertainty", "options": "Retain/correct/INDETERMINATE with evidence", "current_impact": "No human precision/recall/F1 permitted", "safe_work": "TRAIN-only diagnostics, source/control behavior comparisons"},
        {"task": "Resolve domain semantics", "status": "HUMAN_DECISION_PENDING", "judgment": "Original target mappings, physical meanings/units and cross-field requirements", "why": "Could expand defensible validity evidence", "evidence": "Three frozen specifications and nine grouped gaps", "options": "Retain unknowns or supply authoritative sources and approve a new version", "current_impact": "Conservative structure-only validity findings", "safe_work": "Statistical support with explicit assumptions"},
        {"task": "Scientifically accept M2", "status": "HUMAN_DECISION_PENDING", "judgment": "Whether these evidence families/assumptions meet research objectives", "why": "Engineering completion is not scientific acceptance", "evidence": "Methods, five configurations, figures, source-bound cases and tests", "options": "Accept with limitations or request scoped changes", "current_impact": "All results remain exploratory", "safe_work": "Preserve/reproduce current diagnostics"},
        {"task": "Independent external verification and final acceptance", "status": "HUMAN_DECISION_PENDING", "judgment": "Arrange final scientific verification after supervisor review", "why": "No phase is scientifically frozen yet", "evidence": "Local commits, QA evidence and historical inventories", "options": "Verify after label corrections and scope acceptance", "current_impact": "No merge/push/freeze", "safe_work": "Internal read-only review and final regression"},
    ]
    value = envelope("m2-exploratory-report-v1", {
        "scientific_status": "EXPLORATORY_HUMAN_LABEL_EVALUATION_PENDING",
        "phase2_parent_commit": baseline["phase2_parent_commit"],
        "scoring_implementation_revision": baseline["implementation_revision"],
        "experiment_manifest_fingerprint": manifest["fingerprint"],
        "result_fingerprints": {name: r["fingerprint"] for name, r in runs.items()},
        "stable_replay": manifest["stable_replay"], "candidate_count": 601,
        "configuration_count": len(runs), "evidence_records_per_configuration": 1803,
        "baseline_summary_rows": rows, "sensitivity": sensitivity, "availability": availability, "predicate_disagreement": predicates,
        "cases": cases, "decision_ledger": decision_rows,
        "matplotlib_version": matplotlib.__version__,
        "human_validated_performance_claimed": False,
    })
    report = ["# RC-QASyn Phase-3 M2 exploratory results", "",
        "Status: implemented engineering and exploratory experiment; human-label evaluation and scientific acceptance pending.", "",
        "## Motivation and architecture", "",
        ("The aim is complementary interpretable evidence, not a single score or automatic admission. "
        "Authoritative structure tests justified source requirements; local mixed-type neighborhoods "
        "describe nearby TRAIN support; global shrinkage-covariance distance describes learned cross-feature "
        "relationships. Statistical rarity and structural invalidity remain distinct. No superiority, "
        "calibrated validity probability or novelty is established by this selected retrospective study."), "",
        (f"Phase-2 parent: `{baseline['phase2_parent_commit']}`. Scoring implementation: `{baseline['implementation_revision']}`. "
        "Phase-2 human review is unfinished; no scientific freeze is claimed."), "",
        ("The exact equations, authority rules, missingness policy, one-hot encoding, class-support caveats "
        "and reproduction commands are in docs/phase3-m2-methods.md. Local distance is the mean k-nearest "
        "clipped TRAIN-range-scaled numeric / nominal-mismatch distance. Global distance is the square root "
        "of dimension-normalized shrinkage Mahalanobis distance after TRAIN median/IQR scaling and one-hot encoding. "
        "There is no cross-family fusion. Class diagnostics are descriptive neighbor fractions, not a fitted classifier."), "",
        "## Source and experimental design", "",
        ("All 601 historical occurrences are retained: Abalone19 200, Ecoli4 201 and page-blocks0 200. "
        "TRAIN references use the frozen source split only. The 120 second-pass proposals were never used "
        "to fit models, choose thresholds/configurations or compute ground-truth performance. No REAL TEST "
        "value or label enters fitting or configuration selection. Integrity checks read original source "
        "files; exact TRAIN subset fingerprints and row IDs are retained with every run."), "",
        ("Five configurations were fixed a priori: k=5/alpha=0.1 baseline; k=3, k=11; alpha=0.05, alpha=0.25. "
        "Each produces 1,803 evidence records (601 occurrences x three families). One independent deterministic "
        "offline replay matched evidence, fitted parameters and reference identities exactly. Earlier development "
        "runs remain preserved; tables below use experiments-v2 exclusively."), "",
        "## Per-dataset baseline results", "",
        table(["Dataset", "Candidates", "TRAIN", "Structural INVALID", "Local available", "Global available", "Local median", "Global median", "Rank rho", "Tail intersection", "Tail disagreement", "Structural/B2 disagreement"], rows), "",
        ("Structural INVALID is a source-rule flag, not a human-approved label. NOT_ESTABLISHED is never relabeled VALID. "
        "Unavailability is reported rather than imputed. Tail sets use the candidate 90th percentile only for case selection; "
        "they are not admission thresholds. Ties can increase their sizes. Rank disagreement demonstrates different views, "
        "not proof that one family is correct."), "",
        table(["Dataset", "Family", "Available", "Partial", "Unavailable"], availability), "",
        ("The Ecoli4 occurrence with missing numerical features cannot receive either statistical score. "
        "It is retained as UNAVAILABLE and included among the source-bound cases, not silently discarded. "
        "The baseline table below distinguishes total recorded admissions from scored-subset denominators."), "",
        "![Evidence distributions](score-distributions.png)", "",
        "![Local and global evidence disagreement](evidence-disagreement.png)", "",
        "## Recorded baseline behavior comparisons", "",
        table(["Dataset", "Control", "Total accepted", "Total rejected", "Local n accepted", "Local n rejected", "Local median accepted", "Local median rejected", "Global median accepted", "Global median rejected"], controls), "",
        ("These are group descriptions under frozen decisions, not accuracy or error estimates. B1 accepts parseable "
        "candidates; B2 applies original severity and duplicate checks; B3 is the original single judge. M2 additionally "
        "uses source integer declarations and nominal source domains while excluding duplicate-based rejection and "
        "requested-class matching as authoritative record truth. These predicate differences explain some disagreement."), "",
        table(["Dataset", "Structural flag/B2 accept", "B2 reject/no structural flag", "Both flag/reject"], predicates), "",
        ("Non-overlap is disagreement between different predicates, not an estimate of false acceptance "
        "or false rejection. Original B2 duplicate and target-conditioning decisions remain intact."), "",
        "![Structural flags and recorded B2 outcomes](control-evidence.png)", "",
        "## Sensitivity", "",
        table(["Dataset", "Configuration", "Local median", "Global median", "Rank rho", "Tail disagreement"],
              [[s[k] for k in ("dataset", "configuration", "local_median", "cross_feature_median", "spearman", "tail_disagreement_count")] for s in sensitivity]), "",
        "![Sensitivity of evidence medians](sensitivity.png)", "",
        ("No configuration is selected as a winner. k changes neighborhood scale and duplicate/tie influence; "
        "alpha changes regularization of cross-feature relationships. These sensitivities are descriptive and "
        "cannot establish human-validity performance without reviewed labels."), "",
        "## Interpretable cases", "",
        table(["Dataset", "Source ordinal", "Structural state", "Local score", "Global score", "B2 accepted", "B3 accepted"],
              [[c[k] for k in ("dataset_id", "source_ordinal", "structure", "local_score", "cross_feature_score", "recorded_b2_accepted", "recorded_b3_accepted")] for c in cases]), "",
        ("cases.csv and artifact.json retain full payloads, occurrence IDs, source locators, rule observations "
        "and fingerprints. Cases were selected from family-tail disagreement, structural/control disagreement "
        "and structural violations with zero local distance. Strong local feature support can coexist with "
        "a missing mandatory target or other structural defect. The examples are illustrative, not representative."), "",
        "## Runtime and reproducibility", "",
        table(["Configuration", "Pre-persistence seconds", "Evidence rows"], [[r["name"], r["runtime_seconds"], r["evidence_records"]] for r in manifest["runs"]]), "",
        ("Runtime includes source verification, fitting, scoring and summary preparation; excludes final bundle "
        "persistence and is an observed workstation measurement rather than a benchmark guarantee. The five runs "
        "use deterministic closed-form models; seed 42 is retained but no stochastic estimator consumes it. "
        "Environment, model matrices, TRAIN identities and exact configuration are in each sealed result bundle. "
        "Replay compares evidence_content_fingerprint, not runtime-bearing outer artifact fingerprints. "
        "Run scripts/run_phase3_experiments.py --source-root SOURCE_ROOT; then scripts/report_phase3.py. "
        "Render with the recorded Matplotlib version for the same figure environment."), "",
        "## Limitations and pending decisions", "",
        ("The original target mappings, physical meanings/units and cross-field hard rules remain unresolved. "
        "Historical page-blocks0 TRAIN/TEST exact-value overlap remains a limitation. TRAIN duplicates can inflate "
        "local support; sparse minority neighborhoods can be unstable. The global elliptical approximation may "
        "miss nonlinear/multimodal structure and depend on scaling/regularization. Resubstitution TRAIN tail "
        "fractions are not calibrated p-values. The source-selected population and retained 120-row review "
        "cohort do not justify population-wide validity claims. Retaining 40 overlap records does not create "
        "a second human rater or establish inter-rater agreement."), "",
        table(["Task", "Status", "Human judgment", "Impact", "Safely executable"],
              [[d[k] for k in ("task", "status", "judgment", "current_impact", "safe_work")] for d in decision_rows]), "",
        ("The complete decision-ledger.csv also records evidence, options and why each decision matters. "
        "No human labels or signatures were manufactured. Official B2/B3-versus-human analysis is deferred. "
        "Phase-3 engineering completion does not complete Phase-2 human review or scientific acceptance."), "",
        "## Implemented, exploratory, pending and deferred", "",
        ("Implemented and tested: evidence contracts/registry; three validators; source-bound TRAIN-only runner/readers; "
        "determinism, abstention, mixed types, source integrity and held-out perturbation checks. "
        "Exploratory: five offline configurations, control/family disagreements and illustrative cases. "
        "Pending human-label evaluation: personal correction of 120 labels, explicit reviewed-ledger confirmation, "
        "authorized ground-truth evaluation and scientific acceptance. "
        "Deferred to Phase 4: calibrated fusion, risk-aware admission, decision thresholds and contribution/selection "
        "policies. No Phase-4 implementation, new synthesizer, paid generation, dataset addition or ML migration occurred."), ""]
    create_run_dir(output.parent, output.name)
    write_json(output / "artifact.json", value)
    write_text(output / "report.md", "\n".join(report))
    write_text(output / "cases.csv", csv_text(cases))
    write_text(output / "sensitivity.csv", csv_text(sensitivity))
    write_text(output / "decision-ledger.csv", csv_text(decision_rows))
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "figure.facecolor": "white", "svg.hashsalt": "rcqasyn-m2-v1"})
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), constrained_layout=True)
    for i, d in enumerate(datasets):
        for j, family in enumerate(("local_support", "cross_feature")):
            scores = sorted(r["raw_score"] for r in data[d][family].values() if r["raw_score"] is not None)
            axes[j, i].plot(scores, np.arange(1, len(scores) + 1) / len(scores), color="#176B87", linewidth=1.8)
            axes[j, i].set(title=d, xlabel="Local mean distance" if j == 0 else "Global covariance distance", ylabel="Cumulative scored-candidate fraction")
            if j == 1 and d == "page-blocks0":
                axes[j, i].set_xscale("symlog", linthresh=1)
    save(fig, output, "score-distributions")
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), constrained_layout=True)
    for ax, d in zip(axes, datasets, strict=True):
        local, global_ = data[d]["local_support"], data[d]["cross_feature"]
        for state, color in (("NOT_ESTABLISHED", "#176B87"), ("INVALID", "#B84336")):
            keys = [k for k in local.keys() & global_.keys() if local[k]["raw_score"] is not None and global_[k]["raw_score"] is not None and data[d]["authoritative_structure"][k]["authoritative_validity"] == state]
            ax.scatter([local[k]["raw_score"] for k in keys], [global_[k]["raw_score"] for k in keys], s=15, alpha=0.65, c=color, label="Structural " + state)
        ax.set(title=d, xlabel="Local mean distance", ylabel="Global covariance distance")
        if d == "page-blocks0":
            ax.set_yscale("symlog", linthresh=1)
        ax.legend(fontsize=7)
    save(fig, output, "evidence-disagreement")
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), constrained_layout=True)
    for i, d in enumerate(datasets):
        for j, (names, field, labels) in enumerate((
            (["sensitivity-k3", "baseline-k5-a10", "sensitivity-k11"], "local_median", ["k=3", "k=5", "k=11"]),
            (["sensitivity-a05", "baseline-k5-a10", "sensitivity-a25"], "cross_feature_median", ["alpha=.05", "alpha=.10", "alpha=.25"]))):
            points = [next(s[field] for s in sensitivity if s["dataset"] == d and s["configuration"] == name) for name in names]
            axes[j, i].plot(labels, points, marker="o", color="#176B87")
            axes[j, i].set(title=d, ylabel="Median local distance" if j == 0 else "Median global distance")
    save(fig, output, "sensitivity")
    fig, ax = plt.subplots(figsize=(9, 4), constrained_layout=True)
    x = np.arange(3)
    flags = [baseline["summary"][d]["families"]["authoritative_structure"]["authoritative_invalid"] for d in datasets]
    rejects = [sum(not r["controls"]["b2"]["decision"]["accepted"] for r in occurrences.values() if r["dataset_id"] == d) for d in datasets]
    ax.bar(x - .18, flags, .36, label="M2 authoritative structural flags", color="#B84336")
    ax.bar(x + .18, rejects, .36, label="Recorded B2 rejections", color="#176B87")
    ax.set(xticks=x, xticklabels=datasets, ylabel="Candidate count", title="Different predicates; no human-ground-truth performance claim")
    ax.legend(fontsize=9)
    save(fig, output, "control-evidence")
    seal_bundle(output)
    print(json.dumps({"report": str(output / "report.md"), "baseline_rows": rows,
                      "cases": len(cases), "report_fingerprint": value["fingerprint"]}, indent=2))
    return value


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiments", type=Path, default=Path("artifacts/reports/phase3/experiments-v2"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/reports/phase3/m2-report-v2"))
    args = parser.parse_args()
    root = Path.cwd()
    output = (root / args.output).resolve()
    namespace = (root / "artifacts/reports/phase3").resolve()
    if output == namespace or not output.is_relative_to(namespace):
        raise ValueError("report output must be a new Phase-3 artifact version")
    render(root, root / args.experiments, output)
