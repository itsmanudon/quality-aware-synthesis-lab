"""Summarize addendum v2 from saved outputs only and generate booktabs LaTeX tables.

Implements the reporting declared in addendum/v2/addendum-v2.json; never fits or re-scores.
Also renders numbers-only tables for addendum v1 from its saved summary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import mean, stdev
from typing import Any, cast

import numpy as np
from scipy.stats import friedmanchisquare, rankdata, wilcoxon

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT/"addendum/v2/addendum-v2.json"
V1_SUMMARY = ROOT/"addendum/v1/report/summary.json"
CAPTION = "Exploratory addendum, declared after the main study."
CLASSIFIERS = ["logistic_regression", "random_forest"]
SHORT = {"logistic_regression": "LR", "random_forest": "RF"}
METRIC = {"f1": "F1", "average_precision": "AP"}
QC = "combined/quality-coverage"
CURATORS = ["schema/random", "combined/random", "combined/source-order", "combined/farthest-first",
            "combined/coverage-greedy", QC, "reimpl/cllm-style", "reimpl/discriminator-realism"]
OVERSAMPLERS = [f"{m}/{s}" for m in ("SMOTE-ENN", "SMOTE-Tomek", "Borderline-SMOTE", "ADASYN")
                for s in ("full", "+b")]
SMOTE_B = "SMOTE(NC)+b"
COMPARATORS = ["REAL_TRAIN", "CLASS_WEIGHTED_LR", "RandomOverSampler+b", SMOTE_B, *OVERSAMPLERS]
NEW = ["reimpl/cllm-style", "reimpl/discriminator-realism", *OVERSAMPLERS]
R2 = [QC, "combined/random", "combined/farthest-first", "reimpl/cllm-style",
      "reimpl/discriminator-realism", "REAL_TRAIN", "RandomOverSampler+b", SMOTE_B, *OVERSAMPLERS]
LABELS = {"schema/random": "Schema rand.", "combined/random": "Adm. rand.",
          "combined/source-order": "Source order", "combined/farthest-first": "Farthest-first",
          "combined/coverage-greedy": "Cov.-greedy", QC: "QC (ours)",
          "reimpl/cllm-style": "CLLM-style$^\\dagger$", "reimpl/discriminator-realism": "Disc.-realism$^\\dagger$",
          "REAL_TRAIN": "Real only", "CLASS_WEIGHTED_LR": "CW-LR", "RandomOverSampler+b": "ROS+$b$",
          SMOTE_B: "SMOTE(NC)+$b$", **{m: m.replace("/full", " full").replace("/+b", " +$b$")
                                         .replace("Borderline-SMOTE", "B-SMOTE") for m in OVERSAMPLERS}}


def load(path: Path) -> Any:
    return json.loads(path.read_text("utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def regime(method: str) -> str:
    return "HYBRID_MINORITY" if method in CURATORS or method in ("RandomOverSampler+b", SMOTE_B) else "TRTR"


def tex(text: str) -> str:
    return text.replace("_", "\\_").replace("%", "\\%")


class Report:
    def __init__(self, run: Path):
        self.run = run
        self.config = load(CONFIG)
        self.rows = load(run/"results.json")
        for row in self.rows:
            if row["method"] in ("SMOTE+b", "SMOTENC+b"):
                row["method"] = SMOTE_B
        self.populations = load(run/"populations.json")
        self.constructions = load(run/"constructions.json")
        self.unavailable = load(run/"unavailable.json")
        self.pools = load(run/"pools.json")
        self.manifest = load(run/"manifest.json")
        d = self.config["datasets"]
        self.datasets = [*d["canonical"]["ids"], *d["new"]["ids"]]
        self.index: dict[tuple[str, str, str, str], dict[int, float | None]] = {}
        for r in self.rows:
            if r["regime"] != regime(r["method"]):
                continue
            for metric in ("f1", "average_precision", "auroc", "mcc", "balanced_accuracy"):
                key = (r["dataset_id"], r["method"], r["classifier"], metric)
                self.index.setdefault(key, {})[r["split_seed"]] = (
                    r[metric] if r["status"] == "ok" else None)

    def splits(self, dataset: str, method: str, classifier: str, metric: str) -> dict[int, float | None]:
        return self.index.get((dataset, method, classifier, metric), {})

    def value(self, dataset: str, method: str, classifier: str, metric: str) -> float | None:
        values = self.splits(dataset, method, classifier, metric)
        if len(values) != 5 or any(v is None for v in values.values()):
            return None
        return mean(cast(list[float], list(values.values())))

    # ---- declared analyses ------------------------------------------------------------------
    def pairwise(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for dataset in self.datasets:
            for classifier in CLASSIFIERS:
                for metric in ("f1", "average_precision"):
                    qc = self.splits(dataset, QC, classifier, metric)
                    for method in [*NEW, "combined/random", "combined/farthest-first", "REAL_TRAIN"]:
                        other = self.splits(dataset, method, classifier, metric)
                        diffs = [float(a)-float(b) for s, a in qc.items()
                                 if a is not None and (b := other.get(s)) is not None]
                        out[f"{dataset}|{classifier}|{metric}|{method}"] = {
                            "paired_splits": len(diffs),
                            "mean": mean(diffs) if diffs else None,
                            "sd": stdev(diffs) if len(diffs) > 1 else None,
                            "wins": sum(x > 0 for x in diffs), "ties": sum(x == 0 for x in diffs),
                            "losses": sum(x < 0 for x in diffs)}
        return out

    def ranking(self, methods: list[str]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for classifier in CLASSIFIERS:
            for metric in ("f1", "average_precision"):
                complete = [d for d in self.datasets
                            if all(self.value(d, m, classifier, metric) is not None for m in methods)]
                matrix = np.array([[cast(float, self.value(d, m, classifier, metric)) for m in methods]
                                   for d in complete])
                entry: dict[str, Any] = {"datasets": complete, "n_datasets": len(complete)}
                if len(complete):
                    ranks = np.array([rankdata(-row) for row in matrix])
                    entry["average_rank"] = dict(zip(methods, ranks.mean(axis=0).tolist(), strict=True))
                    entry["dataset_means"] = {d: dict(zip(methods, row.tolist(), strict=True))
                                              for d, row in zip(complete, matrix, strict=True)}
                if len(complete) >= 2 and len(methods) >= 3:
                    statistic, p_value = cast(tuple[Any, Any], friedmanchisquare(*matrix.T))
                    entry["friedman"] = {"statistic": float(statistic), "p_value": float(p_value)}
                out[f"{classifier}|{metric}"] = entry
        return out

    def wilcoxon_tests(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for classifier in CLASSIFIERS:
            for metric in ("f1", "average_precision"):
                for method in [m for m in [*CURATORS, *COMPARATORS] if m != QC]:
                    diffs = {d: cast(float, self.value(d, QC, classifier, metric))
                             - cast(float, self.value(d, method, classifier, metric))
                             for d in self.datasets if self.value(d, QC, classifier, metric) is not None
                             and self.value(d, method, classifier, metric) is not None}
                    values = list(diffs.values())
                    entry: dict[str, Any] = {"n_datasets": len(values), "datasets": list(diffs),
                                             "qc_better": sum(v > 0 for v in values),
                                             "qc_worse": sum(v < 0 for v in values),
                                             "median_difference": float(np.median(values)) if values else None}
                    if len(values) >= 2 and any(v != 0 for v in values):
                        statistic, p_value = cast(tuple[Any, Any], wilcoxon(
                            values, alternative="two-sided", zero_method="wilcox", method="auto"))
                        entry.update(statistic=float(statistic), p_value=float(p_value))
                    else:
                        entry.update(statistic=None, p_value=None)
                    out[f"{classifier}|{metric}|{method}"] = entry
        return out

    def sanity(self) -> dict[str, Any]:
        literature = self.config["reporting"]["literature_sanity_check"]["values"]
        out = {}
        for dataset, theirs in literature.items():
            ours = {SHORT[c]: {m: (None if (v := self.value(dataset, m, c, "auroc")) is None else 100*v)
                               for m in ["REAL_TRAIN", SMOTE_B, "ADASYN/full", "SMOTE-ENN/full",
                                         "SMOTE-Tomek/full"]} for c in CLASSIFIERS}
            theirs_sign = np.sign(theirs["SMOTE"]-theirs["unsampled"])
            agreement = {}
            for c, values in ours.items():
                real, smote = values["REAL_TRAIN"], values[SMOTE_B]
                agreement[c] = (None if real is None or smote is None
                                else bool(np.sign(smote-real) == theirs_sign))
            out[dataset] = {"newaz_haq_table7": theirs, "ours_auroc_x100": ours,
                            "smote_minus_unsampled_sign_agrees": agreement}
        return out

    def datasets_table(self) -> list[dict[str, Any]]:
        rows = []
        for dataset in [*self.datasets, *self.config["datasets"]["unavailable"]]:
            populations = [p for p in self.populations if p["dataset_id"] == dataset]
            if not populations:
                rows.append({"dataset_id": dataset, "status": "unavailable"})
                continue
            first = populations[0]
            total = Counter(first["train_class_counts"])+Counter(first["test_class_counts"])
            pools = [p for p in self.pools if p["dataset_id"] == dataset]
            spec_root = ("canonical" if dataset in self.config["datasets"]["canonical"]["ids"] else "new")
            rows.append({"dataset_id": dataset, "status": "ok", "source": spec_root,
                         "rows": sum(total.values()), "minority": total["positive"],
                         "imbalance_ratio": total["negative"]/total["positive"],
                         "budgets": sorted({p["budget"] for p in pools}),
                         "pool_generator": pools[0]["generator"] if pools else None,
                         "test_positives": sorted({p["test_class_counts"].get("positive", 0)
                                                   for p in populations}),
                         "schema_pool_n": sorted({p["schema_pool_n"] for p in pools}),
                         "nominal": dataset in self.config["datasets"]["nominal"]})
        return rows

    def summary(self) -> dict[str, Any]:
        failures = Counter((u["dataset_id"], u["method"], u["reason"]) for u in self.unavailable)
        return {"label": CAPTION,
                "inputs": {"manifest_sha256": sha(self.run/"manifest.json"),
                           "results_sha256": sha(self.run/"results.json"),
                           "settings_sha256": sha(CONFIG)},
                "run": {k: self.manifest[k] for k in ["status_counts", "rows_by_category",
                                                      "declaration_commit", "implementation_revision",
                                                      "pool_identity_all_match", "reproduction"]},
                "unavailable": [{"dataset_id": d, "method": m, "reason": r, "occurrences": n}
                                for (d, m, r), n in sorted(failures.items())],
                "datasets": self.datasets_table(), "pairwise": self.pairwise(),
                "R1_curators": self.ranking(CURATORS), "R2_all": self.ranking(R2),
                "wilcoxon_qc_vs_method": self.wilcoxon_tests(), "literature_sanity_check": self.sanity(),
                "means": {f"{d}|{m}|{c}|{k}": self.value(d, m, c, k) for d in self.datasets
                          for m in [*CURATORS, *COMPARATORS] for c in CLASSIFIERS
                          for k in ("f1", "average_precision", "auroc")}}


# ---- LaTeX ------------------------------------------------------------------------------------
def cell(value: float | None, best: bool = False) -> str:
    if value is None:
        return "--"
    text = f"{value:.3f}".lstrip("0") if value >= 0 else f"$-${abs(value):.3f}".replace("$-$0", "$-$")
    return f"\\textbf{{{text}}}" if best else text


def fit(text: str) -> str:
    """Scale each tabular to the column (table) or page (table*) width; layout is left to authors."""
    width = "\\textwidth" if "\\begin{table*}" in text else "\\linewidth"
    return (text.replace("\\begin{tabular}", f"\\resizebox{{{width}}}{{!}}{{%\n\\begin{{tabular}}")
            .replace("\\end{tabular}", "\\end{tabular}}"))


def panels(s: dict[str, Any], datasets: list[str], methods: list[str], label: str, caption: str,
           note: str) -> str:
    lines = ["\\begin{table*}[!t]", "\\centering", "\\scriptsize", "\\setlength{\\tabcolsep}{3pt}",
             f"\\caption{{{CAPTION} {caption}}}", f"\\label{{{label}}}",
             f"\\begin{{tabular}}{{l{'r'*len(methods)}}}", "\\toprule",
             "Dataset & " + " & ".join(LABELS[m] for m in methods) + " \\\\"]
    for classifier in CLASSIFIERS:
        for metric in ("f1", "average_precision"):
            lines += ["\\midrule", (f"\\multicolumn{{{len(methods)+1}}}{{l}}{{\\textit{{{SHORT[classifier]}, "
                      f"mean {METRIC[metric]} over five splits}}}} \\\\")]
            for dataset in datasets:
                values = [s["means"].get(f"{dataset}|{m}|{classifier}|{metric}") for m in methods]
                if classifier != "logistic_regression":
                    values = [None if m == "CLASS_WEIGHTED_LR" else v
                              for m, v in zip(methods, values, strict=True)]
                top = max((v for v in values if v is not None), default=None)
                lines.append(tex(dataset) + " & " + " & ".join(
                    cell(v, v is not None and v == top) for v in values) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}", "", f"\\vspace{{2pt}}\\parbox{{\\textwidth}}{{\\scriptsize {note}}}",
              "\\end{table*}", ""]
    return "\n".join(lines)


def ranks_table(s: dict[str, Any]) -> str:
    keys = [f"{c}|{m}" for c in CLASSIFIERS for m in ("f1", "average_precision")]
    heads = " & ".join(f"{SHORT[k.split('|')[0]]} {METRIC[k.split('|')[1]]}" for k in keys)
    lines = ["\\begin{table}[!t]", "\\centering", "\\scriptsize", "\\setlength{\\tabcolsep}{3pt}",
             (f"\\caption{{{CAPTION} Average ranks (1 = best) of mean F1 and AP across datasets, with "
             "exploratory Friedman tests, and Wilcoxon signed-rank tests of quality-coverage against "
             "each method. No multiplicity adjustment or significance claim.}"),
             "\\label{tab:addendum-ranks}", "\\begin{tabular}{lrrrr}", "\\toprule"]
    for name, title, methods in [("R1_curators", "(a) Curators", CURATORS), ("R2_all", "(b) All methods", R2)]:
        r = s[name]
        n = r[keys[0]]["n_datasets"]
        lines += [f"\\multicolumn{{5}}{{l}}{{\\textit{{{title}, {n} complete datasets}}}} \\\\",
                  f"Method & {heads} \\\\", "\\midrule"]
        for method in methods:
            lines.append(LABELS[method] + " & " + " & ".join(
                f"{r[k]['average_rank'][method]:.2f}" if "average_rank" in r[k] else "--" for k in keys)
                + " \\\\")
        lines.append("Friedman $p$ & " + " & ".join(
            f"{r[k]['friedman']['p_value']:.3f}" if "friedman" in r[k] else "--" for k in keys) + " \\\\")
        lines.append("\\midrule")
    lines += ["\\multicolumn{5}{l}{\\textit{(c) Wilcoxon, QC minus method: datasets QC better/worse, $p$}} \\\\",
              f"Method & {heads} \\\\", "\\midrule"]
    for method in [m for m in [*CURATORS, *COMPARATORS] if m != QC]:
        parts = []
        for k in keys:
            w = s["wilcoxon_qc_vs_method"][f"{k}|{method}"]
            if not w["n_datasets"]:
                parts.append("--")
            else:
                p = "--" if w["p_value"] is None else f"{w['p_value']:.2f}"
                parts.append(f"{w['qc_better']}/{w['qc_worse']}, {p}")
        lines.append(LABELS[method] + " & " + " & ".join(parts) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]
    return "\n".join(lines)


def datasets_tex(s: dict[str, Any]) -> str:
    lines = ["\\begin{table}[!t]", "\\centering", "\\scriptsize", "\\setlength{\\tabcolsep}{3pt}",
             (f"\\caption{{{CAPTION} Datasets. IR = majority/minority; $b$ = selection budget; TEST "
             "positives are per split (five stratified 80/20 splits).}"),
             "\\label{tab:addendum-datasets}", "\\begin{tabular}{lrrrcrcl}", "\\toprule",
             "Dataset & Rows & Min. & IR & Nom. & $b$ & TEST pos. & Pool gen. \\\\", "\\midrule"]
    for d in s["datasets"]:
        if d["status"] != "ok":
            lines.append(f"{tex(d['dataset_id'])} & \\multicolumn{{7}}{{l}}{{unavailable (empty source archive)}} \\\\")
            continue
        lines.append(f"{tex(d['dataset_id'])} & {d['rows']} & {d['minority']} & {d['imbalance_ratio']:.1f} & "
                     f"{'yes' if d['nominal'] else 'no'} & {'/'.join(map(str, d['budgets']))} & "
                     f"{'/'.join(map(str, d['test_positives']))} & {d['pool_generator']} \\\\")
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]
    return "\n".join(lines)


def v1_tables(v1: dict[str, Any]) -> dict[str, str]:
    e4 = v1["E4"]["comparisons"]
    lines = ["\\begin{table}[!t]", "\\centering", "\\scriptsize", "\\setlength{\\tabcolsep}{3pt}",
             (f"\\caption{{{CAPTION} Addendum v1 across-dataset summary: dataset-level mean difference "
             "and split wins/ties/losses over five fresh splits.}"), "\\label{tab:addendum-v1-e4}",
             "\\begin{tabular}{lllrrr}", "\\toprule",
             "Comparison & Clf & Metric & Datasets $+/-/0$ & Splits W/T/L & Median diff. \\\\", "\\midrule"]
    names = {"QC_minus_admitted_random": "QC $-$ adm. random", "QC_minus_real_only": "QC $-$ real only",
             "best_augmentation_minus_real_only": "Best aug. $-$ real only$^\\ast$"}
    for key, x in e4.items():
        name, classifier, metric = key.split("|")
        lines.append(f"{names[name]} & {SHORT[classifier]} & {METRIC[metric]} & "
                     f"{x['datasets_positive_mean']}/{x['datasets_negative_mean']}/{x['datasets_zero_mean']} & "
                     f"{x['total_wins']}/{x['total_ties']}/{x['total_losses']} & "
                     f"{x['median_dataset_mean_difference']:+.3f} \\\\")
    lines += ["\\bottomrule", "\\end{tabular}", "",
              ("\\vspace{2pt}\\parbox{\\linewidth}{\\scriptsize $^\\ast$Best method chosen on the same TEST "
              "splits; optimistic by construction.}"), "\\end{table}", ""]
    e4_tex = "\n".join(lines)
    lines = ["\\begin{table*}[!t]", "\\centering", "\\scriptsize", "\\setlength{\\tabcolsep}{3pt}",
             (f"\\caption{{{CAPTION} Addendum v1 historical-split designs at fixed budgets: canonical "
             "quality-coverage (QC, quota $0.5b$), QC with the real-ratio quota (E2), admitted random "
             "(mean of five seeds) and random subsets of the B2-accepted pool (E3, mean of five seeds).}"),
             "\\label{tab:addendum-v1-e2e3}", "\\begin{tabular}{llrrrrrrrr}", "\\toprule",
             ("Dataset & Design & Quota & Cov. & Near dup. & LR TSTR F1 & LR Hyb. F1 & RF TSTR F1 & "
             "RF Hyb. F1 & LR Hyb. AP \\\\"), "\\midrule"]
    for dataset, e in v1["E2_E3"].items():
        for label, key in [("QC", "canonical_quality_coverage_same_environment"),
                           ("QC real ratio (E2)", "E2_real_ratio_quality_coverage"),
                           ("Adm. random", "canonical_admitted_random_same_environment"),
                           ("B2 random (E3)", "E3_b2_accepted_random")]:
            x = e[key]
            u = x["utility"]
            quota = x["minority_quota_requested"][0]
            lines.append(
                f"{tex(dataset)} & {label} & {'--' if quota is None else quota} & "
                f"{cell(x['unique_train_feature_coverage']['mean'])} & {cell(x['near_duplicate_rate']['mean'])} & "
                + " & ".join(cell(u[k][m]["mean"]) for k, m in [
                    ("logistic_regression|TSTR", "f1"), ("logistic_regression|HYBRID_MINORITY", "f1"),
                    ("random_forest|TSTR", "f1"), ("random_forest|HYBRID_MINORITY", "f1"),
                    ("logistic_regression|HYBRID_MINORITY", "average_precision")]) + " \\\\")
        lines.append("\\midrule")
    lines[-1] = "\\bottomrule"
    lines += ["\\end{tabular}", "\\end{table*}", ""]
    return {"addendum-v1-e4.tex": e4_tex, "addendum-v1-e2e3.tex": "\n".join(lines)}


SECTION = (
    '% Exploratory addendum: generated scaffold. Tables are generated from saved results',
    '% (addendum/v1/report, addendum/v2/report); no prose is generated here.',
    '\\subsection{Exploratory addendum}',
    '\\label{sec:addendum}',
    '',
    '% AUTHORS: write the paragraph here (scope: declared after the main study; datasets; designs).',
    '\\input{tables/addendum/addendum-datasets}',
    '',
    '% AUTHORS: write the paragraph here (addendum v1: quality-coverage vs admitted random across datasets).',
    '\\input{tables/addendum/addendum-v1-e4}',
    '',
    '% AUTHORS: write the paragraph here (addendum v1: real-ratio quota and equal-budget B2 control).',
    '\\input{tables/addendum/addendum-v1-e2e3}',
    '',
    '% AUTHORS: write the paragraph here (addendum v2: curators incl. re-implemented CLLM-style and discriminator-realism).',
    '\\input{tables/addendum/benchmark-curators}',
    '',
    '% AUTHORS: write the paragraph here (addendum v2: published oversamplers as training comparators).',
    '\\input{tables/addendum/benchmark-oversamplers}',
    '',
    '% AUTHORS: write the paragraph here (addendum v2: ranks and exploratory tests; no significance claim).',
    '\\input{tables/addendum/benchmark-ranks}',
)


def section() -> str:
    return "\n".join(SECTION)+"\n"


def markdown(s: dict[str, Any], conclusion: str) -> str:
    out = ["# RC-QASyn exploratory addendum v2: published-method benchmark", "",
           (f"> **{CAPTION}** Settings committed in `addendum/v2/addendum-v2.json` "
           f"(`{s['run']['declaration_commit'][:7]}`) before any score; one execution "
           f"(`{s['run']['implementation_revision'][:7]}`). Re-implemented curators (marked with a dagger) "
           "follow published principles; they are not the authors' code. Every row counted."), "",
           (f"Rows: {s['run']['rows_by_category']}; status {s['run']['status_counts']}. Pools identical to "
           f"recorded: {s['run']['pool_identity_all_match']}. Reproduction: {s['run']['reproduction']}."), "",
           "## Average ranks (1 = best)", ""]
    for name, methods in [("R1_curators", CURATORS), ("R2_all", R2)]:
        r = s[name]
        keys = list(r)
        out += [f"**{name}** ({r[keys[0]]['n_datasets']} complete datasets: {', '.join(r[keys[0]]['datasets'])})",
                "", "| Method | " + " | ".join(k.replace("logistic_regression", "LR").replace("random_forest", "RF")
                                                .replace("average_precision", "AP") for k in keys) + " |",
                "|---" * (len(keys)+1) + "|"]
        for m in methods:
            out.append(f"| {m} | " + " | ".join(f"{r[k]['average_rank'][m]:.2f}" for k in keys) + " |")
        out.append("| Friedman p | " + " | ".join(f"{r[k]['friedman']['p_value']:.3f}" for k in keys) + " |")
        out.append("")
    out += ["## Wilcoxon: quality-coverage minus method (datasets QC better / worse, median diff, p)", "",
            "| Method | LR F1 | LR AP | RF F1 | RF AP |", "|---|---|---|---|---|"]
    for m in [x for x in [*CURATORS, *COMPARATORS] if x != QC]:
        cells = []
        for c in CLASSIFIERS:
            for k in ("f1", "average_precision"):
                w = s["wilcoxon_qc_vs_method"][f"{c}|{k}|{m}"]
                cells.append("n/a" if not w["n_datasets"] else
                             f"{w['qc_better']}/{w['qc_worse']}, {w['median_difference']:+.3f}, "
                             f"p={'n/a' if w['p_value'] is None else format(w['p_value'], '.2f')}")
        out.append(f"| {m} | " + " | ".join(cells) + " |")
    out += ["", "## Literature sanity check (context only; Newaz & Haq Table 7, RF, 10-fold CV)", "",
            "| Dataset | Theirs unsampled / SMOTE | Ours RF real / SMOTE(NC)+b | Ours LR real / SMOTE(NC)+b | sign agrees RF, LR |",
            "|---|---|---|---|---|"]
    for d, x in s["literature_sanity_check"].items():
        t, o = x["newaz_haq_table7"], x["ours_auroc_x100"]
        fmt = lambda v: "n/a" if v is None else f"{v:.1f}"
        out.append(f"| {d} | {t['unsampled']:.1f} / {t['SMOTE']:.1f} | {fmt(o['RF']['REAL_TRAIN'])} / "
                   f"{fmt(o['RF'][SMOTE_B])} | {fmt(o['LR']['REAL_TRAIN'])} / {fmt(o['LR'][SMOTE_B])} | "
                   f"{x['smote_minus_unsampled_sign_agrees']['RF']}, {x['smote_minus_unsampled_sign_agrees']['LR']} |")
    out += ["", "## Unavailable (every occurrence counted)", ""]
    out += [f"- {u['dataset_id']} / {u['method']}: {u['reason']} (x{u['occurrences']})" for u in s["unavailable"]]
    out += ["", "## Conclusion", "", conclusion.strip(), ""]
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--conclusion", type=Path)
    args = parser.parse_args()
    report = Report(args.run)
    s = report.summary()
    s["conclusion"] = (args.conclusion.read_text("utf-8") if args.conclusion else "PENDING").strip()
    tables = args.output/"tables"
    if (args.output/"summary.json").exists() or tables.exists():
        raise SystemExit("summary outputs exist; write a fresh version instead")
    tables.mkdir(parents=True)
    (args.output/"summary.json").write_text(json.dumps(s, sort_keys=True, indent=2, allow_nan=False)+"\n")
    (args.output/"summary.md").write_text(markdown(s, s["conclusion"]))
    curated = [d for d in report.datasets if report.value(d, QC, "logistic_regression", "f1") is not None]
    (tables/"benchmark-curators.tex").write_text(fit(panels(
        s, curated, CURATORS, "tab:addendum-curators",
        "Mean F1 and AP of the eight curators (hybrid training: real TRAIN plus $b$ selected candidates).",
        "Bold: best in row. $^\\dagger$Re-implementation of the published principle, not the authors' code. "
        "vehicle0 omitted: no structurally complete candidate.")))
    (tables/"benchmark-oversamplers.tex").write_text(fit(panels(
        s, report.datasets, ["REAL_TRAIN", "CLASS_WEIGHTED_LR", "RandomOverSampler+b", SMOTE_B,
                             *OVERSAMPLERS, QC], "tab:addendum-oversamplers",
        "Mean F1 and AP of real-only training, class weighting, existing oversamplers, four published "
        "oversamplers (imbalanced-learn 0.14.2; full balancing and $+b$ rows) and quality-coverage.",
        "Bold: best in row. --: unavailable (no nominal path, library error or no structurally complete "
        "candidate; CW-LR is logistic only). SMOTE-ENN/Tomek may remove rows; final counts are in results.")))
    (tables/"benchmark-ranks.tex").write_text(fit(ranks_table(s)))
    (tables/"addendum-datasets.tex").write_text(fit(datasets_tex(s)))
    for name, text in v1_tables(load(V1_SUMMARY)).items():
        (tables/name).write_text(fit(text))
    (tables/"04b-addendum.tex").write_text(section())


if __name__ == "__main__":
    main()
