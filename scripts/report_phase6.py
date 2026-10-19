"""Consolidate recorded six-phase evidence; never fit, select or evaluate a model."""

from __future__ import annotations

import argparse
import io
import json
from collections import Counter
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from rcqasyn.phase2.common import csv_text, envelope, read_bundle
from rcqasyn.phase6.utility import utility_csv_rows
from rcqasyn.storage.artifacts import create_run_dir, write_json, write_text
from rcqasyn.storage.ownership import seal_bundle, write_scope


def table(headers: list[str], rows: list[list[Any]]) -> str:
    return (
        "| "
        + " | ".join(headers)
        + " |\n|"
        + "|".join("---" for _ in headers)
        + "|\n"
        + "\n".join("| " + " | ".join(str(v) for v in row) + " |" for row in rows)
        + "\n"
    )


def consolidate(root: Path, core: Path, utility: Path) -> dict[str, Any]:
    manifest = read_bundle(core / "manifest")
    repairs = read_bundle(core / "repairs")
    u = read_bundle(utility)
    if u["core_manifest_fingerprint"] != manifest["fingerprint"]:
        raise ValueError("report source mismatch")
    p3 = read_bundle(root / "artifacts/reports/phase3/m2-report-v2")
    p4 = read_bundle(root / "artifacts/reports/phase4/shadow-v1")
    p5 = read_bundle(root / "artifacts/reports/phase5/study-v1/manifest")
    constructions = [
        read_bundle(core / "constructions" / f"{r['dataset_id']}-{r['strategy']}-{r['condition']}")
        for r in manifest["constructions"]
    ]
    datasets = []
    controls = []
    policies = []
    coverage = []
    registry = []
    for pop in u["populations"]:
        d = pop["dataset_id"]
        s = repairs["summary"][d]
        datasets.append(
            {
                "dataset": d,
                "rows": len(pop["train_indices"]) + len(pop["test_indices"]),
                "train": len(pop["train_indices"]),
                "test": len(pop["test_indices"]),
                "train_classes": pop["train_class_counts"],
                "test_classes": pop["test_class_counts"],
                "candidates": s["occurrences"],
                "split_fingerprint": pop["split_fingerprint"],
                "train_fingerprint": pop["train_fingerprint"],
                "test_fingerprint": pop["test_fingerprint"],
            }
        )
        for b, c in p4["summary"]["combined-review"][d]["controls"].items():
            filtered = next(
                r["synthetic_input_n"]
                for r in u["results"]
                if r["dataset_id"] == d and r["method"] == b.upper() + "-structural-complete"
            )
            controls.append(
                {
                    "dataset": d,
                    "control": b.upper(),
                    "original_accepted": c["recorded_accepted"],
                    "original_n": s["occurrences"],
                    "utility_structural_complete_n": filtered,
                    "symmetric_difference_from_combined_pass": c[
                        "provisional_pass_symmetric_difference"
                    ],
                }
            )
            registry.append(
                {
                    "phase": 1,
                    "dataset": d,
                    "method": b.upper(),
                    "population": "original historical occurrences",
                    "status": "RECORDED_FROZEN",
                    "source_fingerprint": p4["fingerprint"],
                }
            )
        for policy, bydata in p4["summary"].items():
            policies.append({"dataset": d, "policy": policy, **bydata[d]["actions"]})
            registry.append(
                {
                    "phase": 4,
                    "dataset": d,
                    "method": policy,
                    "population": "original historical occurrences",
                    "status": "UNCALIBRATED_SHADOW",
                    "source_fingerprint": p4["fingerprint"],
                }
            )
        registry.append(
            {
                "phase": 6,
                "dataset": d,
                "method": repairs["policy"]["version"],
                "population": "all authoritative occurrences",
                "status": "STRUCTURAL_REPAIR_NOT_HUMAN_VALIDITY",
                "source_fingerprint": repairs["fingerprint"],
            }
        )
    for r in p3["sensitivity"]:
        registry.append(
            {
                "phase": 3,
                "dataset": r["dataset"],
                "method": r["configuration"],
                "population": "original historical occurrences x three evidence families",
                "status": "DESCRIPTIVE_EVIDENCE",
                "source_fingerprint": p3["fingerprint"],
            }
        )
    for r in p5["runs"]:
        registry.append(
            {
                "phase": 5,
                "dataset": r["dataset_id"],
                "method": r["name"],
                "population": f"budget {r['budget']}",
                "status": "EXPLORATORY_DATASET_AUDIT_" + r["audit_status"],
                "source_fingerprint": r["fingerprint"],
            }
        )
    for r in constructions:
        m = r["metrics"]
        coverage.append(
            {
                "dataset": r["dataset_id"],
                "strategy": r["strategy"],
                "condition": r["condition"],
                "budget": r["budget_requested"],
                "selected": m["selected_n"],
                "eligible": r["eligible_n"],
                "derived_selected": r["derived_selected"],
                "unique_train_coverage": m["unique_train_feature_coverage"],
                "class_balanced_region_coverage": m["class_balanced_region_coverage"],
                "exact_duplicate_rate": m["exact_duplicate_rate"],
                "near_duplicate_rate": m["near_duplicate_rate"],
                "pairwise_mean": m["pairwise_separation"]["mean"],
                "same_label_minority_coverage": m["class_coverage"][m["minority_literal_label"]][
                    "coverage_by_same_declared_class"
                ],
                "fingerprint": r["fingerprint"],
            }
        )
        registry.append(
            {
                "phase": 6,
                "dataset": r["dataset_id"],
                "method": r["strategy"] + ":" + r["condition"],
                "population": f"budget {r['budget_requested']}",
                "status": "PROVISIONAL_CONSTRUCTION_PARENT_EXCLUSIVE",
                "source_fingerprint": r["fingerprint"],
            }
        )
    for r in u["results"]:
        registry.append(
            {
                "phase": 6,
                "dataset": r["dataset_id"],
                "method": r["method"] + ":" + r["regime"] + ":" + r["classifier"],
                "population": "frozen historically reused REAL TEST; training as regime specifies",
                "status": r["evaluation_result"]["status"],
                "source_fingerprint": r["source_fingerprint"],
            }
        )
    attempted = [r for r in repairs["records"] if r["post"]]
    changes = [e["absolute_change"] for r in attempted for e in r["proposal"]["edits"]]
    cases = sorted(
        attempted,
        key=lambda r: max(abs(v) for v in r["percentile_changes"].values() if v is not None),
        reverse=True,
    )[:5]
    cases = [
        {
            "parent": r["proposal"]["parent_occurrence_id"],
            "derived": r["proposal"]["derived_occurrence_id"],
            "edits": r["proposal"]["edits"],
            "percentile_changes": r["percentile_changes"],
            "new_action": r["post"]["decision"]["action"],
            "source": r["proposal"]["source_provenance"],
        }
        for r in cases
    ]
    decisions = [
        {"question": q, "status": "HUMAN_DECISION_PENDING", "evidence": e, "options": o}
        for q, e, o in [
            (
                "Personal review of all 120 labels",
                "0/27/93 agent VALID/INVALID/INDETERMINATE; no human-final approvals",
                "Review/correct every label and explicitly confirm reviewed ledger fingerprint",
            ),
            (
                "Original target mappings and physical/cross-field semantics",
                "Dataset specifications distinguish literal source declarations from missing domain meaning",
                "Supply authoritative semantics, or retain unresolved limitations",
            ),
            (
                "Official calibration eligibility",
                "Actual cohort unapproved; no validity-positive reference class",
                "Only reconsider after approved independent labels with both classes",
            ),
            (
                "Scientific acceptance and final claims",
                "Six engineering phases and exploratory evidence; single historical split/seed with prior TEST use",
                "Supervisor accepts or revises interpretation; no automatic freeze",
            ),
            (
                "Authors, contributions and institutional declarations",
                "Placeholders and explicit AI assistance statement in draft",
                "Human authors supply accurate affiliations, funding, conflicts and venue-policy wording",
            ),
        ]
    ]
    return envelope(
        "m9-consolidated-report-v1",
        {
            "sources": {
                "core": manifest["fingerprint"],
                "repair": repairs["fingerprint"],
                "utility": u["fingerprint"],
                "phase3": p3["fingerprint"],
                "phase4": p4["fingerprint"],
                "phase5": p5["fingerprint"],
            },
            "datasets": datasets,
            "controls": controls,
            "m2_sensitivity": p3["sensitivity"],
            "dependence": p4["dependence"],
            "shadow_policies": policies,
            "phase5_runs": p5["runs"],
            "repair_summary": repairs["summary"],
            "coverage": coverage,
            "utility": u["results"],
            "utility_status_counts": u["status_counts"],
            "edit_summary": {
                "fields": len(changes),
                "records_by_edited_fields": dict(
                    Counter(r["proposal"]["edited_fields"] for r in attempted)
                ),
                "minimum": min(changes),
                "maximum": max(changes),
                "mean": float(np.mean(changes)),
                "median": float(np.median(changes)),
            },
            "cases": cases,
            "registry": registry,
            "registry_count": len(registry),
            "decision_ledger": decisions,
            "repair_runtime_seconds": repairs["runtime_seconds"],
            "utility_runtime_seconds": u["runtime_seconds"],
            "human_label_review": "PENDING_SUPERVISOR_REVIEW",
            "scientific_freeze_approved": False,
            "calibration_status": "NOT_ELIGIBLE_UNAPPROVED_LABELS",
        },
    )


