# pyright: reportAttributeAccessIssue=false, reportOperatorIssue=false, reportGeneralTypeIssues=false, reportArgumentType=false, reportCallIssue=false
"""Summarise a ``phase2.py run``: pool the 5 cross-fit folds, then compare selection designs.

Per (dataset, split seed, method, classifier) the held-out scores of the 5 folds are pooled
(``crossfit.pooled_scores``): F1/MCC at the cross-fitted threshold (primary, as U2 selects
thresholds on validation), F1 at 0.5, mean per-fold AP. A cell is unavailable unless all 5
folds produced the method. Comparisons are paired within dataset x split x classifier,
averaged over the 5 split seeds, then summarised over datasets (median, counts above and
below zero). ``random`` is the mean of the 5 random selection seeds of the same pool.

Tuning-stability check: designs are ranked by their median gain over random on split seeds
{13, 29} and, separately, on {43, 61, 79}; the Spearman correlation of the two rankings says
whether the ordering is reproducible or noise. Descriptive only; dev data; no TEST.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .crossfit import K_FOLDS, pooled_scores

HALVES = ((13, 29), (43, 61, 79))


def cells(run: Path) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    folds: dict[tuple[str, int], dict[int, dict[str, Any]]] = defaultdict(dict)
    for path in sorted((run / "units").glob("*.json")):
        unit = json.loads(path.read_text(encoding="utf-8"))
        folds[(unit["dataset_id"], unit["split_seed"])][unit["fold"]] = unit
    rows: list[dict[str, Any]] = []
    pool_rows: list[dict[str, Any]] = []
    for (dataset, seed), by_fold in sorted(folds.items()):
        if sorted(by_fold) != list(range(K_FOLDS)):
            continue
        keys = set().union(*(u["scores"] for u in by_fold.values()))
        for key in sorted(keys):
            method, classifier = key.split("|")
            if not all(key in u["scores"] for u in by_fold.values()):
                rows.append({"dataset_id": dataset, "split_seed": seed, "method": method,
                             "classifier": classifier, "status": "unavailable"})
                continue
            pooled = pooled_scores([{"y": by_fold[f]["heldout_y"],
                                     "score": by_fold[f]["scores"][key]}
                                    for f in range(K_FOLDS)])
            rows.append({"dataset_id": dataset, "split_seed": seed, "method": method,
                         "classifier": classifier, "status": "ok",
                         **{k: pooled[k] for k in ("f1", "f1_default", "mcc", "mcc_default",
                                                   "average_precision", "minority_recall",
                                                   "minority_n")}})
        # A design that never produced scores (e.g. an empty pool, MATCHED_BUDGET_SHORTFALL)
        # has no score key at all; list it so a missing dataset is never silently dropped.
        reasons: dict[str, set[str]] = defaultdict(set)
        for unit in by_fold.values():
            for row in unit.get("rows", []):
                if row.get("status") != "ok" and row.get("method"):
                    reasons[row["method"]].add(str(row.get("reason")))
        for unit in by_fold.values():
            for name, info in unit.get("pools", {}).items():
                if info.get("candidates_n") == 0:
                    reasons[f"{name}/*"].add("EMPTY_POOL")
        scored = {k.split("|")[0] for k in keys}
        for method, why in sorted(reasons.items()):
            if method.endswith("/*") and any(s.startswith(method[:-1]) for s in scored):
                continue
            if method not in scored:
                rows.append({"dataset_id": dataset, "split_seed": seed, "method": method,
                             "classifier": "*", "status": "unavailable",
                             "reason": ";".join(sorted(why))})
        for fold, unit in by_fold.items():
            for name, info in unit["pools"].items():
                pool_rows.append({"dataset_id": dataset, "split_seed": seed, "fold": fold,
                                  "pool": name, "budget": unit["budget"],
                                  **{k: v for k, v in info.items()
                                     if not isinstance(v, dict)},
                                  **({f"repair_{k}": v for k, v in
                                      info["repair"]["outcomes"].items()}
                                     if "repair" in info else {})})
    return pd.DataFrame(rows), pool_rows


def paired(frame: pd.DataFrame, metric: str) -> pd.DataFrame:
    """Per dataset x split x classifier: each design minus its pool's random mean, QC, REAL."""
    ok = frame[frame["status"] == "ok"].copy()
    ok["pool"] = ok["method"].str.split("/").str[0]
    ok.loc[~ok["method"].str.contains("/"), "pool"] = ""
    wide = ok.pivot_table(index=["dataset_id", "split_seed", "classifier"], columns="method",
                          values=metric)
    out = []
    for pool in sorted(p for p in ok["pool"].unique() if p):
        random_cols = [c for c in wide.columns if c.startswith(f"{pool}/random/")]
        if not random_cols:
            continue
        random_mean = wide[random_cols].mean(axis=1, skipna=False)
        qc = wide.get(f"{pool}/quality-coverage")
        for design in (c for c in wide.columns if c.startswith(pool + "/")
                       and "/random/" not in c):
            values = wide[design]
            out.append(pd.DataFrame({
                "pool": pool, "design": design.split("/", 1)[1], "value": values,
                "minus_random": values - random_mean,
                "minus_qc": values - qc if qc is not None else np.nan,
                "minus_real": values - wide["REAL_INNER_TRAIN"]}).reset_index())
        out.append(pd.DataFrame({"pool": pool, "design": "random(mean of 5)",
                                 "value": random_mean, "minus_random": 0.0,
                                 "minus_qc": random_mean - qc if qc is not None else np.nan,
                                 "minus_real": random_mean - wide["REAL_INNER_TRAIN"]}
                                ).reset_index())
    for reference in [c for c in wide.columns if "/" not in c and c != "REAL_INNER_TRAIN"]:
        out.append(pd.DataFrame({"pool": "", "design": reference, "value": wide[reference],
                                 "minus_random": np.nan, "minus_qc": np.nan,
                                 "minus_real": wide[reference] - wide["REAL_INNER_TRAIN"]}
                                ).reset_index())
    return pd.concat(out, ignore_index=True)


