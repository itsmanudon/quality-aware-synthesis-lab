# pyright: reportAttributeAccessIssue=false, reportOperatorIssue=false, reportGeneralTypeIssues=false, reportArgumentType=false, reportCallIssue=false, reportIndexIssue=false
"""Phase 4 analysis of the Phase 3 TEST evaluation, exactly as frozen in protocol.json.

Inputs: ``u3_eval.py`` units from one or more output directories (stage 1 ``eval-primary``,
stage 2 ``eval-rest``); rows are keyed (dataset, split seed, method, learner). The report
refuses to run unless every unit carries the frozen protocol SHA-256.

Aggregation (protocol ``statistics.aggregation``):
1. per (dataset, method, learner): mean of the available split cells; fewer than 3 of 5
   splits available -> unavailable;
2. pairwise: per dataset, the mean over learners available for both methods;
3. Friedman / average ranks: per dataset, the mean over learners available for every method
   in the set; only datasets where every method in the set is available enter.

Tests (protocol ``statistics.tests``), nothing else is reported as a test:
- success family: merged vs no-oversampling (tuned) and merged vs u2; two-sided Wilcoxon
  signed-rank (zero_method="wilcox", exact where available), Holm over the two; the success
  criterion also needs no MCC loss against either (not: median MCC difference < 0 and
  Holm-adjusted p < 0.05);
- comparator family: merged vs every other method, two-sided Wilcoxon, Holm over the family;
- median paired difference with a 95% percentile bootstrap interval over datasets (10,000
  resamples, seed 13);
- Friedman test and average ranks over the main methods.
Every unavailable cell is listed with its reason; no dataset is dropped silently. While any
of the planned units is missing the report is stamped PARTIAL and must not be read as the
result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
MERGED = "merged"
SUCCESS = ("no-oversampling", "u2")
MAIN = ("merged", "no-oversampling", "class-weighted", "smote", "u2", "original_ugo",
        "quality-coverage", "random")
MIN_SPLITS = 3
BOOT, BOOT_SEED, ALPHA = 10_000, 13, 0.05


def frozen_sha() -> str:
    return hashlib.sha256((HERE / "protocol.json").read_bytes().replace(b"\r\n", b"\n")
                          ).hexdigest()


def load(dirs: list[Path]) -> tuple[pd.DataFrame, pd.DataFrame, set[tuple[str, int]]]:
    """Cells (one row per dataset x split x method x learner) and unit-level unavailability."""
    sha = frozen_sha()
    cells: dict[tuple[str, int, str, str], dict[str, Any]] = {}
    unavailable: list[dict[str, Any]] = []
    units: set[tuple[str, int]] = set()
    for d in dirs:
        for path in sorted((d / "units").glob("*.json")):
            unit = json.loads(path.read_text(encoding="utf-8"))
            if unit.get("protocol_sha256") != sha:
                raise SystemExit(f"{path}: not evaluated under the frozen protocol")
            key = (unit["dataset_id"], int(unit["split_seed"]))
            units.add(key)
            for method, reason in unit.get("unavailable", {}).items():
                unavailable.append({"dataset_id": key[0], "split_seed": key[1],
                                    "method": method, "classifier": "*", "reason": str(reason)})
            for r in unit["rows"]:
                k = (key[0], key[1], r["method"], r["classifier"])
                if r["status"] != "ok":
                    unavailable.append({"dataset_id": key[0], "split_seed": key[1],
                                        "method": r["method"], "classifier": r["classifier"],
                                        "reason": r.get("reason", r["status"])})
                    continue
                if k in cells:
                    raise SystemExit(f"duplicate cell {k}")
                cells[k] = {"dataset_id": key[0], "split_seed": key[1], "method": r["method"],
                            "classifier": r["classifier"], "f1": r["f1"], "mcc": r["mcc"],
                            "average_precision": r["average_precision"],
                            "minority_recall": r["minority_recall"]}
    # Unit-level unavailability is copied into every stage's result file: count it once.
    unav = pd.DataFrame(unavailable, columns=["dataset_id", "split_seed", "method",
                                              "classifier", "reason"]).drop_duplicates()
    return pd.DataFrame(list(cells.values())), unav, units


def per_learner(cells: pd.DataFrame, metric: str) -> pd.DataFrame:
    """Step 1: dataset x method x learner mean over splits; < MIN_SPLITS -> dropped (unavailable)."""
    g = cells.groupby(["dataset_id", "method", "classifier"])[metric]
    out = pd.DataFrame({"value": g.mean(), "splits": g.count()}).reset_index()
    return pd.DataFrame(out[out["splits"] >= MIN_SPLITS])


def paired(pl: pd.DataFrame, a: str, b: str) -> pd.Series:
    """Step 2: per dataset, a minus b averaged over learners available for both."""
    wide = pl[pl["method"].isin([a, b])].pivot_table(
        index=["dataset_id", "classifier"], columns="method", values="value")
    if a not in wide or b not in wide:
        return pd.Series(dtype=float)
    both = wide.dropna(subset=[a, b])
    return (both[a] - both[b]).groupby(level="dataset_id").mean()


def holm(pvalues: list[float]) -> list[float]:
    order = np.argsort(pvalues)
    m, running, out = len(pvalues), 0.0, [0.0] * len(pvalues)
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[i]))
        out[i] = running
    return out


def bootstrap_median(diff: np.ndarray) -> tuple[float, float]:
    rng = np.random.default_rng(BOOT_SEED)
    idx = rng.integers(0, len(diff), size=(BOOT, len(diff)))
    meds = np.median(diff[idx], axis=1)
    return float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5))


def compare(pl: pd.DataFrame, others: list[str]) -> pd.DataFrame:
    rows = []
    for other in others:
        d = paired(pl, MERGED, other)
        n = len(d)
        row: dict[str, Any] = {"comparator": other, "datasets": n,
                               "median_diff": float(d.median()) if n else np.nan,
                               "above": int((d > 0).sum()), "below": int((d < 0).sum()),
                               "ties": int((d == 0).sum())}
        nonzero = d[d != 0]
        if len(nonzero) >= 1:
            row["p"] = float(stats.wilcoxon(nonzero.to_numpy(), zero_method="wilcox",
                                            alternative="two-sided").pvalue)
        else:
            row["p"] = np.nan
        row["ci_low"], row["ci_high"] = bootstrap_median(d.to_numpy()) if n else (np.nan,
                                                                                 np.nan)
        rows.append(row)
    out = pd.DataFrame(rows)
    ok = out["p"].notna()
    out["p_holm"] = np.nan
    if ok.any():
        out.loc[ok, "p_holm"] = holm(out.loc[ok, "p"].tolist())
    return out


def friedman(pl: pd.DataFrame, methods: tuple[str, ...]) -> dict[str, Any]:
    sub = pl[pl["method"].isin(methods)]
    wide = sub.pivot_table(index=["dataset_id", "classifier"], columns="method", values="value")
    wide = wide.dropna()  # learners available for every method in the set
    per_ds = wide.groupby(level="dataset_id").mean()
    per_ds = per_ds.reindex(columns=list(methods)).dropna()
    if len(per_ds) < 2 or per_ds.shape[1] < 3:
        return {"datasets": len(per_ds), "statistic": None, "p": None, "ranks": {}}
    ranks = per_ds.rank(axis=1, ascending=False).mean().sort_values()
    res = stats.friedmanchisquare(*[per_ds[m].to_numpy() for m in per_ds.columns])
    return {"datasets": len(per_ds), "statistic": float(res.statistic),
            "p": float(res.pvalue), "ranks": {k: float(v) for k, v in ranks.items()}}


def amendments(paths: list[Path]) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]],
                                           dict[str, dict[str, Any]]]:
    """Recorded protocol amendments: datasets excluded, incomplete stages, amendment hashes.

    An amendment must name the frozen protocol's SHA-256 as its base; the frozen file itself
    is never edited.
    """
    excluded: dict[str, dict[str, Any]] = {}
    incomplete: dict[str, dict[str, Any]] = {}
    used: list[dict[str, str]] = []
    for path in paths:
        raw = path.read_bytes().replace(b"\r\n", b"\n")
        a = json.loads(raw)
        if a["base_protocol_sha256"] != frozen_sha():
            raise SystemExit(f"{path}: amendment is not based on the frozen protocol")
        excluded.update(a["change"].get("excluded_datasets", {}))
        incomplete.update(a["change"].get("incomplete_stages", {}))
        used.append({"amendment_id": a["amendment_id"], "path": str(path),
                     "sha256": hashlib.sha256(raw).hexdigest()})
    return excluded, used, incomplete


def dropped_cells(cells: pd.DataFrame) -> pd.DataFrame:
    """(dataset, method, learner) cells removed by the 3-of-5 rule, for the unavailable list."""
    if not len(cells):
        return pd.DataFrame(columns=["dataset_id", "method", "classifier", "splits"])
    g = cells.groupby(["dataset_id", "method", "classifier"])["f1"].count().reset_index(
        name="splits")
    return pd.DataFrame(g[g["splits"] < MIN_SPLITS])


def report(dirs: list[Path], out: Path, planned_units: int,
           amendment_paths: list[Path] | None = None) -> str:
    cells, unav, units = load(dirs)
    excluded, used, incomplete = amendments(amendment_paths or [])
    if excluded:
        # Excluded datasets enter no test; they are listed as unavailable with their reason.
        unav = pd.concat([unav[~unav["dataset_id"].isin(excluded)], pd.DataFrame(
            [{"dataset_id": d, "split_seed": "*", "method": "*", "classifier": "*",
              "reason": info["reason"]} for d, info in excluded.items()])], ignore_index=True)
        cells = cells[~cells["dataset_id"].isin(excluded)] if len(cells) else cells
        units = {u for u in units if u[0] not in excluded}
        planned_units -= 5 * len(excluded)
    # Cells removed by the frozen 3-of-5 rule are listed, never dropped silently.
    drops = dropped_cells(cells)
    if len(drops):
        unav = pd.concat([unav, pd.DataFrame(
            [{"dataset_id": r.dataset_id, "split_seed": f"{r.splits} of 5", "method": r.method,
              "classifier": r.classifier,
              "reason": incomplete.get(r.dataset_id, {}).get("reason",
                                                           "FEWER_THAN_3_OF_5_SPLITS")}
             for r in drops.itertuples()])], ignore_index=True)
    out.mkdir(parents=True, exist_ok=True)
    cells.to_csv(out / "cells.csv", index=False)
    unav.to_csv(out / "unavailable.csv", index=False)

    # Stage 1 and stage 2 write separate files per unit: complete only when each has them all.
    # A stage an amendment declares incomplete for a dataset is counted without that dataset.
    def expected(d: Path) -> tuple[int, int]:
        skip = {ds for ds, info in incomplete.items() if d.name == info.get("stage")}
        got = len([p for p in (d / "units").glob("*.json")
                   if p.name.split("__")[0] not in set(excluded) | skip])
        return got, planned_units - 5 * len(skip)

    counts = {str(d): expected(d) for d in dirs}
    per_dir = {k: v[0] for k, v in counts.items()}
    partial = any(got < want for got, want in counts.values())
    methods = sorted(cells["method"].unique()) if len(cells) else []
    lines = [f"# Phase 4: TEST results under the frozen protocol ({frozen_sha()[:12]})", ""]
    for a in used:
        lines += [f"Amendment applied: {a['amendment_id']} ({a['sha256'][:12]}).", ""]
    for d, info in sorted(excluded.items()):
        lines += [f"- {d} excluded from every test: {info['reason']}."]
    for d, info in sorted(incomplete.items()):
        lines += [(f"- {d}: stage {info['stage']} incomplete, its methods unavailable: "
                   f"{info['reason']}.")]
    if excluded or incomplete:
        lines += [""]
    if partial:
        lines += [(f"**PARTIAL: units evaluated per stage {per_dir} of {planned_units}. Not "
                   "the result; do not interpret.**"), ""]
    n_datasets = cells["dataset_id"].nunique() if len(cells) else 0
    lines += [(f"Units: {len(units)}; datasets: {n_datasets}; cells: {len(cells)}; "
               f"unavailable cells listed: {len(unav)}."), ""]
    pl_f1, pl_mcc = per_learner(cells, "f1"), per_learner(cells, "mcc")
    success = compare(pl_f1, list(SUCCESS))
    success_mcc = compare(pl_mcc, list(SUCCESS))
    met = bool(len(success) == 2 and (success["median_diff"] > 0).all()
               and (success["p_holm"] < ALPHA).all()
               and not ((success_mcc["median_diff"] < 0) & (success_mcc["p_holm"] < ALPHA)).any())
    lines += ["## Success family (F1; Wilcoxon two-sided, Holm over 2)", "",
              "| merged vs | datasets | median diff | 95% CI | above/below/ties | p | p Holm |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in success.itertuples():
        lines.append(f"| {r.comparator} | {r.datasets} | {r.median_diff:+.4f} | "
                     f"[{r.ci_low:+.4f}, {r.ci_high:+.4f}] | {r.above}/{r.below}/{r.ties} | "
                     f"{r.p:.4g} | {r.p_holm:.4g} |")
    lines += ["", "MCC no-loss check (same family):", "",
              "| merged vs | median MCC diff | p Holm | loss |", "| --- | --- | --- | --- |"]
    for r in success_mcc.itertuples():
        loss = bool(r.median_diff < 0 and r.p_holm < ALPHA)
        lines.append(f"| {r.comparator} | {r.median_diff:+.4f} | {r.p_holm:.4g} | {loss} |")
    lines += ["", f"**Success criterion met: {met}**" + (" (PARTIAL data)" if partial else ""),
              ""]
    others = [m for m in methods if m != MERGED and m not in SUCCESS]
    comp = compare(pl_f1, others)
    lines += ["## Comparator family (F1; Wilcoxon two-sided, Holm over the family)", "",
              "| merged vs | datasets | median diff | 95% CI | above/below/ties | p | p Holm |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in comp.sort_values("comparator").itertuples():
        lines.append(f"| {r.comparator} | {r.datasets} | {r.median_diff:+.4f} | "
                     f"[{r.ci_low:+.4f}, {r.ci_high:+.4f}] | {r.above}/{r.below}/{r.ties} | "
                     f"{r.p:.4g} | {r.p_holm:.4g} |")
    fr = friedman(pl_f1, MAIN)
    lines += ["", f"## Friedman over the main methods (F1; {fr['datasets']} complete datasets)",
              "", f"statistic {fr['statistic']}, p {fr['p']}", "",
              "| method | average rank (1 = best) |", "| --- | --- |"]
    lines += [f"| {m} | {v:.2f} |" for m, v in fr["ranks"].items()]
    counts = Counter(zip(unav["method"], unav["reason"].str.split(" ").str[0]))
    lines += ["", "## Unavailable cells (method, reason: count)", ""]
    lines += [f"- {m}: {r}: {n}" for (m, r), n in sorted(counts.items())]
    # Per-dataset breakdown of the success family (descriptive; the tests are above).
    per_ds = pd.DataFrame({f"merged_minus_{c}": paired(pl_f1, MERGED, c) for c in SUCCESS})
    per_ds.index.name = "dataset_id"
    per_ds.to_csv(out / "per_dataset_success_f1.csv")
    lines += ["", "## Per-dataset F1 differences, success family (descriptive)", "",
              "| dataset | merged - no-oversampling | merged - u2 |", "| --- | --- | --- |"]
    for d, r in per_ds.sort_index().iterrows():
        cells_txt = [("" if pd.isna(v) else f"{v:+.4f}") for v in r]
        lines.append(f"| {d} | {cells_txt[0]} | {cells_txt[1]} |")
    success.assign(metric="f1").to_csv(out / "success_f1.csv", index=False)
    success_mcc.assign(metric="mcc").to_csv(out / "success_mcc.csv", index=False)
    comp.to_csv(out / "comparators_f1.csv", index=False)
    (out / "friedman_f1.json").write_text(json.dumps(fr, indent=1), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(
        {"partial": partial, "units": len(units), "planned_units": planned_units,
         "amendments": used, "excluded_datasets": sorted(excluded),
         "incomplete_stages": {d: i["stage"] for d, i in incomplete.items()},
         "success_criterion_met": met, "protocol_sha256": frozen_sha()}, indent=1),
        encoding="utf-8")
    text = "\n".join(lines) + "\n"
    (out / "summary.md").write_text(text, encoding="utf-8")
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evals", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--planned-units", type=int, default=200)
    parser.add_argument("--amendments", type=Path, nargs="*", default=[],
                        help="recorded protocol amendments (e.g. protocol_amendment_1.json)")
    args = parser.parse_args(argv)
    print(report(args.evals, args.out, args.planned_units, args.amendments))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