def markdown(v: dict[str, Any]) -> str:
    v = json.loads(json.dumps(v, sort_keys=True))
    text = "# RC-QASyn: consolidated six-phase exploratory results\n\nENGINEERING COMPLETE; SCIENTIFIC ACCEPTANCE PENDING. All human-final labels remain pending.\n\n"
    text += "## Dataset and evaluation populations\n\n" + table(
        [
            "Dataset",
            "Rows",
            "TRAIN",
            "TEST",
            "TRAIN class counts",
            "TEST class counts",
            "Candidates",
        ],
        [
            [
                r[k]
                for k in (
                    "dataset",
                    "rows",
                    "train",
                    "test",
                    "train_classes",
                    "test_classes",
                    "candidates",
                )
            ]
            for r in v["datasets"]
        ],
    )
    text += "\n## Frozen controls and separately filtered utility populations\n\n" + table(
        list(v["controls"][0]), [list(r.values()) for r in v["controls"]]
    )
    text += "\nHistorical unfiltered task utility is preserved in Phase-1 artifacts. It is not endorsed as a complete-record comparison: absent class can become the string 'nan' in the historical scorer. The new controls explicitly intersect recorded acceptance with authoritative structure compatibility and complete payloads. B1/B2/B3 themselves are unchanged.\n\n## M2 and M4\n\nFive M2 configurations each emit 1,803 evidence records. No evidence family establishes human validity. Full sensitivity rows are in m2.csv. Local/global dependence is measured, not assumed independent.\n\n"
    text += table(
        ["Dataset", "Paired", "Spearman", "Tail disagreement"],
        [
            [d, r["paired_n"], f"{r['spearman']:.6f}", r["concern_disagreement"]]
            for d, r in v["dependence"].items()
        ],
    )
    text += "\n" + table(
        list(v["shadow_policies"][0]), [list(r.values()) for r in v["shadow_policies"]]
    )
    text += "\n## M6 repair audit\n\n" + table(
        [
            "Dataset",
            "Original",
            "Structural rejects",
            "Eligible",
            "Applied",
            "Ineligible",
            "Post actions",
            "Violation categories (overlap)",
        ],
        [
            [
                d,
                s["occurrences"],
                s["structurally_invalid"],
                s["repair_eligible"],
                s["repair_successful"],
                s["repair_ineligible"],
                s["post_actions"],
                s["violation_category_records"],
            ]
            for d, s in v["repair_summary"].items()
        ],
    )
    text += "\n75 structural rejects comprise 15 records missing class, one missing required features, and 64 with fractional integer fields; categories overlap. No invalid primitive or unsupported nominal value appears in this historical audit. There are 26 records with multiple field violations. Of the 64 integer-defect records, five also lack class and five require more than three edits; neither group is repaired.\n\n"
    text += f"Edit statistics: {v['edit_summary']}. All 54 attempts become structurally compatible; 49 pass the frozen shadow policy provisionally and five require review. The 21 ineligible original records remain invalid. This is not semantic validity or human approval. Repair runtime: {v['repair_runtime_seconds']:.3f} s (excludes context loading and construction).\n\n"
    text += "## Fixed-budget construction comparison\n\nM7 objectives, radius .05, near tolerance .01 and quota .5 remain frozen. Budgets are 56/70/49. Original results reproduce their Phase-5 counterparts exactly. Every selected set enforces source-parent exclusivity. Larger candidate pools do not imply larger compared datasets.\n\n"
    text += table(
        [
            "Dataset",
            "Strategy",
            "Condition",
            "Budget",
            "Pool",
            "Derived",
            "Unique TRAIN coverage",
            "Exact duplicates",
            "Near duplicates",
        ],
        [
            [
                r["dataset"],
                r["strategy"],
                r["condition"],
                r["budget"],
                r["eligible"],
                r["derived_selected"],
                *(
                    f"{r[k]:.6f}"
                    for k in (
                        "unique_train_coverage",
                        "exact_duplicate_rate",
                        "near_duplicate_rate",
                    )
                ),
            ]
            for r in v["coverage"]
        ],
    )
    text += "\n## Task-class utility\n\n138 fixed comparisons: 114 ok and 24 explicitly unavailable. The complete utility.csv includes F1, AP (pr_auc alias), balanced accuracy, MCC and AUROC, source identities and unavailable reasons. No scores are human-validity metrics. TRTR trains real; TSTR trains synthetic only; HYBRID_MINORITY augments real TRAIN with synthetic positive-literal records. Single-class TSTR and empty-minority augmentation are unavailable.\n\n"
    rows = [
        r
        for r in v["utility"]
        if r["regime"] == "TRTR"
        or (r["method"].startswith("quality-coverage") and r["classifier"] == "logistic_regression")
    ]
    text += table(
        ["Dataset", "Method", "Regime", "Classifier", "F1", "AP", "BA", "MCC", "Status"],
        [
            [
                r["dataset_id"],
                r["method"],
                r["regime"],
                r["classifier"],
                *(
                    f"{r['evaluation_result'][k]:.6f}"
                    if r["evaluation_result"].get(k) is not None
                    else "unavailable"
                    for k in ("f1", "average_precision", "balanced_accuracy", "mcc")
                ),
                r["evaluation_result"]["status"],
            ]
            for r in rows
        ],
    )
    text += "\nThe quality-coverage page-blocks0 logistic TSTR F1 decreases after repair-pool expansion while AP increases slightly. Hybrid F1 is unchanged for that comparison. These mixed outcomes do not support a uniform utility-improvement claim. The fixed TEST set was already evaluated historically and has documented exact-value TRAIN/TEST overlap. No TEST result selected a policy, repair rule, budget, classifier or seed. No independent inner TRAIN validation is claimed because frozen generation/evidence used full TRAIN. Replays are not repetitions; no confidence interval or significance claim is made.\n\n"
    text += f"Utility runtime: {v['utility_runtime_seconds']:.3f} s including context loading and all 138 rows. registry.csv contains {v['registry_count']} experiment entries with shared exact source/split/model bindings in artifact.json and upstream sealed artifacts.\n\n## Representative large-shift cases\n\n"
    for r in v["cases"]:
        text += f"- Parent `{r['parent']}`; derived `{r['derived']}`; edits {r['edits']}; percentile changes {r['percentile_changes']}; action {r['new_action']}; source {r['source']}.\n"
    text += "\n## Deferred decisions\n\n" + table(
        ["Question", "Status", "Evidence", "Options"],
        [
            [r[k] for k in ("question", "status", "evidence", "options")]
            for r in v["decision_ledger"]
        ],
    )
    text += "\n## Reproduction and interpretation\n\nSee docs/phase6-m6-m9-methods.md for exact commands/formulas. Core and utility replays match substantive fingerprints. Runtime-bearing envelopes intentionally differ; no fabricated identical wall time. Every original occurrence is preserved, derived records bind authoritative parents, and no provider is called. Stage-6 structural correction, percentile concern, provisional admission, TRAIN geometry and task utility remain distinct quantities. Calibration and official B2/B3-versus-human analysis remain inactive. Final QA and historical-byte verification are recorded separately in the closeout bundle.\n"
    return text