def summary(diffs: pd.DataFrame, seeds: tuple[int, ...] | None = None) -> pd.DataFrame:
    data = diffs if seeds is None else diffs[diffs["split_seed"].isin(seeds)]
    per_ds = data.groupby(["pool", "design", "classifier", "dataset_id"])[
        ["value", "minus_random", "minus_qc", "minus_real"]].mean()
    grouped = per_ds.groupby(level=["pool", "design", "classifier"])
    result = grouped.median().add_prefix("median_")
    for column in ("minus_random", "minus_real"):
        result[f"{column}_pos"] = grouped[column].apply(lambda v: int((v > 0).sum()))
        result[f"{column}_neg"] = grouped[column].apply(lambda v: int((v < 0).sum()))
    result["datasets"] = grouped["value"].count()
    return result.reset_index()


def stability(diffs: pd.DataFrame) -> list[dict[str, Any]]:
    out = []
    a, b = (summary(diffs, h) for h in HALVES)
    merged = a.merge(b, on=["pool", "design", "classifier"], suffixes=("_a", "_b"))
    merged = merged[merged["design"] != "random(mean of 5)"]
    for (pool, classifier), group in merged.groupby(["pool", "classifier"]):
        if not pool or len(group) < 3:
            continue
        rho = group["median_minus_random_a"].rank().corr(group["median_minus_random_b"].rank())
        out.append({"pool": pool, "classifier": classifier, "designs": len(group),
                    "spearman_halves": None if pd.isna(rho) else float(rho)})
    return out


