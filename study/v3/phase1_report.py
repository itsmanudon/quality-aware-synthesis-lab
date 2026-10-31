# pyright: reportAttributeAccessIssue=false, reportOperatorIssue=false, reportGeneralTypeIssues=false
"""Summarize a Phase 1 run directory into committed compact tables (validation only).

Writes ``rows.csv`` (every scored row, including failed/unavailable ones), ``pools.csv`` and
``summary.md`` into the given report directory. Differences are paired within a
(dataset, split, classifier) cell, averaged over the 5 splits, then summarized across
datasets as a median and a count of positive datasets. Descriptive only: no test is run.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

METRICS = ("f1", "average_precision", "mcc")
RANDOM = "combined/random"
QC = "combined/quality-coverage"


def load(runs: list[Path]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    pools: list[dict[str, Any]] = []
    for path in sorted(p for run in runs for p in (run / "units").glob("*.json")):
        unit = json.loads(path.read_text(encoding="utf-8"))
        key = {k: unit[k] for k in ("dataset_id", "split_seed", "budget_scale", "budget",
                                    "generator", "validation_minority_n")}
        pools.append({**key, **unit.get("pool", {}), "inner_minority_n": unit["inner_minority_n"],
                      "pool_failure": unit.get("pool_failure")})
        rows.extend({**key, **r} for r in unit["rows"])
    frame = pd.DataFrame(rows)
    # Random curators carry a selection seed suffix; group them as one method family.
    frame["family"] = frame["method"].str.replace(r"/s\d+$", "", regex=True)
    return frame, pd.DataFrame(pools)


def paired(frame: pd.DataFrame, left: str, right: str) -> pd.DataFrame:
    ok = frame[frame["status"] == "ok"]
    keys = ["dataset_id", "budget_scale", "split_seed", "classifier"]
    a = ok[ok["family"] == left].groupby(keys)[list(METRICS)].mean()
    b = ok[ok["family"] == right].groupby(keys)[list(METRICS)].mean()
    diff = (a - b).dropna(how="all")
    return diff.groupby(["dataset_id", "budget_scale", "classifier"]).mean()


def table(diff: pd.DataFrame) -> str:
    lines = [("| budget scale | classifier | metric | median over datasets | datasets > 0 | "
              "datasets < 0 | n |"), "| --- | --- | --- | --- | --- | --- | --- |"]
    for (scale, clf), group in diff.groupby(["budget_scale", "classifier"]):
        for metric in METRICS:
            values = group[metric].dropna()
            lines.append(f"| {scale:g} | {clf} | {metric} | {values.median():+.4f} | "
                         f"{int((values > 0).sum())} | {int((values < 0).sum())} | {len(values)} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--title", default="Phase 1 step 1: QC vs random on validation")
    args = parser.parse_args(argv)
    frame, pools = load(args.run)
    args.out.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.out / "rows.csv", index=False)
    pools.to_csv(args.out / "pools.csv", index=False)
    comparisons = [(QC, RANDOM), (QC, "schema/random"), (RANDOM, "schema/random"),
                   (QC, "REAL_INNER_TRAIN"), (RANDOM, "REAL_INNER_TRAIN"),
                   ("SMOTE+b", "REAL_INNER_TRAIN"), ("SMOTENC+b", "REAL_INNER_TRAIN")]
    parts = [f"# {args.title}", "",
             ("Scored on VALIDATION (stratified 20% of each outer TRAIN); TEST never used. "
              "Paired within dataset x split x classifier, averaged over 5 splits, then the "
              "median across datasets. Random curators are averaged over 5 selection seeds. "
              "Descriptive only; no test is run."), "",
             f"Rows: {len(frame)}; status counts: {frame['status'].value_counts().to_dict()}.",
             ""]
    for left, right in comparisons:
        diff = paired(frame, left, right)
        if diff.empty:
            continue
        parts += [f"## {left} minus {right}", "", table(diff), ""]
        diff.reset_index().to_csv(
            args.out / f"diff__{left.replace('/', '_')}__{right.replace('/', '_')}.csv",
            index=False)
    vmin = pools.groupby("dataset_id")["validation_minority_n"].agg(["min", "max"])
    parts += ["## Validation minority rows per dataset (min-max over splits)", "",
              "| dataset | min | max |", "| --- | --- | --- |"]
    parts += [f"| {d} | {r['min']} | {r['max']} |" for d, r in vmin.iterrows()]
    not_ok = frame[frame["status"] != "ok"]
    parts += ["", f"## Rows not ok: {len(not_ok)}", ""]
    if len(not_ok):
        counts = not_ok.groupby(["dataset_id", "method", "status", "reason"]).size()
        parts += [f"- {k}: {v}" for k, v in counts.items()]
    failures = pools[pools["pool_failure"].notna()]
    parts += ["", f"## Pool failures: {len(failures)}", ""]
    parts += [f"- {r.dataset_id} s{r.split_seed}: {r.pool_failure}" for r in failures.itertuples()]
    (args.out / "summary.md").write_text("\n".join(parts) + "\n", encoding="utf-8")
    print("\n".join(parts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