def figures(v: dict[str, Any]) -> dict[str, bytes]:
    plt.rcParams.update({"font.size": 10, "svg.hashsalt": "rcqasyn-phase6-v1", "figure.dpi": 130})
    out = {}
    labels = [r["dataset"] for r in v["datasets"]]
    fig, ax = plt.subplots(figsize=(7.5, 3.5))
    x = np.arange(3)
    for j, (key, name) in enumerate(
        [
            ("structurally_invalid", "Original structural rejects"),
            ("repair_successful", "Structurally corrected"),
            ("repair_ineligible", "Unrepaired rejects"),
        ]
    ):
        ax.bar(
            x + (j - 1) * 0.24,
            [v["repair_summary"][d][key] for d in labels],
            width=0.24,
            label=name,
        )
    ax.set(
        xticks=x, xticklabels=labels, ylabel="Occurrences", title="Approved bounded repair outcomes"
    )
    ax.legend(fontsize=8)
    fig.tight_layout()
    out["repair-outcomes.png"] = _png(fig)
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.5), sharey=True)
    for ax, d in zip(axes, labels, strict=True):
        rows = [r for r in v["coverage"] if r["dataset"] == d]
        strategies = list(dict.fromkeys(r["strategy"] for r in rows))
        for condition, offset in [("original", -0.17), ("repair-augmented", 0.17)]:
            ax.bar(
                np.arange(4) + offset,
                [
                    next(
                        r["unique_train_coverage"]
                        for r in rows
                        if r["strategy"] == s and r["condition"] == condition
                    )
                    for s in strategies
                ],
                width=0.34,
                label=condition,
            )
        ax.set(
            title=d,
            xticks=np.arange(4),
            xticklabels=["Order", "Diversity", "Coverage", "Quality"],
            ylim=(0, 1.05),
        )
        ax.tick_params(axis="x", rotation=25)
    axes[0].set_ylabel("Unique TRAIN feature coverage (radius .05)")
    axes[-1].legend(fontsize=7)
    fig.tight_layout()
    out["coverage-comparison.png"] = _png(fig)
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.5))
    for ax, metric, title in zip(
        axes, ["f1", "average_precision"], ["Minority task F1", "Average precision"], strict=True
    ):
        for method, marker in [
            ("REAL_TRAIN", "o"),
            ("quality-coverage:original", "s"),
            ("quality-coverage:repair-augmented", "^"),
        ]:
            regime = "TRTR" if method == "REAL_TRAIN" else "TSTR"
            vals = [
                next(
                    r["evaluation_result"][metric]
                    for r in v["utility"]
                    if r["dataset_id"] == d
                    and r["method"] == method
                    and r["regime"] == regime
                    and r["classifier"] == "logistic_regression"
                )
                for d in labels
            ]
            ax.plot(labels, vals, marker=marker, label=regime + ":" + method)
        ax.set(title=title, ylim=(-0.03, 1.05))
        ax.tick_params(axis="x", rotation=15)
    axes[1].legend(fontsize=6)
    fig.suptitle("Fixed logistic-regression comparisons on historically reused TEST")
    fig.tight_layout()
    out["task-utility.png"] = _png(fig)
    return out


def _png(fig: Any) -> bytes:
    stream = io.BytesIO()
    fig.savefig(stream, format="png", metadata={"Software": "RC-QASyn Phase6 deterministic report"})
    plt.close(fig)
    return stream.getvalue()


def publish(root: Path, core: Path, utility: Path, output: Path) -> dict[str, Any]:
    v = consolidate(root, core, utility)
    directory = create_run_dir(output.parent, output.name)
    write_json(directory / "artifact.json", v)
    write_text(directory / "report.md", markdown(v))
    for name, rows in [
        ("datasets", v["datasets"]),
        ("controls", v["controls"]),
        ("shadow", v["shadow_policies"]),
        ("m2", v["m2_sensitivity"]),
        ("coverage", v["coverage"]),
        ("registry", v["registry"]),
        ("utility", utility_csv_rows(v["utility"])),
    ]:
        write_text(directory / (name + ".csv"), csv_text(rows))
    for name, payload in figures(v).items():
        with write_scope(directory / name), (directory / name).open("xb") as stream:
            stream.write(payload)
    seal_bundle(directory)
    return v


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--utility", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    value = publish(root, args.core, args.utility, args.output)
    print(value["fingerprint"], value["registry_count"])


if __name__ == "__main__":
    main()
