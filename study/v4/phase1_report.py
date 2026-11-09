# pyright: reportAttributeAccessIssue=false, reportOperatorIssue=false, reportGeneralTypeIssues=false, reportArgumentType=false, reportCallIssue=false, reportIndexIssue=false
"""Study v4 Phase 1 report: summarise the Part A audit units (descriptive only).

Per generator: medians over units of normalised rates (validity, copying, duplicates, unseen
categories, out-of-TRAIN-range cells), fidelity (KS, total variation, correlation difference,
discriminator AUC), distances (exact-zero and below-real-nearest-neighbour shares, within-pool
spread relative to the real minority, coverage) and gate support. LLM output health and cost
per valid record (actual ledger spend / complete records). Per-dataset discriminator AUC and
Spearman correlations with dataset properties. No test, no threshold, no privacy claim:
exact matches are copying diagnostics; distances are exploratory. Inner TRAIN only.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from study.v3 import budget, providers

LLMS = ("claude-haiku-5-5", "gpt-6-luna", "muse-spark-1.3")
ORDER = (*LLMS, "smote", "u2_native", "u2_flow_gate")


def rows(units: Path) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    pool_rows, health_rows, raw = [], [], []
    for path in sorted(units.glob("*.json")):
        u = json.loads(path.read_text(encoding="utf-8"))
        if u.get("validation_used") or u.get("test_used"):
            raise SystemExit(f"{path}: audit unit touched VALIDATION/TEST")
        raw.append(u)
        base = {"dataset_id": u["dataset_id"], "split_seed": u["split_seed"],
                "outer_train_n": u["outer_train_n"], "features": u["features"],
                "categorical_share": u["categorical"] / max(1, u["features"]),
                "has_missing": u["inner_missing_cells"] > 0}
        for g, m in u["pools"].items():
            n = m.get("n", 0)
            gate = u.get("gate", {}).get(g, {})
            r: dict[str, Any] = {**base, "generator": g, "n": n}
            if n:
                cat_cells = n * u["categorical"]
                num_cells = n * (u["features"] - u["categorical"])
                r.update({
                    "complete_rate": m["complete"] / n,
                    "complete_after_rounding_rate": m["complete_after_integer_rounding"] / n,
                    "wrong_class_rate": m["not_requested_class"] / n,
                    "train_copy_rate": m["exact_copy_of_inner_train"] / n,
                    "reference_copy_rate": (m["exact_copy_of_reference"] / n
                                            if m.get("exact_copy_of_reference") is not None
                                            else np.nan),
                    "duplicate_rate": m["within_pool_duplicates"] / n,
                    "unseen_category_rate": (m["unseen_category_cells"] / cat_cells
                                             if cat_cells else np.nan),
                    "out_of_range_rate": (m["out_of_train_range_cells"] / num_cells
                                          if num_cells else np.nan),
                    "mean_ks": m.get("mean_ks"), "mean_tv": m.get("mean_tv"),
                    "corr_mean_abs_diff": m.get("corr_mean_abs_diff"),
                    "discriminator_auc": m.get("discriminator_auc"),
                    "dcr_zero_share": m.get("dcr_zero_share"),
                    "dcr_below_real_nn_share": m.get("dcr_below_real_nn_share"),
                    "spread_ratio": (m["within_pool_nn_median"] / m["real_minority_nn_median"]
                                     if m.get("within_pool_nn_median") is not None
                                     and m.get("real_minority_nn_median") else np.nan),
                    "real_minority_coverage": m.get("real_minority_coverage"),
                    **{f"gate_{k}": v for k, v in gate.items()}})
            pool_rows.append(r)
        for g, h in u["health"].items():
            health_rows.append({**base, "generator": g,
                                **{k: v for k, v in h.items()
                                   if k not in ("finish_reasons", "load", "reference_row_ids")},
                                "truncated_calls": sum(n for k, n in h["finish_reasons"].items()
                                                       if k in ("max_tokens", "length")),
                                "complete": u["pools"].get(g, {}).get("complete", 0)})
    return pd.DataFrame(pool_rows), pd.DataFrame(health_rows), raw


METRICS = [("complete_rate", "complete (raw)"),
           ("complete_after_rounding_rate", "complete after integer rounding"),
           ("wrong_class_rate", "not the requested class"),
           ("train_copy_rate", "exact copy of an inner-TRAIN row"),
           ("reference_copy_rate", "exact copy of a prompt reference row"),
           ("duplicate_rate", "within-pool duplicate"),
           ("unseen_category_rate", "categorical cells unseen in TRAIN"),
           ("out_of_range_rate", "numeric cells outside the TRAIN range"),
           ("mean_ks", "mean KS (numeric) vs real minority"),
           ("mean_tv", "mean total variation (categorical)"),
           ("corr_mean_abs_diff", "mean |correlation difference|"),
           ("discriminator_auc", "discriminator AUC (0.5 = indistinguishable)"),
           ("dcr_zero_share", "distance 0 to a TRAIN row"),
           ("dcr_below_real_nn_share", "closer to TRAIN than real minority rows are to each other"),
           ("spread_ratio", "within-pool spread / real-minority spread"),
           ("real_minority_coverage", "real minority covered"),
           ("gate_combined_admitted_share", "gate admitted (combined)"),
           ("gate_local_support_raw_median", "gate local-support raw score (median)")]


def report(units: Path, out: Path) -> str:
    pools, health, raw = rows(units)
    out.mkdir(parents=True, exist_ok=True)
    pools.to_csv(out / "pools.csv", index=False)
    health.to_csv(out / "llm_health.csv", index=False)
    gens = [g for g in ORDER if g in set(pools["generator"])]
    n_units = len(raw)
    lines = ["# Study v4 Phase 1: audit of generated minority records (inner TRAIN only)", "",
             (f"{n_units} units, {pools['dataset_id'].nunique()} datasets. Medians over units "
              "(each unit: one dataset x split, one pool of up to 4 x B records). Descriptive "
              "only: no test; exact matches are copying diagnostics, never privacy results; "
              "distances are exploratory. VALIDATION and TEST were never read."), ""]
    if n_units < 200:
        lines += [f"**PARTIAL: {n_units} of 200 units.**", ""]
    lines += ["## Per generator (median over units)", "",
              "| metric | " + " | ".join(gens) + " |", "|---|" + "---|" * len(gens)]
    table = pools.groupby("generator").median(numeric_only=True)
    for col, label in METRICS:
        if col not in table:
            continue
        vals = [table.loc[g, col] if g in table.index else np.nan for g in gens]
        lines.append(f"| {label} | " + " | ".join("" if pd.isna(v) else f"{v:.3f}"
                                                  for v in vals) + " |")
    units_n = pools.groupby("generator")["dataset_id"].count()
    lines.append("| units with a pool | " + " | ".join(str(int(units_n.get(g, 0)))
                                                       for g in gens) + " |")
    table.to_csv(out / "per_generator_median.csv")
    if len(health):
        lines += ["", "## LLM output health and cost", "",
                  ("| generator | calls ok | parse failures / call | truncated calls | records "
                   "returned / requested | complete records | spend | $ per 1,000 complete |"),
                  "|---|---|---|---|---|---|---|---|"]
        spend = {m: budget.spend(providers.MODELS[m].provider).known_usd for m in LLMS}
        for g in LLMS:
            h = health[health["generator"] == g]
            if h.empty:
                continue
            complete = int(h["complete"].sum())
            lines.append(
                f"| {g} | {int(h['ok_calls'].sum())} | "
                f"{h['parse_failures'].sum() / max(1, h['ok_calls'].sum()):.3f} | "
                f"{int(h['truncated_calls'].sum())} | "
                f"{h['returned'].sum() / max(1, h['requested_records'].sum()):.3f} | "
                f"{complete} | ${spend[g]:.2f} | "
                f"${1000 * spend[g] / max(1, complete):.3f} |")
        lines += ["", ("Spend is the provider's total Study v3 ledger spend (all Phase 3 "
                       "calls of that model, pilots included), divided by complete records in "
                       "the audited units; one model per provider.")]
    lines += ["", "## Discriminator AUC per dataset (median over splits)", "",
              "| dataset | rows | features | categorical | " + " | ".join(gens) + " |",
              "|---|---|---|---|" + "---|" * len(gens)]
    per_ds = pools.pivot_table(index="dataset_id", columns="generator",
                               values="discriminator_auc", aggfunc="median")
    props = pools.groupby("dataset_id")[["outer_train_n", "features", "categorical_share"]].first()
    for d in props.sort_values("outer_train_n").index:
        vals = [per_ds.loc[d, g] if g in per_ds.columns and d in per_ds.index else np.nan
                for g in gens]
        p = props.loc[d]
        lines.append(f"| {d} | {int(p['outer_train_n'])} | {int(p['features'])} | "
                     f"{p['categorical_share']:.2f} | "
                     + " | ".join("" if pd.isna(v) else f"{v:.2f}" for v in vals) + " |")
    per_ds.to_csv(out / "per_dataset_discriminator_auc.csv")
    lines += ["", "## Spearman correlation with dataset properties (over units)", "",
              "| generator | metric | rows | features | categorical share |", "|---|---|---|---|---|"]
    for g in gens:
        sub = pools[pools["generator"] == g]
        for col in ("discriminator_auc", "train_copy_rate", "complete_rate"):
            if col not in sub or sub[col].notna().sum() < 10:
                continue
            cells = []
            for prop in ("outer_train_n", "features", "categorical_share"):
                ok = sub[[col, prop]].dropna()
                rho = stats.spearmanr(ok[col], ok[prop]).statistic if len(ok) >= 10 else np.nan
                cells.append("" if pd.isna(rho) else f"{rho:+.2f}")
            lines.append(f"| {g} | {col} | " + " | ".join(cells) + " |")
    prec_dir = units.parent.parent / "phase1-precision" / "units"
    prec = [json.loads(q.read_text(encoding="utf-8")) for q in sorted(prec_dir.glob("*.json"))]
    if prec:
        pr = pd.DataFrame([{"generator": g, "dataset_id": u["dataset_id"],
                            "auc_stored": m["auc_stored"], "auc_rounded": m["auc_rounded"]}
                           for u in prec for g, m in u["pools"].items()]).dropna()
        pr["change"] = pr["auc_rounded"] - pr["auc_stored"]
        pr.to_csv(out / "precision_check.csv", index=False)
        lines += ["", ("## Precision check: discriminator AUC after rounding both real and "
                       f"synthetic numerics to the coarser precision ({len(prec)} units)"), "",
                  ("| generator | median AUC as stored | median AUC rounded | median change | "
                   "units with rounded AUC < 0.75 |"), "|---|---|---|---|---|"]
        for g in gens:
            s = pr[pr["generator"] == g]
            if s.empty:
                continue
            lines.append(f"| {g} | {s['auc_stored'].median():.3f} | "
                         f"{s['auc_rounded'].median():.3f} | {s['change'].median():+.3f} | "
                         f"{int((s['auc_rounded'] < 0.75).sum())} / {len(s)} |")
        lines += ["", ("Rounding removes formatting differences (LLMs write rounded numbers). An "
                       "AUC that stays high after rounding reflects a distributional difference, "
                       "not number formatting.")]
    unavailable = Counter((k, v) for u in raw for k, v in u.get("unavailable", {}).items())
    lines += ["", "## Unavailable", ""]
    lines += [f"- {k}: {v}: {n} units" for (k, v), n in sorted(unavailable.items())] or ["- none"]
    text = "\n".join(lines) + "\n"
    (out / "summary.md").write_text(text, encoding="utf-8")
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--units", type=Path, default=Path("study/v4/runs/phase1/units"))
    parser.add_argument("--out", type=Path, default=Path("study/v4/report/phase1"))
    args = parser.parse_args(argv)
    print(report(args.units, args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