def report(run: Path, out: Path) -> str:
    frame, pool_rows = cells(run)
    out.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out / "cells.csv", index=False)
    pools = pd.DataFrame(pool_rows)
    pools.to_csv(out / "pools.csv", index=False)
    lines = ["# Phase 2: utility-aware selection on dev data (5-fold cross-fit inside TRAIN)",
             "",
             ("Pooled over the 5 held-out folds of each outer TRAIN; F1 at the cross-fitted "
              "threshold (each fold's threshold chosen on the other 4 folds, U2's rule). "
              "Differences are paired per dataset x split x classifier, averaged over the 5 "
              "split seeds, then the median over datasets (with counts above / below zero). "
              "`random` = mean of 5 random selections from the same admitted pool. "
              "Descriptive only; dev data; TEST never used."), ""]
    tables: dict[str, pd.DataFrame] = {}
    for metric in ("f1", "f1_default", "mcc", "average_precision"):
        diffs = paired(frame, metric)
        diffs.to_csv(out / f"diffs_{metric}.csv", index=False)
        tables[metric] = summary(diffs)
        tables[metric].to_csv(out / f"summary_{metric}.csv", index=False)
    f1 = tables["f1"]
    for pool in sorted(p for p in f1["pool"].unique() if p):
        lines += [f"## Pool `{pool}`: F1 (cross-fitted threshold)", "",
                  ("| design | classifier | median F1 | minus random | +/- | minus QC | "
                   "minus REAL | +/- | datasets |"),
                  "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for r in f1[f1["pool"] == pool].sort_values(["classifier", "design"]).itertuples():
            lines.append(
                f"| {r.design} | {r.classifier} | {r.median_value:.4f} | "
                f"{r.median_minus_random:+.4f} | {r.minus_random_pos}/{r.minus_random_neg} | "
                f"{r.median_minus_qc:+.4f} | {r.median_minus_real:+.4f} | "
                f"{r.minus_real_pos}/{r.minus_real_neg} | {r.datasets} |")
        lines.append("")
    refs = f1[f1["pool"] == ""]
    lines += ["## References minus REAL_INNER_TRAIN (F1, cross-fitted threshold)", "",
              "| method | classifier | median F1 | minus REAL | +/- | datasets |",
              "| --- | --- | --- | --- | --- | --- |"]
    for r in refs.sort_values(["design", "classifier"]).itertuples():
        lines.append(f"| {r.design} | {r.classifier} | {r.median_value:.4f} | "
                     f"{r.median_minus_real:+.4f} | {r.minus_real_pos}/{r.minus_real_neg} | "
                     f"{r.datasets} |")
    real = frame[(frame["method"] == "REAL_INNER_TRAIN") & (frame["status"] == "ok")]
    real_med = real.groupby(["classifier", "dataset_id"])["f1"].mean().groupby(
        "classifier").median()
    lines += ["", "REAL_INNER_TRAIN median F1: " +
              ", ".join(f"{k} {v:.4f}" for k, v in real_med.items()), ""]
    stab = stability(paired(frame, "f1"))
    (out / "stability.json").write_text(json.dumps(stab, indent=1), encoding="utf-8")
    lines += ["## Tuning stability (split seeds {13, 29} vs {43, 61, 79})", "",
              ("Spearman correlation of the design rankings (median F1 minus random) between "
               "the two halves of the split seeds. Near 0 or negative: the ordering is noise."),
              "", "| pool | classifier | designs | Spearman |", "| --- | --- | --- | --- |"]
    lines += [f"| {s['pool']} | {s['classifier']} | {s['designs']} | "
              f"{'' if s['spearman_halves'] is None else format(s['spearman_halves'], '+.2f')} |"
              for s in stab]
    unavailable = frame[frame["status"] != "ok"]
    lines += ["", f"## Unavailable cells: {len(unavailable)}", ""]
    if len(unavailable):
        if "reason" not in unavailable.columns:
            unavailable = unavailable.assign(reason="")
        counts = unavailable.fillna({"reason": ""}).groupby(
            ["dataset_id", "method", "reason"]).size()
        lines += [f"- {d} {m}: {n}" + (f" ({r})" if r else "")
                  for (d, m, r), n in counts.items()]
    if not pools.empty:
        agg = pools.groupby(["dataset_id", "pool"]).sum(numeric_only=True)
        # phase2.py names the counts schema_n / combined_n; phase2_llm.py *_admitted_n
        schema = "schema_n" if "schema_n" in agg.columns else "schema_admitted_n"
        combined = "combined_n" if "combined_n" in agg.columns else "combined_admitted_n"
        copies = [c for c in ("exact_copy_of_inner_train_n", "exact_copy_of_reference_n",
                              "exact_duplicate_within_pool_n") if c in agg.columns]
        splits = pools.groupby("dataset_id")["split_seed"].nunique().max()
        lines += ["", f"## Pools (summed over {splits} split(s) x 5 folds)", "",
                  ("| dataset | pool | candidates | schema | combined admitted | budget sum |"
                   + "".join(f" {c.removesuffix('_n').replace('_', ' ')} |" for c in copies)),
                  "| --- | --- | --- | --- | --- | --- |" + " --- |" * len(copies)]
        for (d, p), r in agg.iterrows():
            lines.append(f"| {d} | {p} | {int(r['candidates_n'])} | {int(r[schema])} | "
                         f"{int(r[combined])} | {int(r['budget'])} |"
                         + "".join(f" {int(r[c])} |" for c in copies))
        repair_cols = [c for c in pools.columns if c.startswith("repair_")]
        if repair_cols:
            rep = pools[pools["pool"].str.endswith("+round")].groupby(
                ["dataset_id", "pool"])[repair_cols].sum()
            lines += ["", "## Repair variant integer-round-all-half-even-v3", ""]
            for (d, p), r in rep.iterrows():
                parts = ", ".join(f"{c.removeprefix('repair_')} {int(v)}"
                                  for c, v in r.items() if v)
                lines.append(f"- {d} {p}: {parts}")
    text = "\n".join(lines) + "\n"
    (out / "summary.md").write_text(text, encoding="utf-8")
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    print(report(args.run, args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
