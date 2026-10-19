"""Reproducible report and standard scientific plots from sealed shadow evidence."""
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

from rcqasyn.phase2.common import csv_text, envelope
from rcqasyn.phase2.workflow import load_preparation
from rcqasyn.phase4.contracts import ACTIONS
from rcqasyn.phase4.workflow import read_shadow
from rcqasyn.storage.artifacts import create_run_dir, write_json, write_text
from rcqasyn.storage.ownership import seal_bundle, write_scope

plt.rcParams.update({"svg.hashsalt": "rcqasyn-phase4-report-v1", "font.size": 10})


def table(headers: list[str], rows: list[list[Any]]) -> str:
    def cell(v: Any) -> str:
        return f"{v:.4g}" if isinstance(v, float) else str(v)
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"]*len(headers)) + " |",
                       *["| " + " | ".join(cell(v) for v in r) + " |" for r in rows]])


def save(fig: Any, output: Path, name: str) -> None:
    for ext in ("png", "svg"):
        stream = io.BytesIO()
        opts = {"metadata": {"Date": None}} if ext == "svg" else {}
        fig.savefig(stream, format=ext, dpi=180, bbox_inches="tight", **opts)
        path = output/f"{name}.{ext}"
        with write_scope(path), path.open("xb") as target:
            target.write(stream.getvalue())
    plt.close(fig)


