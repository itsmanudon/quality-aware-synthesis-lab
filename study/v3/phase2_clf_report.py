# pyright: reportAttributeAccessIssue=false, reportOperatorIssue=false, reportGeneralTypeIssues=false, reportArgumentType=false, reportCallIssue=false
"""Summarise the Phase 2 five-learner check (``u2_crossfit.py`` units). Dev data; no TEST.

Per (dataset, split seed, learner) every design is scored by cross-fitted selection over the
5 folds (pooled F1/MCC). The rounded pools (``<pool>+round``) exist only where integer fields
are declared (vehicle0); as in Phase 3 curation, where they exist they stand in for ``<pool>``
(``pool family``). Differences are paired within dataset x split x learner, averaged over the
5 split seeds, then summarised over datasets per learner (median, counts above / below zero)
and over the five learners (median of the per-learner medians; learners with a positive
median). Descriptive only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

LEARNERS = ("logistic_regression", "random_forest", "xgboost", "mlp", "svm")


def load(units: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in sorted(units.glob("*.json")):
        unit = json.loads(path.read_text(encoding="utf-8"))
        for r in unit["rows"]:
            rows.append({"dataset_id": unit["dataset_id"], "split_seed": unit["split_seed"],
                         "method": r["method"], "classifier": r["classifier"],
                         "f1": r.get("f1"), "mcc": r.get("mcc"),
                         "average_precision": r.get("average_precision")})
    frame = pd.DataFrame(rows)
    rounded = set(frame.loc[frame["method"].str.contains(r"\+round/"), "dataset_id"])
    keep = ~frame["dataset_id"].isin(rounded) | ~frame["method"].str.contains("/") | \
        frame["method"].str.contains(r"\+round/")
    frame = pd.DataFrame(frame[keep])
    frame["method"] = frame["method"].str.replace("+round/", "/", regex=False)
    return frame


def diffs(frame: pd.DataFrame, metric: str) -> pd.DataFrame:
    wide = frame.pivot_table(index=["dataset_id", "split_seed", "classifier"],
                             columns="method", values=metric)
    out = []
    for pool in sorted({m.split("/")[0] for m in wide.columns if "/" in m}):
        random_col, qc_col = f"{pool}/random/s13", f"{pool}/quality-coverage"
        for design in [c for c in wide.columns if c.startswith(pool + "/")]:
            out.append(pd.DataFrame({
                "pool": pool, "design": design.split("/", 1)[1], "value": wide[design],
                "minus_random": wide[design] - wide[random_col],
                "minus_qc": wide[design] - wide[qc_col],
                "minus_real": wide[design] - wide["REAL_INNER_TRAIN"]}).reset_index())
    for ref in [c for c in wide.columns if "/" not in c and c != "REAL_INNER_TRAIN"]:
        out.append(pd.DataFrame({"pool": "", "design": ref, "value": wide[ref],
                                 "minus_random": float("nan"), "minus_qc": float("nan"),
                                 "minus_real": wide[ref] - wide["REAL_INNER_TRAIN"]}
                                ).reset_index())
    return pd.concat(out, ignore_index=True)


def summary(d: pd.DataFrame) -> pd.DataFrame:
    per_ds = d.groupby(["pool", "design", "classifier", "dataset_id"])[
        ["value", "minus_random", "minus_qc", "minus_real"]].mean()
    g = per_ds.groupby(level=["pool", "design", "classifier"])
    s = g.median().add_prefix("median_")
    for c in ("minus_random", "minus_qc", "minus_real"):
        s[f"{c}_pos"] = g[c].apply(lambda v: int((v > 0).sum()))
        s[f"{c}_neg"] = g[c].apply(lambda v: int((v < 0).sum()))
    s["datasets"] = g["value"].count()
    return s.reset_index()


def report(units: Path, out: Path) -> str:
    frame = load(units)
    out.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out / "cells.csv", index=False)
    lines = ["# Phase 2 five-learner check (U2's five learners, cross-fitted selection)", "",
             (f"{frame['dataset_id'].nunique()} dev datasets x "
              f"{frame['split_seed'].nunique()} split seeds x 5 folds. Pool family: the rounded "
              "pool stands in where integer fields are declared (vehicle0). Medians over "
              "datasets of per-dataset means over split seeds; counts are datasets above / "
              "below zero. Descriptive only; dev data; TEST never used."), ""]
    for metric in ("f1", "mcc"):
        s = summary(diffs(frame, metric))
        s.to_csv(out / f"summary_{metric}.csv", index=False)
        lines += [f"## {metric.upper()}: designs minus random / QC / REAL, per learner", "",
                  ("| pool | design | learner | median | minus random | +/- | minus QC | +/- "
                   "| minus REAL | +/- |"),
                  "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for r in s.sort_values(["pool", "design", "classifier"]).itertuples():
            lines.append(
                f"| {r.pool or '-'} | {r.design} | {r.classifier} | {r.median_value:.4f} | "
                f"{r.median_minus_random:+.4f} | {r.minus_random_pos}/{r.minus_random_neg} | "
                f"{r.median_minus_qc:+.4f} | {r.minus_qc_pos}/{r.minus_qc_neg} | "
                f"{r.median_minus_real:+.4f} | {r.minus_real_pos}/{r.minus_real_neg} |")
        across = s[s["pool"] != ""].groupby(["pool", "design"]).agg(
            learners=("classifier", "nunique"),
            median_of_medians_minus_random=("median_minus_random", "median"),
            learners_above_random=("median_minus_random", lambda v: int((v > 0).sum())),
            median_of_medians_minus_qc=("median_minus_qc", "median"),
            learners_above_qc=("median_minus_qc", lambda v: int((v > 0).sum())),
            median_of_medians_minus_real=("median_minus_real", "median"),
            learners_above_real=("median_minus_real", lambda v: int((v > 0).sum())))
        across.to_csv(out / f"across_learners_{metric}.csv")
        lines += ["", f"### {metric.upper()} across the five learners", "",
                  ("| pool | design | minus random (median of 5) | learners > 0 | minus QC | "
                   "learners > 0 | minus REAL | learners > 0 |"),
                  "| --- | --- | --- | --- | --- | --- | --- | --- |"]
        for (pool, design), r in across.iterrows():
            lines.append(f"| {pool} | {design} | {r.median_of_medians_minus_random:+.4f} | "
                         f"{int(r.learners_above_random)}/5 | "
                         f"{r.median_of_medians_minus_qc:+.4f} | {int(r.learners_above_qc)}/5 | "
                         f"{r.median_of_medians_minus_real:+.4f} | "
                         f"{int(r.learners_above_real)}/5 |")
        lines.append("")
    text = "\n".join(lines) + "\n"
    (out / "summary.md").write_text(text, encoding="utf-8")
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--units", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    print(report(args.units, args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
