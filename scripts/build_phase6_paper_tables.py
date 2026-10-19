import json
import re
import shutil
from pathlib import Path

from rcqasyn.phase2.common import digest, read_bundle

root = Path.cwd()
paper = root / "paper/rcqasyn-final-draft"
for name in ["sections", "tables", "figures", "notes"]:
    (paper / name).mkdir(parents=True, exist_ok=True)
v = read_bundle(root / "artifacts/reports/phase6/report-v2")
trace = {}


def table(name, caption, headers, rows, source):
    def esc(s):
        return str(s).replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")

    text = r"\begin{longtable}{" + "l" + "r" * (len(headers) - 1) + "}\n"
    text += r"\caption{" + caption + r"}\label{tab:" + name + r"}\\" + "\n\\toprule\n"
    head = " & ".join(esc(h) for h in headers) + r" \\" + "\n\\midrule\n"
    text += head + "\\endfirsthead\n\\toprule\n" + head + "\\endhead\n"
    for row in rows:
        text += (
            " & ".join(esc(f"{x:.4f}" if isinstance(x, float) else x) for x in row) + r" \\" + "\n"
        )
    text += "\\bottomrule\n\\end{longtable}\n"
    (paper / "tables" / (name + ".tex")).write_text(text, encoding="utf-8")
    trace[name] = {
        "source": source,
        "headers": headers,
        "rows": rows,
        "canonical_rows_fingerprint": digest(rows),
    }