def report_data(root: Path, experiment: Path, replay: Path | None = None) -> dict[str, Any]:
    raw = read_shadow(experiment)
    value = read_shadow(experiment, root/raw["m2_input"])
    stable = None
    if replay is not None:
        other = read_shadow(replay, root/raw["m2_input"])
        stable = (value["decision_content_fingerprint"] == other["decision_content_fingerprint"]
                  and value["harmonized"] == other["harmonized"])
        if not stable:
            raise ValueError("offline replay differs")
    _, cws, _, _ = load_preparation(root/"artifacts/reports/phase2/gate-a-v3")
    originals = {r["occurrence_id"]: r for cw in cws for r in cw["records"]}
    policies = [p["name"] for p in value["plan"]["policies"]]
    datasets = sorted(value["dependence"])
    rows, controls, classes = [], [], []
    for p in policies:
        for d in datasets:
            s = value["summary"][p][d]
            rows.append({"dataset": d, "policy": p, "n": s["n"], **s["actions"]})
            for c, counts in s["literal_payload_class_breakdown"].items():
                classes.append({"dataset": d, "policy": p, "literal_payload_class": c,
                                **{a: counts.get(a, 0) for a in ACTIONS}})
            for b, c in s["controls"].items():
                controls.append({"dataset": d, "policy": p, "control": b,
                    "recorded_accepted": c["recorded_accepted"],
                    "provisional_pass": s["actions"]["PROVISIONAL_PASS"],
                    "provisional_pass_symmetric_difference": c["provisional_pass_symmetric_difference"],
                    "joint_action_acceptance": c["cross_table"]})
    vectors = {v["occurrence_id"]: v for v in value["harmonized"]["vectors"]}
    base = [r for r in value["decisions"] if r["policy"]["name"] == "combined-review"]
    cases = []
    for d in datasets:
        group = [r for r in base if r["dataset_id"] == d]
        conditions = {
            "structural_rejection": lambda r: r["action"] == "REJECT_STRUCTURAL",
            "family_concern_disagreement": lambda r: r["statistical_disagreement"] is True and r["action"] == "REVIEW_REQUIRED",
            "provisional_pass_not_validity": lambda r: r["action"] == "PROVISIONAL_PASS",
            "missing_statistical_evidence": lambda r: bool(r["missing_any_statistical_family"]),
            "structural_B2_behavior_difference": lambda r: (r["structural_judgment"] == "INVALID") == originals[r["occurrence_id"]]["controls"]["b2"]["decision"]["accepted"],
        }
        for category, predicate in conditions.items():
            row = next((r for r in group if predicate(r)), None)
            if row is None:
                continue
            o = originals[row["occurrence_id"]]; v = vectors[row["occurrence_id"]]
            cases.append({"dataset": d, "selection": category, "occurrence_id": row["occurrence_id"],
                "source_ordinal": o["source_occurrence_ordinal"], "payload_sha256": o["payload_sha256"],
                "payload": o["payload"], "action": row["action"], "normalized": v["normalized"],
                "structural_findings": v["structural"], "explanation": row["explanation"],
                "missing_evidence": row["missing_any_statistical_family"],
                "recorded_B2_accepted": o["controls"]["b2"]["decision"]["accepted"],
                "recorded_B2_reason": o["controls"]["b2"]["decision"]["reason"],
                "not_ground_truth": True})
    decisions = [
        {"decision": "Personal review of all 120 labels", "status": "PENDING_SUPERVISOR", "dependency": "Source-bound reviewed ledger plus explicit fingerprint confirmation; agent proposals are not ground truth"},
        {"decision": "Target mappings, physical meanings and cross-field semantics", "status": "PENDING_SUPERVISOR", "dependency": "Authoritative sources and approved specification version; keep nine grouped semantic gaps explicit"},
        {"decision": "Ground-truth calibration eligibility and partitioning", "status": "PENDING_SUPERVISOR", "dependency": "Confirmed independent labels, adequate VALID/INVALID support and separated calibration/evaluation IDs"},
        {"decision": "Official decision thresholds", "status": "PENDING_SUPERVISOR", "dependency": "Current q=.8/.9/.95 are fixed exploratory heuristics; no empirically tuned official threshold"},
        {"decision": "Scientific acceptance of Phase 3 and Phase 4", "status": "PENDING_SUPERVISOR", "dependency": "Review assumptions, reports, selected-cohort and historical TRAIN/TEST overlap limits"},
        {"decision": "Final scientific claims and independent acceptance", "status": "PENDING_SUPERVISOR", "dependency": "Human evidence and scientific assessment; no validated correctness, novelty or risk guarantee claimed"},
    ]
    return envelope("m4-m5-exploratory-report-v1", {"experiment_fingerprint": value["fingerprint"],
        "scoring_implementation_revision": value["implementation_revision"],
        "phase3_parent": value["phase3_parent"], "plan_fingerprint": value["plan_fingerprint"],
        "m2_bundle_fingerprint": value["m2_bundle_fingerprint"],
        "decision_content_fingerprint": value["decision_content_fingerprint"],
        "vector_content_fingerprint": value["harmonized"]["vector_content_fingerprint"],
        "replay_identical": stable, "policies": policies, "datasets": datasets,
        "candidate_count": len(vectors), "decision_count": len(value["decisions"]),
        "runtime_seconds": value["runtime_seconds"], "runtime_definition": "Source validation plus pure fusion/decisions/summary; excludes persistence/readback and report rendering",
        "results": rows, "controls": controls, "classes": classes, "dependence": value["dependence"],
        "calibration": value["calibration"], "sensitivity": value["sensitivity"],
        "cases": cases, "decision_ledger": decisions, "matplotlib_version": matplotlib.__version__,
        "scientific_status": "EXPLORATORY_SHADOW_ONLY_HUMAN_REVIEW_PENDING"})


