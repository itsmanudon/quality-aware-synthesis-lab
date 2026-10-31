# pyright: reportAttributeAccessIssue=false, reportOperatorIssue=false, reportGeneralTypeIssues=false, reportArgumentType=false, reportCallIssue=false
"""Summaries for Phase 1 step 4 (oracle bound) and the U2 five-classifier ablation.

``oracle``  per dataset x classifier: mean over 5 splits of the random-subset mean F1, the
            in-sample oracle gain (max - mean on full VALIDATION) and the honest gain
            (best on half A, scored on half B, minus mean on B); plus the observed
            QC-minus-random F1 from step 1 for scale.
``clf``     U2's five learners, parameters and threshold chosen on one VALIDATION half and
            scored on the other (2-fold cross-fit, averaged): F1 of each training set minus
            REAL_INNER_TRAIN, and QC minus random, per learner.
Descriptive only; VALIDATION only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


def oracle(run: Path, step1: Path, out: Path) -> str:
    rows: list[dict[str, Any]] = []
    for path in sorted((run / "units").glob("*.json")):
        unit = json.loads(path.read_text(encoding="utf-8"))
        if unit.get("status") != "ok":
            rows.append({"dataset_id": unit["dataset_id"], "split_seed": unit["split_seed"],
                         "status": unit.get("status"), "reason": unit.get("reason")})
            continue
        for clf, s in unit["summary"].items():
            rows.append({"dataset_id": unit["dataset_id"], "split_seed": unit["split_seed"],
                         "status": "ok", "classifier": clf, "k": unit["k"],
                         "half_minority": unit["half_minority"], **s})
    frame = pd.DataFrame(rows)
    out.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out / "oracle.csv", index=False)
    step1_rows = pd.read_csv(step1 / "diff__combined_quality-coverage__combined_random.csv")
    observed = step1_rows[step1_rows["budget_scale"] == 1].set_index(
        ["dataset_id", "classifier"])["f1"]
    ok = frame[frame["status"] == "ok"]
    agg = ok.groupby(["dataset_id", "classifier"])[[
        "mean_full", "sd_full", "in_sample_gain", "honest_gain"]].mean()
    lines = ["# Phase 1 step 4: oracle upper bound for selection from the admitted SMOTE pool",
             "",
             ("K = 100 random budget-sized subsets of the combined admitted pool per split; "
              "HYBRID_MINORITY scored on VALIDATION. In-sample gain = best minus mean F1 on full "
              "validation (optimistic by construction). Honest gain = subset chosen on "
              "validation half A, scored on half B, minus mean B F1. Means over 5 splits. "
              "Observed = step-1 QC minus random F1 (1x budget). Descriptive only."), "",
             ("| dataset | classifier | random mean F1 | SD across subsets | in-sample gain | "
              "honest gain | observed QC - random |"),
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for (dataset, clf), r in agg.iterrows():
        obs = observed.get((dataset, clf))
        lines.append(f"| {dataset} | {clf} | {r['mean_full']:.4f} | {r['sd_full']:.4f} | "
                     f"{r['in_sample_gain']:+.4f} | {r['honest_gain']:+.4f} | "
                     f"{'' if obs is None or pd.isna(obs) else f'{obs:+.4f}'} |")
    med = agg.groupby("classifier")[["in_sample_gain", "honest_gain"]].median()
    lines += ["", "Median over datasets:", ""]
    lines += [f"- {clf}: in-sample {r['in_sample_gain']:+.4f}, honest {r['honest_gain']:+.4f}"
              for clf, r in med.iterrows()]
    skipped = frame[frame["status"] != "ok"]
    lines += ["", f"Units not ok: {len(skipped)}"]
    lines += [f"- {r.dataset_id} s{r.split_seed}: {r.reason}" for r in skipped.itertuples()]
    text = "\n".join(lines) + "\n"
    (out / "summary.md").write_text(text, encoding="utf-8")
    return text


def clf(run: Path, out: Path) -> str:
    rows: list[dict[str, Any]] = []
    unavailable: list[str] = []
    for path in sorted((run / "units").glob("*.json")):
        unit = json.loads(path.read_text(encoding="utf-8"))
        rows.extend({"dataset_id": unit["dataset_id"], "split_seed": unit["split_seed"], **r}
                    for r in unit["rows"])
        unavailable += [f"{unit['dataset_id']} s{unit['split_seed']} {m}: {why}"
                        for m, why in unit["unavailable"].items()]
    frame = pd.DataFrame(rows)
    out.mkdir(parents=True, exist_ok=True)
    frame.drop(columns=["selected_parameters"]).to_csv(out / "rows.csv", index=False)
    frame["family"] = frame["method"].str.replace(r"/s\d+$", "", regex=True)
    frame.loc[frame["family"].isin(["SMOTE+b", "SMOTENC+b"]), "family"] = "SMOTE(NC)+b"
    cell = frame.groupby(["family", "dataset_id", "split_seed", "classifier"])[
        ["f1", "average_precision", "mcc"]].mean()
    per_ds = cell.groupby(["family", "dataset_id", "classifier"]).mean()
    lines = ["# Phase 1: U2's five learners on dev VALIDATION (2-fold cross-fit over halves)",
             "",
             ("Parameters (U2 search spaces, 10 candidates, default first) and the F1 threshold "
              "chosen on one validation half, scored on the other, then swapped and averaged. "
              "No outer refit, no TEST. Training sets from the step-1 SMOTE pool. Paired per "
              "dataset x split x learner, averaged over 5 splits; median over datasets. "
              "Descriptive only."), ""]

    def table(left: str, right: str) -> None:
        a = per_ds.loc[left]
        b = per_ds.loc[right]
        diff = (a - b).dropna(how="all")
        lines.extend([f"## {left} minus {right}", "",
                      "| learner | metric | median over datasets | datasets > 0 | datasets < 0 | n |",
                      "| --- | --- | --- | --- | --- | --- |"])
        for learner, group in diff.groupby(level="classifier"):
            for metric in ("f1", "average_precision", "mcc"):
                v = group[metric].dropna()
                lines.append(f"| {learner} | {metric} | {v.median():+.4f} | "
                             f"{int((v > 0).sum())} | {int((v < 0).sum())} | {len(v)} |")
        lines.append("")

    families = set(per_ds.index.get_level_values("family"))
    for left, right in [("combined/quality-coverage", "combined/random"),
                        ("combined/random", "REAL_INNER_TRAIN"),
                        ("combined/quality-coverage", "REAL_INNER_TRAIN"),
                        ("SMOTE(NC)+b", "REAL_INNER_TRAIN")]:
        if {left, right} <= families:
            table(left, right)
    real = per_ds.loc["REAL_INNER_TRAIN"].groupby("classifier")["f1"].median()
    lines += ["## REAL_INNER_TRAIN median F1 over datasets, by learner", ""]
    lines += [f"- {k}: {v:.4f}" for k, v in real.items()]
    lines += ["", f"## Unavailable training sets: {len(unavailable)}", ""]
    lines += [f"- {u}" for u in unavailable]
    text = "\n".join(lines) + "\n"
    (out / "summary.md").write_text(text, encoding="utf-8")
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    o = sub.add_parser("oracle")
    o.add_argument("--run", type=Path, required=True)
    o.add_argument("--step1", type=Path, required=True, help="step-1 report directory")
    o.add_argument("--out", type=Path, required=True)
    c = sub.add_parser("clf")
    c.add_argument("--run", type=Path, required=True)
    c.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    print(oracle(args.run, args.step1, args.out) if args.command == "oracle"
          else clf(args.run, args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