table(
    "datasets",
    "Frozen task datasets and literal positive counts.",
    ["Dataset", "Rows", "TRAIN", "TEST", "TRAIN+", "TEST+", "Candidates"],
    [
        [
            r["dataset"],
            r["rows"],
            r["train"],
            r["test"],
            r["train_classes"]["positive"],
            r["test_classes"]["positive"],
            r["candidates"],
        ]
        for r in v["datasets"]
    ],
    "report.datasets; original source specifications",
)
table(
    "controls",
    "Recorded control acceptance and separately named complete structure-compatible utility subsets. Acceptance is not verified validity.",
    ["Dataset / control", "Accepted", "Candidates", "Utility subset", "Pass difference"],
    [
        [
            r["dataset"] + " / " + r["control"],
            r["original_accepted"],
            r["original_n"],
            r["utility_structural_complete_n"],
            r["symmetric_difference_from_combined_pass"],
        ]
        for r in v["controls"]
    ],
    "report.controls; Phase4 combined-review.controls",
)
table(
    "evidence",
    "Baseline local/global dependence and concern disagreement at descriptive cutoff .90.",
    ["Dataset", "Paired", "Spearman", "Union", "Intersection", "Disagree"],
    [
        [
            d,
            r["paired_n"],
            r["spearman"],
            r["concern_union"],
            r["concern_intersection"],
            r["concern_disagreement"],
        ]
        for d, r in v["dependence"].items()
    ],
    "report.dependence; Phase4.dependence",
)
table(
    "shadow",
    "Frozen exploratory policies. R: structural reject; V: review; P: provisional pass; A: abstain.",
    ["Dataset / policy", "R", "V", "P", "A"],
    [
        [
            r["dataset"] + " / " + r["policy"],
            r["REJECT_STRUCTURAL"],
            r["REVIEW_REQUIRED"],
            r["PROVISIONAL_PASS"],
            r["ABSTAIN"],
        ]
        for r in v["shadow_policies"]
    ],
    "report.shadow_policies",
)
table(
    "repair",
    "Approved integer-only repair outcomes; denominator is original structural rejects.",
    ["Dataset", "Rejects", "Eligible", "Applied", "Failed", "Ineligible"],
    [
        [
            d,
            *(
                r[k]
                for k in [
                    "structurally_invalid",
                    "repair_eligible",
                    "repair_successful",
                    "repair_failed",
                    "repair_ineligible",
                ]
            ),
        ]
        for d, r in v["repair_summary"].items()
    ],
    "report.repair_summary",
)
table(
    "coverage",
    "Matched middle-budget construction. C: distinct-feature TRAIN coverage; D: exact duplicate rate; N: near-duplicate rate. O: original pool; R: repair-augmented pool.",
    ["Dataset / strategy / pool", "n", "Derived", "C", "D", "N"],
    [
        [
            r["dataset"]
            + " / "
            + r["strategy"]
            + " / "
            + ("O" if r["condition"] == "original" else "R"),
            r["selected"],
            r["derived_selected"],
            r["unique_train_coverage"],
            r["exact_duplicate_rate"],
            r["near_duplicate_rate"],
        ]
        for r in v["coverage"]
    ],
    "report.coverage; core-v1.constructions",
)
utility = [
    r for r in v["utility"] if r["regime"] == "TRTR" or r["method"].startswith("quality-coverage")
]
table(
    "utility",
    "Fixed TEST task utility. L/F: logistic/random forest. QO/QR: quality-coverage original/repair pool. H: hybrid minority augmentation.",
    ["Dataset / source / regime / model", "F1", "AP", "BA", "MCC"],
    [
        [
            r["dataset_id"]
            + " / "
            + (
                "Real"
                if r["method"] == "REAL_TRAIN"
                else "QO"
                if r["method"].endswith(":original")
                else "QR"
            )
            + " / "
            + ("H" if r["regime"] == "HYBRID_MINORITY" else r["regime"])
            + " / "
            + ("L" if r["classifier"] == "logistic_regression" else "F"),
            *(
                r["evaluation_result"].get(k, "NA")
                for k in ["f1", "average_precision", "balanced_accuracy", "mcc"]
            ),
        ]
        for r in utility
    ],
    "report.utility; complete 138-row utility.csv",
)
table(
    "phase5",
    "Original Phase-5 primary budget matrix. C: distinct-feature TRAIN coverage.",
    ["Dataset / strategy", "Budget", "C", "Exact", "Near"],
    [
        [
            r["dataset_id"] + " / " + r["strategy"],
            r["budget"],
            r["metrics"]["unique_train_feature_coverage"],
            r["metrics"]["exact_duplicate_rate"],
            r["metrics"]["near_duplicate_rate"],
        ]
        for r in v["phase5_runs"]
        if r["control_intersection"] is None and r["policy"] == "combined-review"
    ],
    "report.phase5_runs; Phase5.study-v1.manifest.runs",
)
for name in ["repair-outcomes.png", "coverage-comparison.png", "task-utility.png"]:
    shutil.copyfile(root / "artifacts/reports/phase6/report-v2" / name, paper / "figures" / name)
keys = [
    "xu2019ctgan",
    "kotelnikov2023tabddpm",
    "alaa2022faithful",
    "guo2017calibration",
    "borisov2023great",
    "stoian2024realistic",
    "zheng2023judging",
    "long2024survey",
]
entries = re.split(r"\n(?=@)", (root / "paper/references.bib").read_text(encoding="utf-8").strip())
selected = [e for e in entries if re.match(r"@\w+\{([^,]+)", e).group(1) in keys]
assert len(selected) == 8
(paper / "references.bib").write_text(
    ("\n\n".join(selected).rstrip() + "\n").replace("Mihaela C. Stoian", "Mihaela Stoian"), encoding="utf-8"
)
urls = {
    re.match(r"@\w+\{([^,]+)", e).group(1): re.search(r"url\s*=\s*\{([^}]+)", e).group(1)
    for e in selected
}
(paper / "notes/references-verified.json").write_text(
    json.dumps(
        {
            "verified_on": "2026-10-19",
            "method": "Primary publisher/proceedings records inspected; primary arXiv preprint record for GReaT; no unverified publication status asserted",
            "references": urls,
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
(paper / "notes/table-evidence.json").write_text(
    json.dumps({"report_fingerprint": v["fingerprint"], "tables": trace}, indent=2) + "\n",
    encoding="utf-8",
)
print("8 source-generated tables, 8 verified references")