def render(root: Path, experiment: Path, output: Path, replay: Path | None = None) -> dict[str, Any]:
    v = report_data(root, experiment, replay)
    output = create_run_dir(output.parent, output.name)
    write_json(output/"artifact.json", v)
    for name, rows in (("results", v["results"]), ("controls", v["controls"]), ("class-breakdown", v["classes"]),
                       ("cases", v["cases"]), ("sensitivity", v["sensitivity"]), ("decision-ledger", v["decision_ledger"])):
        write_text(output/f"{name}.csv", csv_text(rows))
    headers = ["Dataset", "Policy", "N", "Structural reject", "Review", "Provisional pass", "Abstain"]
    table_rows = [[r["dataset"], r["policy"], r["n"], *[r[a] for a in ACTIONS]] for r in v["results"]]
    # ACTIONS order is reject, review, pass, abstain; explicit column order above.
    ctl = [r for r in v["controls"] if r["policy"] == "combined-review"]
    dt = [[d, x["paired_n"], x["spearman"], x["concern_intersection"], x["concern_union"], x["concern_disagreement"], x["tail_jaccard"]] for d, x in v["dependence"].items()]
    text = ["# Phase-4 M4/M5 exploratory shadow results", "", "PHASE-4 ENGINEERING AND EXPLORATORY SHADOW EXPERIMENTS COMPLETE \u2014 HUMAN REVIEW PENDING", "",
        "These are behavior and evidence summaries, not calibrated validation performance. Phase 2 and Phase 3 are not scientifically frozen. No human truth metrics, real calibrator, final accepted dataset or provider calls were produced.", "",
        f"Exact Phase-3 parent: `{v['phase3_parent']}`. Scoring implementation: `{v['scoring_implementation_revision']}`.",
        f"Plan fingerprint: `{v['plan_fingerprint']}`. M2 input: `{v['m2_bundle_fingerprint']}`.",
        f"Decision content: `{v['decision_content_fingerprint']}`. Vector content: `{v['vector_content_fingerprint']}`.", "",
        "## Design and mathematical interpretation", "",
        "See docs/phase4-m4-m5-methods.md (repository root) for every formula, algorithm and reproduction command. Frozen M2 scores are ranked within dataset/family across the frozen generated-candidate population using u=(#lower+0.5*#equal)/n. Larger u means weaker statistical support. This reference includes the focal record and is not TRAIN or REAL TEST. Minimum n=10. Raw scores are preserved. U=max(uL,uG) and I=min(uL,uG) are descriptive and uncalibrated; no independent-evidence multiplication is used. Missing families produce null combined indices.", "",
        "Structure-only requires no statistical family; local/global require their named family; combined uses a union of concerns u>=0.9. Predeclared q=0.8 and q=0.95 are limited sensitivities. Authoritative structural rejection takes precedence, then required-missing abstention, partial-structure review, statistical review, otherwise provisional pass. PROVISIONAL_PASS is not human-validated VALID. Statistical support never establishes hard invalidity.", "",
        "## Per-dataset decisions", "", table(headers, table_rows), "", "![Shadow decisions](shadow-decisions.png)", "",
        "All policies retain the same 75 authoritative structural rejections (5 Abalone19, 6 Ecoli4, 64 page-blocks0). No statistical-only rejection occurs. Zero realized abstentions does not mean missingness was ignored: Ecoli4 occurrence 181 has no feature evidence but already has a substantiated structural violation, so rejection precedence applies. Both statistical families are available on 600/601 records (200 per dataset); required missingness remains explicit in every decision.", "",
        "## Dependence and agreement", "", table(["Dataset", "Paired N", "Spearman", "Both concerns", "Either", "Different concern", "Tail Jaccard"], dt), "",
        "![Evidence dependence](evidence-dependence.png)", "",
        "High Abalone19 correlation shows substantial redundancy. Ecoli4 family concerns differ more often. These relationships motivate explicit dependence reporting; they do not measure which family is correct. Counts in this table use all paired-available records before structural precedence, so review totals can be lower than the union count.", "",
        "## Recorded controls", "", table(["Dataset", "Control", "Recorded accepted", "Shadow provisional pass", "Symmetric difference"], [[r["dataset"], r["control"].upper(), r["recorded_accepted"], r["provisional_pass"], r["provisional_pass_symmetric_difference"]] for r in ctl]), "",
        "![Control behavior comparison](control-comparison.png)", "",
        "The symmetric difference compares the set of shadow provisional passes with recorded accepted occurrences. It is not an error count. Full per-policy joint action/acceptance tables are in controls.csv and artifact.json. Literal payload-class action counts, including missing class, are in class-breakdown.csv; requested_class is never imputed. Neither controls nor agent labels select these policies. B1/B2/B3 remain unchanged.", "",
        "## Sensitivity and reproducibility", "", table(["Dataset", "Sensitivity", "Changed actions", "N"], [[r["dataset"],r["policy"],r["changed"],r["n"]] for r in v["sensitivity"]]), "",
        "![Fixed sensitivity](policy-sensitivity.png)", "",
        f"Six fixed policies produced {v['decision_count']} decisions for {v['candidate_count']} occurrences. Replay content identical: {v['replay_identical']}. Runtime {v['runtime_seconds']:.3f} seconds: {v['runtime_definition']}. Exact action transitions are in sensitivity.csv. Source metadata and dependency versions are in the experiment bundle. Cutoffs were not optimized after observing results.", "",
        "## Calibration and human dependency", "", "**NOT_ELIGIBLE_UNAPPROVED_LABELS**. All 120 latest labels remain AGENT / PENDING_HUMAN_APPROVAL, with null human-final labels: 0 VALID, 27 INVALID, 93 INDETERMINATE. No real calibrator exists. Future dataset-specific isotonic fitting requires the existing source-bound confirmed human ledger, disjoint calibration/evaluation populations and >=5 scored VALID and INVALID cases in each partition. INDETERMINATE is excluded, never recoded. Synthetic fixtures only exercise this interface; they do not establish real eligibility or population guarantees. Research fingerprints bind content, not human identity; production authentication stays disabled.", "",
        "## Representative explainable cases", "", table(["Dataset", "Selection", "Source ordinal", "Action", "Recorded B2 reason"], [[r["dataset"],r["selection"],r["source_ordinal"],r["action"],r["recorded_B2_reason"]] for r in v["cases"]]), "",
        "Cases are deterministic first occurrences satisfying each descriptive selection category, not outcome-balanced exemplars or ground truth. cases.csv includes exact payloads, source identities, normalized/raw evidence, structural reasons and explanations. Multiple categories can show the same occurrence.", "",
        "## Limitations and pending decisions", "", "The selected cohort is nonrepresentative. Rank references describe the fixed historical candidate population and change with population membership. Unknown original target mappings, physical meanings/units and cross-field rules remain unresolved. Rare/out-of-range/duplicate records are not automatically invalid. Historical TRAIN/TEST exact-value overlap persists; no REAL TEST values were fitted or used for selection. One supervisor review cannot establish inter-rater agreement. Scientific acceptance, reviewed labels, calibration adequacy, official thresholds and final claims remain pending in the single decision-ledger.csv. Dataset contribution/coverage belongs to Phase 5, which is not started.", "",
        "## Reproduction", "", "Run the commands in docs/phase4-m4-m5-methods.md with fresh versioned output paths. The sealed shadow reader replays decisions and normalization from the frozen M2 bundle. Report rendering uses only saved evidence; its deterministic content can be regenerated without fitting or provider calls. Final verification logs are saved separately under ../final-verification-v1. Prior passing Phase-3 full-suite evidence is retained in the inherited Phase-3 closeout.", ""]
    write_text(output/"report.md", "\n".join(text))
    summary = """# Manuscript integration draft: exploratory Phase-4 methods and results

We retained the three frozen M2 evidence families and mapped local/global scores
to dataset-specific empirical mid-distribution ranks of the fixed historical
candidate population. Raw evidence and structural findings were preserved.
Dependence was summarized with Spearman ranks and concern-set overlap; fusion
used a predeclared union predicate rather than independent-evidence likelihoods.
Six fixed shadow policies evaluated 601 occurrences across three datasets.
At the main q=0.9 combined policy, structural rejection/review/provisional-pass
counts were 5/25/170 for Abalone19, 6/33/162 for Ecoli4, and 64/17/119 for
page-blocks0; no realized abstention occurred because the sole unavailable-feature
case already required structural rejection. Local/global rank correlations were
0.908, 0.488 and 0.621 respectively. Lowering q to 0.8 changed 75 actions;
raising it to 0.95 changed 37. Replay reproduced all decision/evidence content.
These are exploratory behavior comparisons, not verified correctness or risk
control. PROVISIONAL_PASS is not human-valid ground truth. Calibration remains
ineligible pending personal supervisor review and explicit ledger confirmation.
Selected-cohort bias, unresolved semantics and historical TRAIN/TEST overlap
limit interpretation; novelty, calibrated performance and superiority are not claimed.
"""
    write_text(output/"manuscript-summary.md", summary)
    colors = ["#A93226", "#D68910", "#2471A3", "#707B7C"]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.7), sharey=True)
    labels = ["Structure", "Local", "Global", "Union .90", "Union .80", "Union .95"]
    for ax, d in zip(axes, v["datasets"], strict=True):
        bottom = np.zeros(len(v["policies"]))
        for action, color in zip(ACTIONS, colors, strict=True):
            counts = np.array([next(r[action] for r in v["results"] if r["dataset"] == d and r["policy"] == p) for p in v["policies"]])
            ax.bar(np.arange(len(counts)), counts, bottom=bottom, label=action.replace("_", " ").title(), color=color)
            bottom += counts
        ax.set_title(d); ax.set_xticks(range(len(labels)), labels, rotation=45, ha="right")
        ax.set_ylim(0, 215); ax.set_ylabel("Historical occurrences")
    axes[0].legend(loc="upper left", bbox_to_anchor=(0, 1.38), ncol=4, fontsize=9)
    fig.suptitle("Exploratory shadow actions \u2014 provisional pass is not human validity", y=1.08)
    save(fig, output, "shadow-decisions")
    raw = read_shadow(experiment)
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), sharex=True, sharey=True)
    for ax, d in zip(axes, v["datasets"], strict=True):
        group = [r for r in raw["harmonized"]["vectors"] if r["dataset_id"] == d]
        xy = [(r["normalized"]["local_support"]["percentile"],r["normalized"]["cross_feature"]["percentile"]) for r in group]
        xy = [(x,y) for x,y in xy if x is not None and y is not None]
        ax.scatter(*zip(*xy, strict=True), s=14, alpha=.55, color="#2471A3")
        ax.axvline(.9, color="#A93226", linestyle="--"); ax.axhline(.9, color="#A93226", linestyle="--")
        ax.set_title(f"{d}: rho={v['dependence'][d]['spearman']:.3f}; n={len(xy)}")
        ax.set_xlim(0,1); ax.set_ylim(0,1); ax.set_xlabel("Local descriptive percentile")
    axes[0].set_ylabel("Global descriptive percentile")
    fig.suptitle("Dependent descriptive evidence; dashed cutoffs are exploratory heuristics")
    save(fig, output, "evidence-dependence")
    fig, axes = plt.subplots(1,3,figsize=(12,4),sharey=True)
    for ax,d in zip(axes,v["datasets"],strict=True):
        subset = [r for r in ctl if r["dataset"] == d]
        ax.bar([r["control"].upper() for r in subset], [r["provisional_pass_symmetric_difference"] for r in subset], color="#707B7C")
        ax.set_title(d); ax.set_xlabel("Recorded control")
    axes[0].set_ylabel("Symmetric difference (occurrences)")
    fig.suptitle("Combined q=.90 provisional passes versus recorded acceptance \u2014 not error counts")
    save(fig,output,"control-comparison")
    fig,ax=plt.subplots(figsize=(7,4))
    for d in v["datasets"]:
        ys=[next(r["REVIEW_REQUIRED"] for r in v["results"] if r["dataset"]==d and r["policy"]==p) for p in ("combined-review-q80","combined-review","combined-review-q95")]
        ax.plot([.8,.9,.95],ys,marker="o",label=d)
    ax.set_xticks([.8,.9,.95]); ax.set_xlabel("Predeclared descriptive percentile cutoff")
    ax.set_ylabel("Review required (occurrences)"); ax.legend()
    ax.set_title("Limited sensitivity \u2014 no optimized threshold selected")
    save(fig,output,"policy-sensitivity")
    seal_bundle(output)
    return v


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--experiment",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--replay",type=Path)
    args=parser.parse_args()
    result=render(Path.cwd(),args.experiment,args.output,args.replay)
    print(json.dumps({"report_fingerprint":result["fingerprint"],"decisions":result["decision_count"]}))
