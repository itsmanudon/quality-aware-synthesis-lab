"""Render saved empirical evidence; this program never fits a model."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from rcqasyn.empirical.study import file_hash, write_json
from rcqasyn.phase2.common import digest


def read(path: Path) -> Any:
    return json.loads(path.read_text("utf-8-sig"))


def tex(value: Any) -> str:
    return str(value).replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")


def number(value: Any) -> str:
    return "--" if value is None or pd.isna(value) else f"{value:.3f}"


def method_label(method: str) -> str:
    return {"REAL_TRAIN": "Real", "CLASS_WEIGHTED_LR": "Weighted LR",
            "RandomOverSampler+b": "ROS+b", "SMOTE+b": "SMOTE+b", "SMOTENC+b": "SMOTENC+b",
            "schema/random": "Schema random", "combined/random": "Admitted random",
            "combined/quality-coverage": "Curated Q"}.get(method, method)


def main(root: Path, run: Path, output: Path, paper: Path) -> None:
    if output.exists():
        raise FileExistsError("fresh report directory required")
    output.mkdir(parents=True)
    (paper/"tables").mkdir(parents=True, exist_ok=True)
    (paper/"figures").mkdir(exist_ok=True)
    (paper/"notes").mkdir(exist_ok=True)
    results = read(run/"results.json")
    constructions = read(run/"constructions.json")
    intervals = read(run/"bootstrap.json")
    differences = read(run/"paired-differences.json")
    summary = read(run/"split-summary.json")
    manifest = read(run/"manifest.json")
    population = read(run/"populations.json")
    coverage_path = root/"artifacts/reports/phase6/report-v2/coverage.csv"
    old_coverage = pd.read_csv(coverage_path).to_dict(orient="records")
    ledger: dict[str, Any] = {}

    def table(name: str, caption: str, headers: list[str], rows: list[list[str]], sources: Any) -> None:
        content = (r"\begin{longtable}{"+"l"+"r"*(len(headers)-1)+"}\n"
                   +r"\caption{"+caption+r"}\label{tab:"+name+r"}\\"+"\n"
                   +r"\toprule"+"\n"+" & ".join(headers)+r" \\"+"\n"
                   +r"\midrule\endfirsthead"+"\n"+r"\toprule"+"\n"
                   +" & ".join(headers)+r" \\"+"\n"+r"\midrule\endhead"+"\n"
                   +"\n".join(" & ".join(r)+r" \\" for r in rows)+"\n"
                   +r"\bottomrule\end{longtable}"+"\n")
        (paper/f"tables/{name}.tex").write_text(content, encoding="utf-8")
        ledger[name] = {"headers": headers, "rendered_cells": rows, "sources": sources,
                        "table_sha256": file_hash(paper/f"tables/{name}.tex")}

    consolidated = []
    for c in constructions:
        if c["track"] != "A":
            continue
        utility = next(r for r in results if r["track"] == "A" and r["dataset_id"] == c["dataset_id"]
                       and r["method"] == c["method"] and r["classifier"] == "logistic_regression"
                       and r["regime"] == "TSTR")
        consolidated.append({**c, "f1_tstr_lr": utility.get("f1"),
                             "ap_tstr_lr": utility.get("average_precision"),
                             "utility_status": utility["status"],
                             "source": "constructions.json + results.json", "source_row_hash": digest(c)})
    for old in old_coverage:
        method = old["strategy"]+":"+old["condition"]
        utility = next(r for r in results if r["track"] == "A" and r["dataset_id"] == old["dataset"]
                       and r["method"] == method and r["classifier"] == "logistic_regression"
                       and r["regime"] == "TSTR")
        consolidated.append({"dataset_id": old["dataset"], "method": method,
                             "eligible_n": old["eligible"], "budget": old["budget"],
                             "selected_n": old["selected"], "budget_achieved": old["selected"],
                             "unique_train_feature_coverage": old["unique_train_coverage"],
                             "exact_duplicate_rate": old["exact_duplicate_rate"],
                             "near_duplicate_rate": old["near_duplicate_rate"],
                             "f1_tstr_lr": utility.get("f1"),
                             "ap_tstr_lr": utility.get("average_precision"),
                             "utility_status": utility["status"],
                             "source": "phase6/report-v2/coverage.csv + results.json",
                             "source_row_hash": digest(old)})
    write_json(output/"consolidated-ablations.json", consolidated)
    pd.DataFrame(consolidated).to_csv(output/"consolidated-ablations.csv", index=False)
    ablation_rows, ablation_sources = [], []
    datasets = ["Abalone19", "Ecoli4", "page-blocks0"]
    labels = {"raw-labeled/random": "Raw labeled random", "schema/random": "Schema random",
              "combined/random": "Admitted random", "ablation/structure-only": "Structure + Q selection",
              "ablation/local-review": "Structure/local + Q", "ablation/global-review": "Structure/global + Q",
              "ablation/combined-review": "Structure/local/global + Q",
              "selection/source-order": "Admitted source order", "selection/farthest-first": "Admitted farthest first",
              "selection/coverage-greedy": "Admitted coverage greedy",
              "quality-coverage:repair-augmented": "Repair pool + Q"}
    for dataset in datasets:
        for method, label in labels.items():
            group = [r for r in consolidated if r["dataset_id"] == dataset and
                     (r["method"].startswith(method+"/s") or r["method"] == method)]
            if not group:
                raise ValueError("missing ablation table source")
            def mean(field: str, group: list[dict[str, Any]] = group) -> str:
                values = [r[field] for r in group if r.get(field) is not None]
                return number(np.mean(values)) if values else "--"
            ablation_rows.append([tex(dataset) if method == "raw-labeled/random" else "",
                                  label, str(group[0]["eligible_n"]), str(group[0]["budget_achieved"]),
                                  mean("unique_train_feature_coverage"), mean("exact_duplicate_rate"),
                                  mean("near_duplicate_rate"), mean("f1_tstr_lr")])
            ablation_sources.append({"dataset": dataset, "method": method,
                                     "input_row_hashes": [digest(r) for r in group],
                                     "aggregation": "arithmetic mean across five selection seeds for random; otherwise single fixed selection",
                                     "fields": ["dataset_id", "method", "eligible_n", "budget_achieved",
                                                "unique_train_feature_coverage", "exact_duplicate_rate",
                                                "near_duplicate_rate", "f1_tstr_lr"]})
    table("ablations", "Consolidated historical ablations. Q denotes unchanged quality-coverage selection. Random rows average five seeds; complete per-seed data accompany the paper. F1 is logistic pure TSTR; -- means unavailable.",
          ["Dataset", "Method", "Pool", "$n$", "Coverage", "Exact", "Near", "F1"], ablation_rows, ablation_sources)

    ext_rows = [r for r in results if r["track"] == "A" and r["method"] in
                ["REAL_TRAIN", "CLASS_WEIGHTED_LR", "RandomOverSampler+b", "SMOTE+b", "SMOTENC+b"]]
    table("external", "Historical external training baselines. ROS and SMOTE/NC append b minority rows. LR: logistic regression; RF: random forest. These differ from candidate curation.",
          ["Dataset / method", "Model", "$+n$", "F1", "AP", "BA", "MCC"],
          [[tex(r["dataset_id"]+" / "+method_label(r["method"])), "LR" if r["classifier"] == "logistic_regression" else "RF",
            str(r.get("synthetic_input_n", 0)), *[number(r.get(m)) for m in
            ["f1", "average_precision", "balanced_accuracy", "mcc"]]] for r in ext_rows],
          {"file": "results.json", "rows": [digest(r) for r in ext_rows]})
    ci_rows, ci_sources = [], []
    for dataset in datasets:
        for method in ["REAL_TRAIN", "quality-coverage:original", "quality-coverage:repair-augmented"]:
            for classifier in ["logistic_regression", "random_forest"]:
                regime = "TRTR" if method == "REAL_TRAIN" else "TSTR"
                group = [r for r in intervals if r["dataset_id"] == dataset and r["method"] == method
                         and r["classifier"] == classifier and r["regime"] == regime]
                label = {"REAL_TRAIN": "Real", "quality-coverage:original": "Q", "quality-coverage:repair-augmented": "Q repair"}[method]
                values = []
                for metric in ["f1", "average_precision", "balanced_accuracy", "mcc"]:
                    row = next(r for r in group if r["metric"] == metric)
                    values.append(number(row["estimate"])+" ["+number(row["lower"])+", "+number(row["upper"])+"]")
                ci_rows.append([tex(dataset+" / "+label), "LR" if classifier == "logistic_regression" else "RF", *values])
                ci_sources.append({"file": "bootstrap.json", "row_hashes": [digest(r) for r in group]})
    table("bootstrap", r"Conditional 95\% bootstrap intervals (2,000 stratified paired resamples). Q: quality-coverage pure TSTR; Real: TRTR. Degenerate MCC intervals are unavailable; all valid counts are saved.",
          ["Dataset / method", "Model", "F1 [CI]", "AP [CI]", "BA [CI]", "MCC [CI]"], ci_rows, ci_sources)
    pair_rows = [r for r in differences if r["left"][0] == "quality-coverage:repair-augmented"
                 and r["left"][1] == "logistic_regression" and r["left"][2] == "TSTR"]
    table("paired", "Repair-pool minus original Q, logistic pure TSTR: conditional paired difference intervals. These measure pool expansion and reselection together.",
          ["Dataset", "Metric", "Lower", "Upper", "Valid", "Undefined"],
          [[tex(r["dataset_id"]), tex(r["metric"]), number(r["lower"]), number(r["upper"]),
            str(r["valid_replicates"]), str(r["undefined_replicates"])] for r in pair_rows],
          {"file": "paired-differences.json", "rows": [digest(r) for r in pair_rows]})
    repeated_rows = [r for r in summary if r["regime"] != "TSTR" and r["classifier"] == "logistic_regression"
                     and r["method"] in ["REAL_TRAIN", "CLASS_WEIGHTED_LR", "RandomOverSampler+b", "SMOTE+b", "SMOTENC+b",
                                         "schema/random", "combined/random", "combined/quality-coverage"]]
    table("repeated", r"Offline replication: five repeated stratified holdouts, logistic regression, mean $\pm$ sample SD. Real and weighted are TRTR; other methods are hybrid minority augmentation. No historical candidates are reused.",
          ["Dataset / method", "$k$", "F1", "AP", "BA", "MCC"],
          [[tex(r["dataset_id"]+" / "+method_label(r["method"])), str(r["completed"]),
            *[number(r[m+"_mean"])+r" $\pm$ "+number(r[m+"_std"])
              for m in ["f1", "average_precision", "balanced_accuracy", "mcc"]]] for r in repeated_rows],
          {"file": "split-summary.json", "rows": [digest(r) for r in repeated_rows]})
    confusions = [r for r in results if r["status"] == "ok"]
    pd.DataFrame([{k: r.get(k) for k in ["track", "dataset_id", "split_seed", "method", "classifier", "regime",
                    "test_positive_n", "test_negative_n", "tp", "fp", "tn", "fn", "recall_wilson95"]}
                  for r in confusions]).to_csv(output/"confusions.csv", index=False)
    # Split-wise paired differences retain each seed, rather than compare independent averages.
    split_pairs = []
    for row in results:
        if row["track"] != "B" or row["method"] != "combined/quality-coverage" or row["status"] != "ok":
            continue
        for control in ["schema/random", "combined/random", "REAL_TRAIN"]:
            ref = next((r for r in results if r["track"] == "B" and r["dataset_id"] == row["dataset_id"]
                        and r["split_seed"] == row["split_seed"] and r["classifier"] == row["classifier"]
                        and r["method"] == control and r["status"] == "ok"
                        and r["regime"] == ("TRTR" if control == "REAL_TRAIN" else row["regime"])), None)
            if ref is not None:
                split_pairs.append({"dataset_id": row["dataset_id"], "split_seed": row["split_seed"],
                                    "classifier": row["classifier"], "regime": row["regime"],
                                    "left": row["method"], "right": control,
                                    **{m: row[m]-ref[m] for m in ["f1", "average_precision", "balanced_accuracy", "mcc"]}})
    write_json(output/"split-paired-differences.json", split_pairs)
    write_json(output/"table-evidence.json", ledger)
    write_json(paper/"notes/table-evidence.json", ledger)

    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "figure.dpi": 160, "savefig.bbox": "tight", "pdf.fonttype": 42})
    colors = ["#284f70", "#b75c3d", "#597b57"]
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.2), sharey=True)
    for ax, dataset, color in zip(axes, datasets, colors, strict=True):
        choices = ["schema/random", "combined/random", "selection/farthest-first", "ablation/combined-review"]
        groups = [[r for r in consolidated if r["dataset_id"] == dataset and r["method"].startswith(name+"/s")]
                  for name in choices]
        ax.bar(range(4), [np.mean([r["unique_train_feature_coverage"] for r in g]) for g in groups], color=color)
        ax.set_xticks(range(4), ["Schema\nrandom", "Admitted\nrandom", "Farthest\nfirst", "Quality\ncoverage"], fontsize=8)
        ax.set_title(dataset)
        ax.set_ylim(0, 1)
    axes[0].set_ylabel("Distinct TRAIN feature coverage")
    fig.tight_layout()
    fig.savefig(paper/"figures/coverage.pdf")
    fig.savefig(paper/"figures/coverage.png")
    plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.1))
    method_order = ["REAL_TRAIN", "schema/random", "combined/quality-coverage"]
    for ax, dataset, color in zip(axes, datasets, colors, strict=True):
        for ix, method in enumerate(method_order):
            vals = [r["f1"] for r in results if r["track"] == "B" and r["dataset_id"] == dataset
                    and r["method"] == method and r["classifier"] == "logistic_regression"
                    and r["regime"] != "TSTR" and r["status"] == "ok"]
            ax.scatter(np.full(len(vals), ix)+np.linspace(-.08, .08, len(vals)), vals, color=color, s=24)
            ax.plot([ix-.2, ix+.2], [np.mean(vals)]*2, color="black", lw=1.5)
        ax.set_xticks(range(3), ["Real", "Schema\nrandom", "Quality\ncoverage"])
        ax.set_title(dataset)
        ax.set_ylim(-.03, 1.05)
    axes[0].set_ylabel("F1 across five fresh splits (LR)")
    fig.tight_layout()
    fig.savefig(paper/"figures/repeated-f1.pdf")
    fig.savefig(paper/"figures/repeated-f1.png")
    plt.close(fig)

    # A compact factual readout is also used to review manuscript numerical claims.
    report = ["# RC-QASyn empirical evidence v2", "", "## Completed evidence", "",
              f"Frozen protocol: {manifest['protocol_fingerprint']}",
              f"Historical replay: {manifest['historical_replay_rows']} rows, all match: {manifest['historical_replay_all_match']}.",
              f"Utility rows: {len(results)}; status counts: {manifest['status_counts']}.",
              f"Fresh split populations: {sum(p['track'] == 'B' for p in population)}.",
              f"Bootstrap endpoint intervals: {len(intervals)}; paired difference intervals: {len(differences)}.",
              "", "## Five-split logistic results", "",
              "| Dataset | Method | Completed | F1 mean | F1 SD | AP mean | AP SD |",
              "|---|---|---:|---:|---:|---:|---:|"]
    report += [f"|{r['dataset_id']}|{r['method']}|{r['completed']}|{number(r['f1_mean'])}|{number(r['f1_std'])}|{number(r['average_precision_mean'])}|{number(r['average_precision_std'])}|" for r in repeated_rows]
    report += ["", "## Exploratory findings and unavailable comparisons", "",
               "Historical TEST reuse and value overlap preclude untouched-confirmatory interpretation.",
               "Offline minority-only pools make pure TSTR unavailable by construction.",
               "page-blocks0 replication uses ROS and creates no novel support; SMOTE numeric baseline is not integer-coerced.",
               "Classical training baselines and candidate curation answer different questions.",
               "Bootstrap is conditional on observed class counts, not independent split uncertainty.",
               "Admission ablations change eligibility; repair comparisons change pool and selection together.",
               "", "## Pending scientific decisions", "",
               "Author/affiliation/CRediT/funding/ethics and venue declarations; final scientific acceptance.",
               "Human annotation and validity calibration are outside this paper's active scope."]
    (output/"report.md").write_text("\n".join(report)+"\n", encoding="utf-8")
    write_json(output/"manifest.json", {"run_manifest_sha256": file_hash(run/"manifest.json"),
                                       "input_hashes": manifest["output_hashes"],
                                       "reporter_sha256": file_hash(Path(__file__)),
                                       "outputs": {p.relative_to(output).as_posix(): file_hash(p)
                                                   for p in output.rglob("*") if p.is_file()}})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paper", type=Path, required=True)
    args = parser.parse_args()
    main(Path(__file__).resolve().parents[1], args.run, args.output, args.paper)
