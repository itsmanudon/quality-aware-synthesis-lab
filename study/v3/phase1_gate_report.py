# pyright: reportAttributeAccessIssue=false, reportOperatorIssue=false, reportGeneralTypeIssues=false, reportArgumentType=false, reportCallIssue=false, reportReturnType=false
"""Summarize Phase 1 step 3 (quality gate on U2/UGO/SMOTE pools) into committed tables.

Reads ``phase1_u2.py gate`` units plus the step-1 run (for REAL_INNER_TRAIN on the same
inner TRAIN / VALIDATION rows) and writes ``gate.csv``, ``rows.csv`` and ``summary.md``.
Descriptive only; VALIDATION only; no test is run.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

METRICS = ("f1", "average_precision", "mcc")
METHOD_ORDER = ("smote", "kmeans_smote", "rwo", "original_ugo", "u2_native", "u2_flow_gate")


def load_gate(run: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    gates: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for path in sorted((run / "units").glob("*.json")):
        unit = json.loads(path.read_text(encoding="utf-8"))
        key = {"dataset_id": unit["dataset_id"], "split_seed": unit["split_seed"],
               "generator": unit["method"], "budget": unit["budget"]}
        g = unit.get("gate", {})
        repair = g.get("repair_outcomes", {})
        gates.append({**key, "pool_status": unit["pool_status"],
                      "pool_reason": unit.get("pool_reason"),
                      **{k: v for k, v in g.items() if k not in ("repair_outcomes", "label_counts")},
                      "repair_not_needed_n": repair.get("NOT_NEEDED", 0),
                      "repair_eligible_n": repair.get("REPAIR_ELIGIBLE", 0),
                      "repair_other_n": sum(v for k, v in repair.items() if not k.startswith(
                          "reason:") and k not in ("NOT_NEEDED", "REPAIR_ELIGIBLE")),
                      "repair_reasons": json.dumps({k[7:]: v for k, v in repair.items()
                                                    if k.startswith("reason:")}, sort_keys=True)})
        rows.extend({**key, **r} for r in unit["rows"])
    frame = pd.DataFrame(rows)
    if len(frame):
        frame["family"] = frame["method"].str.replace(r"/s\d+$", "", regex=True)
    return pd.DataFrame(gates), frame


def real_rows(step1: Path) -> pd.DataFrame:
    out = []
    for path in sorted((step1 / "units").glob("*__b1.json")):
        unit = json.loads(path.read_text(encoding="utf-8"))
        for r in unit["rows"]:
            if r["method"] in ("REAL_INNER_TRAIN", "SMOTE+b", "SMOTENC+b"):
                out.append({"dataset_id": unit["dataset_id"], "split_seed": unit["split_seed"],
                            **r})
    return pd.DataFrame(out)


def per_dataset(frame: pd.DataFrame, value: str) -> pd.Series:
    keys = ["generator", "dataset_id", "split_seed", "classifier"]
    return frame.groupby(keys)[value].mean().groupby(["generator", "dataset_id",
                                                      "classifier"]).mean()


def diff_table(left: pd.Series, right: pd.Series, title: str) -> list[str]:
    diff = (left - right).dropna()
    lines = [f"## {title}", "",
             "| generator | classifier | median over datasets | datasets > 0 | datasets < 0 | n |",
             "| --- | --- | --- | --- | --- | --- |"]
    for (gen, clf), group in diff.groupby(level=["generator", "classifier"]):
        lines.append(f"| {gen} | {clf} | {group.median():+.4f} | {int((group > 0).sum())} | "
                     f"{int((group < 0).sum())} | {len(group)} |")
    return [*lines, ""]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--step1", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    gates, frame = load_gate(args.run)
    args.out.mkdir(parents=True, exist_ok=True)
    gates.to_csv(args.out / "gate.csv", index=False)
    frame.to_csv(args.out / "rows.csv", index=False)
    g = gates[gates["pool_status"] == "ok"].copy()
    totals = g.groupby("generator")[[
        "pool_n", "structurally_complete_n", "repair_eligible_n", "repair_other_n",
        "exact_duplicate_within_pool_n", "exact_copy_of_inner_train_n",
        "noncategorical_one_hot_n", "schema_admitted_n", "combined_admitted_n"]].sum()
    shortfall = g.assign(short=g["combined_admitted_n"].fillna(0) < g["budget"]).groupby(
        "generator")["short"].sum()
    parts = ["# Phase 1 step 3: RC-QASyn quality gate on U2, UGO and SMOTE-family pools", "",
             ("Pools exported by `u2_pools.py` (pinned ml_ugo, unmodified samplers, in-loop "
              "learner = U2 logistic regression at default parameters) on the same inner TRAIN "
              "/ VALIDATION rows as step 1; target = minority + 4 x budget. Gate = frozen "
              "rcqasyn checks. Exact-copy counts are copying diagnostics, not privacy results. "
              "VALIDATION only; descriptive only."), "",
             "## Gate totals over 8 dev datasets x 5 splits", "",
             ("| generator | candidates | structurally incomplete | repair-eligible | "
              "not repairable | duplicate within pool | exact copy of inner TRAIN | "
              "non-one-hot categorical | schema-admitted | combined-admitted (q=0.90) | "
              "splits with pool < budget |"),
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for gen in [m for m in METHOD_ORDER if m in totals.index]:
        t = totals.loc[gen]
        n = int(t["pool_n"])

        def pct(v: float, n: int = n) -> str:
            return f"{int(v)} ({100 * v / n:.1f}%)" if n else f"{int(v)}"
        parts.append(f"| {gen} | {n} | {pct(n - t['structurally_complete_n'])} | "
                     f"{pct(t['repair_eligible_n'])} | {pct(t['repair_other_n'])} | "
                     f"{pct(t['exact_duplicate_within_pool_n'])} | "
                     f"{pct(t['exact_copy_of_inner_train_n'])} | "
                     f"{pct(t['noncategorical_one_hot_n'])} | {pct(t['schema_admitted_n'])} | "
                     f"{pct(t['combined_admitted_n'])} | {int(shortfall.get(gen, 0))} of "
                     f"{int((g['generator'] == gen).sum())} |")
    by_ds = g.groupby(["dataset_id", "generator"])[["pool_n", "structurally_complete_n",
                                                    "combined_admitted_n"]].sum()
    parts += ["", ("## Per dataset (sum over 5 splits): candidates / structurally complete / "
                   "combined-admitted"), "",
              "| dataset | " + " | ".join(METHOD_ORDER) + " |",
              "| --- |" + " --- |" * len(METHOD_ORDER)]
    for dataset in sorted(g["dataset_id"].unique()):
        cells = []
        for gen in METHOD_ORDER:
            if (dataset, gen) in by_ds.index:
                r = by_ds.loc[(dataset, gen)]
                cells.append(f"{int(r['pool_n'])} / {int(r['structurally_complete_n'])} / "
                             f"{int(r['combined_admitted_n'])}")
            else:
                cells.append("-")
        parts.append(f"| {dataset} | " + " | ".join(cells) + " |")
    ok = frame[frame["status"] == "ok"] if len(frame) else frame
    if len(ok):
        real = real_rows(args.step1)
        real_ok = real[(real["method"] == "REAL_INNER_TRAIN") & (real["status"] == "ok")]
        real_ds = real_ok.groupby(["dataset_id", "split_seed", "classifier"])["f1"].mean() \
            .groupby(["dataset_id", "classifier"]).mean()
        qc = per_dataset(ok[ok["family"] == "combined/quality-coverage"], "f1")
        rnd = per_dataset(ok[ok["family"] == "combined/random"], "f1")
        parts += ["", *diff_table(qc, rnd, "F1: combined/quality-coverage minus combined/random, "
                                            "per generator pool")]
        rnd_vs_real = rnd.reset_index().merge(real_ds.rename("real").reset_index(),
                                              on=["dataset_id", "classifier"])
        rnd_vs_real = rnd_vs_real.set_index(["generator", "dataset_id", "classifier"])
        parts += diff_table(rnd_vs_real["f1"], rnd_vs_real["real"],
                            "F1: combined/random from each generator pool minus REAL_INNER_TRAIN")
        qc_vs_real = qc.reset_index().merge(real_ds.rename("real").reset_index(),
                                            on=["dataset_id", "classifier"])
        qc_vs_real = qc_vs_real.set_index(["generator", "dataset_id", "classifier"])
        parts += diff_table(qc_vs_real["f1"], qc_vs_real["real"],
                            "F1: combined/quality-coverage from each generator pool minus "
                            "REAL_INNER_TRAIN")
    not_ok = frame[frame["status"] != "ok"] if len(frame) else frame
    parts += [f"## Curator rows not ok: {len(not_ok)}", ""]
    if len(not_ok):
        counts = not_ok.groupby(["generator", "dataset_id", "status", "reason"]).size()
        parts += [f"- {k}: {v}" for k, v in counts.items()]
    failed = gates[gates["pool_status"] != "ok"]
    parts += ["", f"## Pools not ok: {len(failed)}", ""]
    parts += [f"- {r.dataset_id} s{r.split_seed} {r.generator}: {r.pool_reason}"
              for r in failed.itertuples()]
    (args.out / "summary.md").write_text("\n".join(parts) + "\n", encoding="utf-8")
    print("\n".join(parts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
