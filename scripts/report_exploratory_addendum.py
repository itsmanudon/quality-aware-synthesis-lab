"""Summarize the exploratory addendum from saved outputs only; never fits or re-scores.

Implements the E4 definitions declared in configs/empirical/addendum-v1.json. Every row,
including unavailable ones, is counted; nothing here selects settings or reruns a design.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import mean, stdev
from typing import Any, cast

from scipy.stats import wilcoxon

ROOT = Path(__file__).resolve().parents[1]
RUN_V2 = ROOT/"artifacts/reports/empirical-v2/run-v2"
CANONICAL = ["Abalone19", "Ecoli4", "page-blocks0"]
CURATORS = ["schema/random", "combined/random", "combined/source-order", "combined/farthest-first",
            "combined/coverage-greedy", "combined/quality-coverage"]
AUGMENTATIONS = [*CURATORS, "RandomOverSampler+b", "SMOTE+b", "SMOTENC+b"]
CLASSIFIERS = ["logistic_regression", "random_forest"]
SHORT = {"logistic_regression": "LR", "random_forest": "RF"}
LABEL = "Exploratory addendum, declared after the main study; not part of the canonical tables."


def load(path: Path) -> Any:
    return json.loads(path.read_text("utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stats(values: list[float]) -> dict[str, Any]:
    return {"n": len(values), "mean": mean(values) if values else None,
            "sd": stdev(values) if len(values) > 1 else None}


def fmt(value: Any, digits: int = 3) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def signed(value: Any) -> str:
    return "n/a" if value is None else f"{value:+.3f}"


class Report:
    def __init__(self, run: Path):
        self.run = run
        self.rows = load(run/"results.json")
        for line, row in enumerate(self.rows, start=2):
            row["_csv_line"] = line  # results.csv header is line 1
        self.constructions = load(run/"constructions.json")
        self.populations = load(run/"populations.json")
        self.pools = load(run/"pools.json")
        self.repairs = load(run/"repairs.json")
        self.unavailable = load(run/"unavailable.json")
        self.config = load(ROOT/"configs/empirical/addendum-v1.json")
        self.canonical = load(RUN_V2/"results.json")
        self.canonical_constructions = load(RUN_V2/"constructions.json")
        self.datasets_new = self.config["E1"]["datasets"]

    # ---- row access -------------------------------------------------------------------------
    def find(self, rows: list[dict[str, Any]], **keys: Any) -> list[dict[str, Any]]:
        return [r for r in rows if all(r.get(k) == v for k, v in keys.items())]

    def fresh_rows(self, dataset: str) -> list[dict[str, Any]]:
        if dataset in CANONICAL:
            return [r for r in self.canonical if r["track"] == "B" and r["dataset_id"] == dataset]
        return [r for r in self.rows if r["track"] == "E1" and r["dataset_id"] == dataset]

    def per_split(self, rows: list[dict[str, Any]], method: str, classifier: str, regime: str,
                  metric: str) -> dict[int, float | None]:
        out: dict[int, float | None] = {}
        for r in self.find(rows, method=method, classifier=classifier, regime=regime):
            out[r["split_seed"]] = r[metric] if r["status"] == "ok" else None
        return out

    # ---- E1 ---------------------------------------------------------------------------------
    def e1(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for dataset in self.datasets_new:
            rows = self.fresh_rows(dataset)
            if not rows:
                result[dataset] = {"status": "unavailable", "reason": next(
                    u["reason"] for u in self.unavailable if u["dataset_id"] == dataset)}
                continue
            entry: dict[str, Any] = {"pools": [p for p in self.pools if p["track"] == "E1"
                                               and p["dataset_id"] == dataset], "utility": {},
                                     "geometry": {}}
            methods = ["REAL_TRAIN", "CLASS_WEIGHTED_LR", *AUGMENTATIONS]
            for method in methods:
                for classifier in CLASSIFIERS:
                    for regime in ["TRTR", "HYBRID_MINORITY"]:
                        found = self.find(rows, method=method, classifier=classifier, regime=regime)
                        if not found:
                            continue
                        ok = [r for r in found if r["status"] == "ok"]
                        entry["utility"][f"{method}|{classifier}|{regime}"] = {
                            "splits": len(found), "completed": len(ok),
                            "reasons": dict(Counter(r["reason"] for r in found if r["status"] != "ok")),
                            **{m: stats([r[m] for r in ok if r[m] is not None])
                               for m in ["f1", "average_precision", "mcc"]}}
            for method in CURATORS:
                built = [c for c in self.constructions if c["track"] == "E1"
                         and c["dataset_id"] == dataset and c["method"] == method]
                ok = [c for c in built if c["status"] == "ok"]
                entry["geometry"][method] = {
                    "constructions": len(built), "budget_reached": len(ok),
                    **{k: stats([c[k] for c in ok if c[k] is not None])
                       for k in ["unique_train_feature_coverage", "class_balanced_region_coverage",
                                 "exact_duplicate_rate", "near_duplicate_rate"]}}
            result[dataset] = entry
        return result

    # ---- E2 / E3 ----------------------------------------------------------------------------
    def track_a_entry(self, track: str, dataset: str, methods: list[str]) -> dict[str, Any]:
        built = [c for c in self.constructions if c["track"] == track and c["dataset_id"] == dataset
                 and c["method"] in methods]
        utility: dict[str, Any] = {}
        for classifier in CLASSIFIERS:
            for regime in ["TSTR", "HYBRID_MINORITY"]:
                found = [r for r in self.rows if r["track"] == track and r["dataset_id"] == dataset
                         and r["method"] in methods and r["classifier"] == classifier
                         and r["regime"] == regime]
                ok = [r for r in found if r["status"] == "ok"]
                utility[f"{classifier}|{regime}"] = {
                    "rows": len(found), "completed": len(ok),
                    "csv_lines": [r["_csv_line"] for r in found],
                    "reasons": dict(Counter(r["reason"] for r in found if r["status"] != "ok")),
                    **{m: stats([r[m] for r in ok if r[m] is not None])
                       for m in ["f1", "average_precision", "mcc"]}}
        return {"constructions": len(built),
                "budget_reached": sum(c["status"] == "ok" for c in built),
                "label_counts": [c["label_counts"] for c in built],
                "minority_quota_requested": [c.get("minority_quota_requested") for c in built],
                **{k: stats([c[k] for c in built if c[k] is not None])
                   for k in ["unique_train_feature_coverage", "class_balanced_region_coverage",
                             "exact_duplicate_rate", "near_duplicate_rate"]},
                "utility": utility}

    def run_v2_entry(self, dataset: str, methods: list[str]) -> dict[str, Any]:
        out = {}
        for classifier in CLASSIFIERS:
            for regime in ["TSTR", "HYBRID_MINORITY"]:
                ok = [r for r in self.canonical if r["track"] == "A" and r["dataset_id"] == dataset
                      and r["method"] in methods and r["classifier"] == classifier
                      and r["regime"] == regime and r["status"] == "ok"]
                out[f"{classifier}|{regime}"] = {m: stats([r[m] for r in ok if r[m] is not None])
                                                 for m in ["f1", "average_precision", "mcc"]}
        return out

    def e2_e3(self) -> dict[str, Any]:
        random = [f"combined/random/s{s}" for s in self.config["selection_seeds"]]
        b2 = [f"E3/b2-accepted-random/s{s}" for s in self.config["selection_seeds"]]
        result: dict[str, Any] = {}
        for dataset in CANONICAL:
            result[dataset] = {
                "pool": next(p for p in self.pools if p["track"] == "A" and p["dataset_id"] == dataset),
                "E2_real_ratio_quality_coverage": self.track_a_entry(
                    "E2", dataset, ["E2/quality-coverage-real-ratio/s42"]),
                "canonical_quality_coverage_same_environment": self.track_a_entry(
                    "A-reproduction", dataset, ["selection/quality-coverage/s42"]),
                "canonical_admitted_random_same_environment": self.track_a_entry(
                    "A-reproduction", dataset, random),
                "E3_b2_accepted_random": self.track_a_entry("E3", dataset, b2),
                "run_v2_quality_coverage": self.run_v2_entry(dataset,
                                                             ["selection/quality-coverage/s42"]),
                "run_v2_admitted_random": self.run_v2_entry(dataset, random)}
        return result

    # ---- E4 ---------------------------------------------------------------------------------
    def e4(self) -> dict[str, Any]:
        datasets = [*CANONICAL, *self.datasets_new]
        comparisons: dict[str, Any] = {}
        per_dataset: dict[str, Any] = {}
        for dataset in datasets:
            rows = self.fresh_rows(dataset)
            populations = (self.find(self.canonical_populations(), track="B", dataset_id=dataset)
                           if dataset in CANONICAL
                           else self.find(self.populations, track="E1", dataset_id=dataset))
            per_dataset[dataset] = {
                "source": "run-v2 Track B" if dataset in CANONICAL else "addendum E1",
                "available": bool(rows),
                "test_positive_n_by_split": {p["root_seed"]: p["test_class_counts"].get("positive", 0)
                                             for p in populations},
                "budget_by_split": {r["split_seed"]: r["budget"] for r in rows
                                    if r["method"] == "combined/quality-coverage"
                                    and r["classifier"] == "logistic_regression"
                                    and r["regime"] == "HYBRID_MINORITY"}}
            if not rows:
                per_dataset[dataset]["reason"] = next(u["reason"] for u in self.unavailable
                                                      if u["dataset_id"] == dataset)
        for classifier in CLASSIFIERS:
            for metric in ["f1", "average_precision"]:
                for name in ["QC_minus_admitted_random", "QC_minus_real_only",
                             "best_augmentation_minus_real_only"]:
                    key = f"{name}|{classifier}|{metric}"
                    entries = {}
                    for dataset in datasets:
                        rows = self.fresh_rows(dataset)
                        if not rows:
                            entries[dataset] = {"status": "unavailable", "reason": "DATASET_UNAVAILABLE"}
                            continue
                        real = self.per_split(rows, "REAL_TRAIN", classifier, "TRTR", metric)
                        chosen = None
                        if name == "QC_minus_admitted_random":
                            left = self.per_split(rows, "combined/quality-coverage", classifier,
                                                  "HYBRID_MINORITY", metric)
                            right = self.per_split(rows, "combined/random", classifier,
                                                   "HYBRID_MINORITY", metric)
                        elif name == "QC_minus_real_only":
                            left = self.per_split(rows, "combined/quality-coverage", classifier,
                                                  "HYBRID_MINORITY", metric)
                            right = real
                        else:
                            candidates = {}
                            for method in AUGMENTATIONS:
                                values = self.per_split(rows, method, classifier, "HYBRID_MINORITY",
                                                        metric)
                                if len(values) == 5 and all(v is not None for v in values.values()):
                                    candidates[method] = values
                            if candidates:
                                # Optimistic by construction: chosen on the same TEST splits.
                                chosen = max(candidates, key=lambda m: (
                                    mean(v for v in candidates[m].values() if v is not None), m))
                                left = candidates[chosen]
                            else:
                                left = {}
                            right = real
                        diffs = {s: float(a)-float(b) for s, a in sorted(left.items())
                                 if (b := right.get(s)) is not None and a is not None}
                        values = list(diffs.values())
                        entries[dataset] = {
                            "status": "ok" if values else "unavailable",
                            "reason": None if values else "NO_PAIRED_AVAILABLE_SPLIT",
                            "paired_splits": len(values),
                            "mean_difference": mean(values) if values else None,
                            "per_split": diffs, "best_method": chosen,
                            "wins": sum(v > 0 for v in values), "ties": sum(v == 0 for v in values),
                            "losses": sum(v < 0 for v in values)}
                    means = [e["mean_difference"] for e in entries.values() if e["status"] == "ok"]
                    test: dict[str, Any] = {"n_datasets": len(means),
                                            "excluded": [d for d, e in entries.items()
                                                         if e["status"] != "ok"]}
                    if len(means) >= 2 and any(m != 0 for m in means):
                        statistic, p_value = cast(tuple[Any, Any], wilcoxon(
                            means, alternative="two-sided", zero_method="wilcox", method="auto"))
                        test.update(statistic=float(statistic), p_value=float(p_value))
                    else:
                        test.update(statistic=None, p_value=None, reason="INSUFFICIENT_NONZERO_DIFFERENCES")
                    comparisons[key] = {
                        "datasets": entries, "wilcoxon": test,
                        "datasets_positive_mean": sum(m > 0 for m in means),
                        "datasets_negative_mean": sum(m < 0 for m in means),
                        "datasets_zero_mean": sum(m == 0 for m in means),
                        "total_wins": sum(e.get("wins", 0) for e in entries.values()),
                        "total_ties": sum(e.get("ties", 0) for e in entries.values()),
                        "total_losses": sum(e.get("losses", 0) for e in entries.values()),
                        "median_dataset_mean_difference": sorted(means)[len(means)//2]
                        if len(means) % 2 else (mean(sorted(means)[len(means)//2-1:len(means)//2+1])
                                                if means else None)}
        return {"per_dataset": per_dataset, "comparisons": comparisons,
                "interpretation": "Exploratory; Wilcoxon p-values carry no multiplicity adjustment "
                "and no significance claim. best_augmentation is selected on the same TEST splits."}

    def canonical_populations(self) -> list[dict[str, Any]]:
        return load(RUN_V2/"populations.json")

    # ---- outputs ----------------------------------------------------------------------------
    def summary(self) -> dict[str, Any]:
        manifest = load(self.run/"manifest.json")
        return {"label": LABEL,
                "inputs": {"run_manifest_sha256": sha(self.run/"manifest.json"),
                           "run_results_sha256": sha(self.run/"results.json"),
                           "run_v2_results_sha256": sha(RUN_V2/"results.json"),
                           "addendum_protocol_sha256": sha(ROOT/"configs/empirical/addendum-v1.json")},
                "run": {k: manifest[k] for k in ["status_counts", "rows_by_track",
                                                 "declaration_commit", "implementation_revision",
                                                 "reproduction_rows",
                                                 "reproduction_all_selected_ids_match",
                                                 "reproduction_max_abs_metric_difference"]},
                "unavailable": self.unavailable,
                "E1": self.e1(),
                "E1_repair": {"repairs": self.repairs,
                              "pools": [p for p in self.pools if p["track"] == "E1-repair"],
                              "rows": dict(Counter(r["status"] for r in self.rows
                                                   if r["track"] == "E1-repair")),
                              "constructions": [
                                  {k: c[k] for k in ("dataset_id", "split_seed", "method", "budget",
                                                     "budget_achieved", "status", "reason")}
                                  for c in self.constructions if c["track"] == "E1-repair"],
                              "ok_rows_by_split": {str(k): v for k, v in Counter(
                                  r["split_seed"] for r in self.rows if r["track"] == "E1-repair"
                                  and r["status"] == "ok").items()},
                              "not_applicable": [u["dataset_id"] for u in self.unavailable
                                                 if u["track"] == "E1-repair"
                                                 and u["status"] == "not_applicable"]},
                "E2_E3": self.e2_e3(), "E4": self.e4()}


def markdown(s: dict[str, Any], conclusion: str) -> str:
    lines = ["# RC-QASyn exploratory addendum v1", "",
             (f"> **{LABEL}** Settings were committed in `configs/empirical/addendum-v1.json` "
             f"(commit `{s['run']['declaration_commit'][:7]}`) before any score; one execution "
             f"(implementation `{s['run']['implementation_revision'][:7]}`). Every row is counted, "
             "including unavailable rows. No significance or state-of-the-art claim."), "",
             f"Rows: {s['run']['rows_by_track']}; status {s['run']['status_counts']}.", ""]
    # E1
    lines += ["## E1: fresh-split curation on new datasets (HYBRID_MINORITY, five splits)", "",
              ("Mean over completed splits. QC = combined/quality-coverage; AR = combined/random "
              "(admitted random); Real = REAL_TRAIN. Coverage = TRAIN distinct-feature coverage at "
              "0.05; Near = near-duplicate rate at 0.01."), "",
              ("| Dataset | b | gen | noncompliant/pool | QC cov | AR cov | QC near | AR near | "
              "LR F1 Real / QC / AR | RF F1 Real / QC / AR |"),
              "|---|---|---|---|---|---|---|---|---|---|"]
    for dataset, e in s["E1"].items():
        if e.get("status") == "unavailable":
            lines.append(f"| {dataset} | - | - | - | unavailable: {e['reason'][:60]}... | | | | | |")
            continue
        budgets = sorted({p["budget"] for p in e["pools"]})
        nonc = sum(p["generated_noncompliant_n"] for p in e["pools"])
        total = sum(p["candidates_n"] for p in e["pools"])
        g = e["geometry"]
        u = e["utility"]

        def f1(method: str, classifier: str, regime: str = "HYBRID_MINORITY",
               u: dict[str, Any] = u) -> str:
            cell = u.get(f"{method}|{classifier}|{regime}")
            if not cell or not cell["completed"]:
                return "n/a"
            return fmt(cell["f1"]["mean"]) + ("" if cell["completed"] == cell["splits"]
                                              else f"({cell['completed']}/{cell['splits']})")
        lines.append(
            f"| {dataset} | {'/'.join(map(str, budgets))} | {e['pools'][0]['generator']} | "
            f"{nonc}/{total} | {fmt(g['combined/quality-coverage']['unique_train_feature_coverage']['mean'])} | "
            f"{fmt(g['combined/random']['unique_train_feature_coverage']['mean'])} | "
            f"{fmt(g['combined/quality-coverage']['near_duplicate_rate']['mean'])} | "
            f"{fmt(g['combined/random']['near_duplicate_rate']['mean'])} | "
            + " / ".join([f1("REAL_TRAIN", "logistic_regression", "TRTR"),
                          f1("combined/quality-coverage", "logistic_regression"),
                          f1("combined/random", "logistic_regression")]) + " | "
            + " / ".join([f1("REAL_TRAIN", "random_forest", "TRTR"),
                          f1("combined/quality-coverage", "random_forest"),
                          f1("combined/random", "random_forest")]) + " |")
    lines += ["", "TSTR is unavailable for every E1 curator (minority-only pools hold one class).", ""]
    # E1-repair
    r = s["E1_repair"]
    lines += ["## E1-repair: bounded repair of fresh pools", "",
              ("| Dataset | split | repair eligible / candidates | schema pool after repair | b | "
              "constructions reaching b | utility rows ok (shortfall) |"),
              "|---|---|---|---|---|---|---|"]
    for rep, pool in zip(r["repairs"], r["pools"], strict=True):
        split = [x for x in r["constructions"] if x["split_seed"] == rep["split_seed"]]
        lines.append(f"| {rep['dataset_id']} | {rep['split_seed']} | "
                     f"{rep['outcomes'].get('REPAIR_ELIGIBLE', 0)} / {rep['candidates_n']} | "
                     f"{pool['schema_pool_n']} | {pool['budget']} | "
                     f"{sum(x['status'] == 'ok' for x in split)}/{len(split)} | "
                     f"{r['ok_rows_by_split'].get(str(rep['split_seed']), 0)} |")
    lines += ["", (f"E1-repair utility rows: {r['rows']}. Every E1-repair construction fell short "
                   "of b, so its ok utility rows train on 2-4 repaired records instead of b and are "
                   "MATCHED_BUDGET_SHORTFALL, not matched-budget results. Not applicable (no "
                   f"integer-declared features, repair NOT_NEEDED): {', '.join(r['not_applicable'])}."),
              ""]
    # E2 / E3
    lines += ["## E2 and E3: historical Track A at fixed budgets", "",
              ("QC = canonical quality-coverage (quota 0.5b); QC-ratio = E2 quota floor(b x TRAIN "
              "minority fraction); AR = admitted random (mean of 5 seeds); B2 = E3 random subsets of "
              "the B2-accepted complete pool (mean of 5 seeds). Same-environment re-scores."), "",
              ("| Dataset | Design | quota | minority selected | cov | near | exact | "
              "LR TSTR F1 | LR HYB F1 | RF TSTR F1 | RF HYB F1 | LR HYB AP | LR HYB MCC |"),
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for dataset, e in s["E2_E3"].items():
        for label, key in [("QC", "canonical_quality_coverage_same_environment"),
                           ("QC-ratio (E2)", "E2_real_ratio_quality_coverage"),
                           ("AR x5", "canonical_admitted_random_same_environment"),
                           ("B2 x5 (E3)", "E3_b2_accepted_random")]:
            x = e[key]
            u = x["utility"]
            minority = [c.get("positive", 0) for c in x["label_counts"]]
            quota = x["minority_quota_requested"][0] if x["minority_quota_requested"][0] is not None else "-"

            def cell(k: str, metric: str = "f1", u: dict[str, Any] = u) -> str:
                c = u[k]
                text = fmt(c[metric]["mean"])
                return text if c["completed"] == c["rows"] else f"{text} ({c['completed']}/{c['rows']})"
            lines.append(
                f"| {dataset} | {label} | {quota} | {'/'.join(map(str, minority))} | "
                f"{fmt(x['unique_train_feature_coverage']['mean'])} | "
                f"{fmt(x['near_duplicate_rate']['mean'])} | {fmt(x['exact_duplicate_rate']['mean'])} | "
                f"{cell('logistic_regression|TSTR')} | {cell('logistic_regression|HYBRID_MINORITY')} | "
                f"{cell('random_forest|TSTR')} | {cell('random_forest|HYBRID_MINORITY')} | "
                f"{cell('logistic_regression|HYBRID_MINORITY', 'average_precision')} | "
                f"{cell('logistic_regression|HYBRID_MINORITY', 'mcc')} |")
    lines += ["", "Pools: " + "; ".join(
        f"{d}: combined-review {e['pool']['combined_review_pool_n']}, B2-accepted complete "
        f"{e['pool']['b2_accepted_complete_pool_n']}, TRAIN minority fraction "
        f"{e['pool']['train_minority_fraction']:.4f}" for d, e in s["E2_E3"].items()) + ".",
        (f"Same-environment re-scoring of canonical comparators: selected records identical "
        f"({s['run']['reproduction_all_selected_ids_match']}); maximum absolute metric difference "
        f"from run-v2 {s['run']['reproduction_max_abs_metric_difference']:.4f} (cross-platform)."), ""]
    # E4
    e4 = s["E4"]
    lines += ["## E4: across-dataset summary (fresh splits)", "",
              ("Dataset-level mean difference over paired splits (W/T/L over splits). Canonical "
              "datasets come from run-v2 Track B unchanged."), "",
              ("| Dataset | TEST pos/split | LR F1 QC-AR | RF F1 QC-AR | LR F1 QC-Real | RF F1 QC-Real | "
              "LR F1 Best-Real (method) | RF F1 Best-Real (method) |"),
              "|---|---|---|---|---|---|---|---|"]
    c = e4["comparisons"]
    for dataset, d in e4["per_dataset"].items():
        if not d["available"]:
            lines.append(f"| {dataset} | - | unavailable | | | | | |")
            continue

        def cmp(name: str, classifier: str, dataset: str = dataset, method: bool = False) -> str:
            x = c[f"{name}|{classifier}|f1"]["datasets"][dataset]
            if x["status"] != "ok":
                return "n/a"
            text = f"{signed(x['mean_difference'])} ({x['wins']}/{x['ties']}/{x['losses']})"
            return text + (f" {x['best_method']}" if method else "")
        positives = "/".join(str(v) for _, v in sorted(d["test_positive_n_by_split"].items()))
        lines.append(f"| {dataset} | {positives} | {cmp('QC_minus_admitted_random', 'logistic_regression')} | "
                     f"{cmp('QC_minus_admitted_random', 'random_forest')} | "
                     f"{cmp('QC_minus_real_only', 'logistic_regression')} | "
                     f"{cmp('QC_minus_real_only', 'random_forest')} | "
                     f"{cmp('best_augmentation_minus_real_only', 'logistic_regression', method=True)} | "
                     f"{cmp('best_augmentation_minus_real_only', 'random_forest', method=True)} |")
    lines += ["", ("| Comparison | Clf | Metric | datasets (+/-/0) | split W/T/L | median diff | "
              "Wilcoxon n, p (exploratory) |"), "|---|---|---|---|---|---|---|"]
    for key, x in c.items():
        name, classifier, metric = key.split("|")
        w = x["wilcoxon"]
        lines.append(f"| {name} | {SHORT[classifier]} | {metric} | "
                     f"{x['datasets_positive_mean']}/{x['datasets_negative_mean']}/{x['datasets_zero_mean']} | "
                     f"{x['total_wins']}/{x['total_ties']}/{x['total_losses']} | "
                     f"{signed(x['median_dataset_mean_difference'])} | "
                     f"{w['n_datasets']}, {fmt(w.get('p_value'), 3)} |")
    lines += ["", "Excluded from QC comparisons: " + ", ".join(sorted({
        d for x in c.values() for d in x["wilcoxon"]["excluded"]})) + ". best_augmentation is "
        "chosen on the same TEST splits and is optimistic by construction.", "",
        "## Conclusion", "", conclusion.strip(), ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--conclusion", type=Path, help="author-written five-sentence conclusion")
    args = parser.parse_args()
    summary = Report(args.run).summary()
    targets = [args.output/"summary.json", args.output/"summary.md"]
    if any(t.exists() for t in targets):
        raise SystemExit("summary outputs exist; write a fresh version instead")
    args.output.mkdir(parents=True, exist_ok=True)
    conclusion = args.conclusion.read_text("utf-8") if args.conclusion else "PENDING_AUTHOR_CONCLUSION"
    summary["conclusion"] = conclusion.strip()
    targets[0].write_text(json.dumps(summary, sort_keys=True, indent=2, allow_nan=False)+"\n", "utf-8")
    targets[1].write_text(markdown(summary, conclusion), "utf-8")


if __name__ == "__main__":
    main()
