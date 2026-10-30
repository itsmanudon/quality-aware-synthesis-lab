"""Build the IEEE manuscript's multi-panel figures from saved study evidence.

Read-only with respect to research evidence: every value is read from finalized
reports (Empirical v2 run/report, Phase 4 evidence vectors, Phase 6 repair audit,
exploratory addenda v1/v2). Nothing is refitted, rescored or reselected, and no
B1/B2/B3 decision is read for anything other than display. Outputs go only to
``paper/rcqasyn-ieee/figures``.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

# Validated categorical slots (dataviz reference palette, light mode). Slots 3-5 sit
# below 3:1 on white, so every use is paired with a marker shape or direct label.
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300")
GREY, INK, MUTED = "#8a8984", "#0b0b0b", "#52514e"
CANONICAL = ["Abalone19", "Ecoli4", "page-blocks0"]

FULL = 7.16  # IEEE two-column text width, inches
COLUMN = 3.5


def _style() -> None:
    plt.rcParams.update({
        "font.family": "serif", "font.serif": ["Times New Roman", "Times", "STIXGeneral"],
        "mathtext.fontset": "stix", "font.size": 7, "axes.titlesize": 7.5,
        "axes.labelsize": 7, "xtick.labelsize": 6.5, "ytick.labelsize": 6.5,
        "legend.fontsize": 6.5, "axes.spines.top": False, "axes.spines.right": False,
        "axes.edgecolor": MUTED, "axes.linewidth": 0.6, "xtick.color": MUTED,
        "ytick.color": MUTED, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
        "grid.color": "#e4e3df", "grid.linewidth": 0.5, "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02, "pdf.fonttype": 42, "figure.dpi": 200,
    })


def _json(path: Path) -> Any:
    return json.loads(path.read_text())


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _tag(ax: Any, letter: str) -> None:
    ax.set_title(f"({letter})", loc="left", fontsize=7.5, fontweight="bold", pad=3)


def _save(fig: Any, out: Path, name: str) -> None:
    fig.savefig(out / f"{name}.pdf")
    fig.savefig(out / f"{name}.png", dpi=200)
    plt.close(fig)


# ---------------------------------------------------------------- historical audit
def figure_audit(root: Path, out: Path) -> None:
    vectors = _csv(root / "artifacts/reports/phase4/shadow-v1/vectors.csv")
    audit = _csv(root / "artifacts/reports/phase6/core-final-replay-v1/repairs/audit.csv")

    fig = plt.figure(figsize=(FULL, 4.15))
    grid = fig.add_gridspec(2, 3, hspace=0.62, wspace=0.34)

    # (a) structural defect composition per dataset
    ax = fig.add_subplot(grid[0, 0])
    kinds = {"Missing class/feature": ORANGE, "Fractional integer": BLUE, "Both": MAGENTA}
    counts: dict[str, Counter[str]] = {d: Counter() for d in CANONICAL}
    totals: Counter[str] = Counter()
    for row in vectors:
        totals[row["dataset_id"]] += 1
        structural = json.loads(row["structural"])
        if structural["authoritative_validity"] != "INVALID":
            continue
        reasons = {v["reason"] for v in structural["quantities"]["violations"]}
        missing = "ABSENT_DECLARED_FIELD" in reasons
        fractional = "NONINTEGRAL_DECLARED_INTEGER" in reasons
        key = "Both" if missing and fractional else (
            "Missing class/feature" if missing else "Fractional integer")
        counts[row["dataset_id"]][key] += 1
    y = np.arange(len(CANONICAL))
    left = np.zeros(len(CANONICAL))
    for kind, color in kinds.items():
        vals = np.array([counts[d][kind] for d in CANONICAL], dtype=float)
        ax.barh(y, vals, left=left, color=color, height=0.55, edgecolor="white",
                linewidth=1, label=kind)
        left += vals
    for i, d in enumerate(CANONICAL):
        ax.text(left[i] + 1.5, i, f"{int(left[i])}/{totals[d]}", va="center", fontsize=6.5,
                color=INK)
    ax.set_yticks(y, CANONICAL)
    ax.invert_yaxis()
    ax.set_xlim(0, 85)
    ax.set_xlabel("Structurally rejected candidates")
    ax.legend(frameon=False, loc="upper right", handlelength=1, borderaxespad=0.1)
    _tag(ax, "a")

    # (b-d) local vs global percentile evidence, coloured by structural status
    for col, dataset in enumerate(["Abalone19", "Ecoli4"], start=1):
        ax = fig.add_subplot(grid[0, col])
        _evidence_scatter(ax, [r for r in vectors if r["dataset_id"] == dataset], dataset,
                          legend=col == 1)
        _tag(ax, "bc"[col - 1])
    ax = fig.add_subplot(grid[1, 0])
    _evidence_scatter(ax, [r for r in vectors if r["dataset_id"] == "page-blocks0"],
                      "page-blocks0", legend=False)
    _tag(ax, "d")

    # (e) repair outcome for every structurally rejected record
    ax = fig.add_subplot(grid[1, 1])
    labels = {
        "Repaired": lambda r: r["outcome"] == "REPAIR_APPLIED",
        "Missing/\nother req.": lambda r: r["reasons"]
        == '["OTHER_OR_MISSING_STRUCTURAL_REQUIREMENTS"]',
        ">3 int.\nedits": lambda r: r["reasons"] == '["MORE_THAN_THREE_INTEGER_FIELDS"]',
        "Both\nreasons": lambda r: "OTHER" in r["reasons"] and "MORE_THAN" in r["reasons"],
    }
    rejected = [r for r in audit if r["pre_structural_state"] == "STRUCTURALLY_INVALID"]
    vals = [sum(1 for r in rejected if test(r)) for test in labels.values()]
    colors = [BLUE, ORANGE, YELLOW, MAGENTA]
    bars = ax.bar(range(len(vals)), vals, color=colors, width=0.6)
    for bar, v in zip(bars, vals, strict=True):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 1, str(v), ha="center", fontsize=6.5)
    ax.set_xticks(range(len(vals)), list(labels), fontsize=5.8)
    ax.set_ylabel("Records")
    ax.set_ylim(0, 64)
    ax.set_title("Repair outcome, 75 rejects", fontsize=7)
    _tag(ax, "e")

    # (f) edits per repaired record and admission after repair
    ax = fig.add_subplot(grid[1, 2])
    applied = [r for r in audit if r["outcome"] == "REPAIR_APPLIED"]
    edits = Counter(int(r["edited_fields"]) for r in applied)
    after = {k: Counter(r["new_action"] for r in applied if int(r["edited_fields"]) == k)
             for k in (1, 2, 3)}
    xs = np.arange(3)
    passed = np.array([after[k]["PROVISIONAL_PASS"] for k in (1, 2, 3)])
    review = np.array([after[k]["REVIEW_REQUIRED"] for k in (1, 2, 3)])
    ax.bar(xs, passed, color=BLUE, width=0.55, label="Provisional pass")
    ax.bar(xs, review, bottom=passed, color=YELLOW, width=0.55, edgecolor="white",
           linewidth=1, label="Review required")
    for x, k in enumerate((1, 2, 3)):
        ax.text(x, edits[k] + 1, str(edits[k]), ha="center", fontsize=6.5)
    ax.set_xticks(xs, ["1 edit", "2 edits", "3 edits"])
    ax.set_ylabel("Repaired records")
    ax.set_ylim(0, 46)
    ax.legend(frameon=False, loc="upper right", handlelength=1)
    ax.set_title("Edits, 54 repairs", fontsize=7)
    _tag(ax, "f")
    _save(fig, out, "audit")


def _evidence_scatter(ax: Any, rows: list[dict[str, str]], dataset: str, legend: bool) -> None:
    pts: dict[bool, list[tuple[float, float]]] = {True: [], False: []}
    for row in rows:
        norm = json.loads(row["normalized"])
        local, glob = norm["local_support"], norm["cross_feature"]
        if local["state"] != "AVAILABLE" or glob["state"] != "AVAILABLE":
            continue
        invalid = json.loads(row["structural"])["authoritative_validity"] == "INVALID"
        pts[invalid].append((local["percentile"], glob["percentile"]))
    for invalid, color, marker, label in ((False, BLUE, "o", "Compliant"),
                                          (True, ORANGE, "x", "Struct. reject")):
        if pts[invalid]:
            arr = np.array(pts[invalid])
            ax.scatter(arr[:, 0], arr[:, 1], s=7 if not invalid else 10, c=color,
                       marker=marker, linewidths=0.6 if invalid else 0.2,
                       edgecolors="white" if not invalid else None, alpha=0.85, label=label)
    for v in (0.9,):
        ax.axvline(v, color=GREY, lw=0.6, ls="--")
        ax.axhline(v, color=GREY, lw=0.6, ls="--")
    ax.set_xlim(0, 1.02)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Local-support percentile")
    ax.set_ylabel("Global-consistency percentile")
    ax.set_title(dataset, fontsize=7)
    if legend:
        ax.legend(frameon=False, loc="upper left", handletextpad=0.2, borderaxespad=0.1,
                  markerscale=1.3)


# ------------------------------------------------------- matched-budget construction
SELECTORS = [
    ("selection/source-order/s42", "Source order", GREY, "s"),
    ("selection/farthest-first/s42", "Farthest-first", AQUA, "^"),
    ("selection/coverage-greedy/s42", "Coverage-greedy", YELLOW, "D"),
    ("selection/quality-coverage/s42", "Quality-coverage", BLUE, "o"),
]


def figure_construction(root: Path, out: Path) -> None:
    rows = _csv(root / "artifacts/reports/empirical-v2/report-v3/consolidated-ablations.csv")
    fig, axes = plt.subplots(2, 3, figsize=(FULL, 4.0),
                             gridspec_kw={"hspace": 0.6, "wspace": 0.3})
    for col, dataset in enumerate(CANONICAL):
        drows = [r for r in rows if r["dataset_id"] == dataset]
        ax = axes[0, col]
        for prefix, color, label in (("schema/random/", ORANGE, "Schema random (5 seeds)"),
                                     ("combined/random/", MAGENTA, "Admitted random (5 seeds)")):
            sel = [r for r in drows if r["method"].startswith(prefix)]
            ax.scatter([float(r["unique_train_feature_coverage"]) for r in sel],
                       [float(r["near_duplicate_rate"]) for r in sel], s=12, c=color,
                       marker="v", linewidths=0.3, edgecolors="white", label=label)
        for method, label, color, marker in SELECTORS:
            r = next(r for r in drows if r["method"] == method)
            # Quality-coverage is drawn largest and lowest so a coincident selector stays visible.
            qc = label == "Quality-coverage"
            ax.scatter(float(r["unique_train_feature_coverage"]), float(r["near_duplicate_rate"]),
                       s=60 if qc else 26, c=color, marker=marker, edgecolors=INK,
                       linewidths=0.4, label=label, zorder=2 if qc else 3)
        ax.set_title(dataset, fontsize=7)
        ax.set_xlabel("Distinct TRAIN coverage")
        ax.set_ylim(-0.04, 0.82)
        if col == 0:
            ax.set_ylabel("Near-duplicate rate")
        ax.grid(True)
        _tag(ax, "abc"[col])

        # bottom row: pool size and pure-TSTR F1 under each admission rule
        ax = axes[1, col]
        ablations = [("ablation/structure-only/s42", "Structure"),
                     ("ablation/local-review/s42", "+ local"),
                     ("ablation/global-review/s42", "+ global"),
                     ("ablation/combined-review/s42", "+ both")]
        f1s, pools = [], []
        for method, _ in ablations:
            r = next(r for r in drows if r["method"] == method)
            f1s.append(float(r["f1_tstr_lr"]))
            pools.append(int(r["eligible_n"]))
        x = np.arange(len(ablations))
        bars = ax.bar(x, f1s, color=BLUE, width=0.55)
        for bar, pool, f1 in zip(bars, pools, f1s, strict=True):
            ax.text(bar.get_x() + bar.get_width() / 2, f1 + 0.012, f"{f1:.3f}", ha="center",
                    fontsize=6)
            ax.text(bar.get_x() + bar.get_width() / 2, -0.075, f"n={pool}", ha="center",
                    fontsize=5.8, color=MUTED)
        ax.set_xticks(x, [label for _, label in ablations])
        ax.tick_params(axis="x", pad=9)
        ax.set_ylim(0, 0.52)
        if col == 0:
            ax.set_ylabel("LR pure-TSTR F1")
        ax.set_title(f"{dataset}: admission rule", fontsize=7)
        _tag(ax, "def"[col])
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=6, frameon=False,
               bbox_to_anchor=(0.5, 1.02), handletextpad=0.2, columnspacing=1.0)
    _save(fig, out, "construction")


# ------------------------------------------------------------- conditional uncertainty
PAIRS = [
    ("quality-coverage:original", "schema/random/s13", "TSTR", "QC $-$ schema random"),
    ("quality-coverage:original", "combined/random/s13", "TSTR", "QC $-$ admitted random"),
    ("quality-coverage:repair-augmented", "quality-coverage:original", "TSTR",
     "Repaired $-$ original"),
    ("quality-coverage:original", "schema/random/s13", "HYBRID_MINORITY",
     "QC $-$ schema random"),
    ("quality-coverage:original", "combined/random/s13", "HYBRID_MINORITY",
     "QC $-$ admitted random"),
    ("quality-coverage:repair-augmented", "quality-coverage:original", "HYBRID_MINORITY",
     "Repaired $-$ original"),
    ("quality-coverage:original", "REAL_TRAIN", "HYBRID_MINORITY", "QC hybrid $-$ real only"),
]


def figure_uncertainty(root: Path, out: Path) -> None:
    diffs = _json(root / "artifacts/reports/empirical-v2/run-v2/paired-differences.json")
    index = {(d["dataset_id"], d["left"][0], d["right"][0], d["left"][1], d["left"][2],
              d["metric"]): d for d in diffs}
    # Point estimates are the observed endpoint metrics; the interval file stores bounds only.
    endpoints = {(b["dataset_id"], b["method"], b["classifier"], b["regime"], b["metric"]):
                 b.get("estimate")
                 for b in _json(root / "artifacts/reports/empirical-v2/run-v2/bootstrap.json")}
    colors = dict(zip(CANONICAL, (BLUE, ORANGE, AQUA), strict=True))
    markers = dict(zip(CANONICAL, ("o", "s", "^"), strict=True))
    fig, axes = plt.subplots(1, 4, figsize=(FULL, 3.0), sharey=True,
                             gridspec_kw={"wspace": 0.12})
    panels = [("logistic_regression", "f1", "LR, F1"),
              ("logistic_regression", "average_precision", "LR, AP"),
              ("random_forest", "f1", "RF, F1"),
              ("random_forest", "average_precision", "RF, AP")]
    ypos = np.arange(len(PAIRS))
    for ax, (clf, metric, title), letter in zip(axes, panels, "abcd", strict=True):
        for off, dataset in zip((-0.22, 0, 0.22), CANONICAL, strict=True):
            for y, (left, right, regime, _) in zip(ypos, PAIRS, strict=True):
                d = index.get((dataset, left, right, clf, regime, metric))
                if d is None or d["status"] != "ok":
                    continue
                left_est = endpoints.get((dataset, left, clf, regime, metric))
                right_regime = "TRTR" if right == "REAL_TRAIN" else regime
                right_est = endpoints.get((dataset, right, clf, right_regime, metric))
                est = (None if left_est is None or right_est is None
                       else left_est - right_est)
                lo, hi = d["lower"], d["upper"]
                ax.plot([lo, hi], [y + off] * 2, color=colors[dataset], lw=1.1)
                if est is not None:
                    ax.scatter(est, y + off, s=10, c=colors[dataset], marker=markers[dataset],
                               zorder=3, edgecolors="white", linewidths=0.3)
        ax.axvline(0, color=INK, lw=0.6)
        ax.axhline(2.5, color=GREY, lw=0.5, ls=":")
        ax.set_title(title, fontsize=7)
        ax.set_xlabel("Paired difference (95% interval)")
        ax.grid(True, axis="x")
        _tag(ax, letter)
    axes[0].set_yticks(ypos, [p[3] for p in PAIRS])
    axes[0].invert_yaxis()
    axes[0].text(-0.86, 1, "Pure TSTR", transform=axes[0].get_yaxis_transform(),
                 rotation=90, va="center", ha="center", fontsize=6.5, color=MUTED)
    axes[0].text(-0.86, 4.5, "Hybrid", transform=axes[0].get_yaxis_transform(),
                 rotation=90, va="center", ha="center", fontsize=6.5, color=MUTED)
    handles = [Line2D([], [], color=colors[d], marker=markers[d], lw=1.1, markersize=3.5,
                      label=d) for d in CANONICAL]
    fig.legend(handles=handles, loc="upper center", ncol=3, frameon=False,
               bbox_to_anchor=(0.55, 1.04))
    _save(fig, out, "uncertainty")


# ------------------------------------------------------------------ fresh splits
FRESH = [
    ("REAL_TRAIN", "TRTR", "Real only", GREY),
    ("CLASS_WEIGHTED_LR", "TRTR", "Class-weighted", GREY),
    ("RandomOverSampler+b", "HYBRID_MINORITY", "ROS $+b$", GREEN),
    ("SMOTE*", "HYBRID_MINORITY", "SMOTE(NC) $+b$", GREEN),
    ("schema/random", "HYBRID_MINORITY", "Schema random", ORANGE),
    ("combined/random", "HYBRID_MINORITY", "Admitted random", ORANGE),
    ("combined/source-order", "HYBRID_MINORITY", "Source order", AQUA),
    ("combined/farthest-first", "HYBRID_MINORITY", "Farthest-first", AQUA),
    ("combined/coverage-greedy", "HYBRID_MINORITY", "Coverage-greedy", AQUA),
    ("combined/quality-coverage", "HYBRID_MINORITY", "Quality-coverage", BLUE),
]


def figure_fresh(root: Path, out: Path) -> None:
    rows = [r for r in _csv(root / "artifacts/reports/empirical-v2/run-v2/results.csv")
            if r["track"] == "B" and r["status"] == "ok" and r["classifier"] == "logistic_regression"]
    fig, axes = plt.subplots(2, 3, figsize=(FULL, 3.9), sharex=True,
                             gridspec_kw={"hspace": 0.18, "wspace": 0.22})
    for col, dataset in enumerate(CANONICAL):
        for row_ix, (metric, label) in enumerate((("f1", "F1"), ("average_precision", "AP"))):
            ax = axes[row_ix, col]
            for x, (method, regime, _, color) in enumerate(FRESH):
                vals = [float(r[metric]) for r in rows if r["dataset_id"] == dataset
                        and r["regime"] == regime
                        and (r["method"].startswith("SMOTE") if method == "SMOTE*"
                             else r["method"] == method)]
                if not vals:
                    ax.text(x, 0.02, "n/a", ha="center", fontsize=5.5, color=MUTED, rotation=90)
                    continue
                jitter = np.linspace(-0.18, 0.18, len(vals))
                ax.scatter(x + jitter, vals, s=7, c=color, alpha=0.9, edgecolors="white",
                           linewidths=0.2)
                ax.plot([x - 0.3, x + 0.3], [mean(vals)] * 2, color=INK, lw=1.1)
            ax.set_ylim(-0.03, 1.03)
            ax.grid(True, axis="y")
            if col == 0:
                ax.set_ylabel(f"LR {label}, five splits")
            if row_ix == 0:
                ax.set_title(dataset, fontsize=7)
            _tag(ax, "abcdef"[row_ix * 3 + col])
        axes[1, col].set_xticks(range(len(FRESH)), [f[2] for f in FRESH], rotation=55,
                                ha="right", fontsize=6)
    handles = [Line2D([], [], color=c, marker="o", lw=0, markersize=3.5, label=lab)
               for lab, c in (("Training baseline", GREY), ("Oversampler", GREEN),
                              ("Random curation", ORANGE), ("Deterministic selector", AQUA),
                              ("Quality-coverage", BLUE))]
    handles.append(Line2D([], [], color=INK, lw=1.1, label="Five-split mean"))
    fig.legend(handles=handles, loc="upper center", ncol=6, frameon=False,
               bbox_to_anchor=(0.5, 1.0))
    _save(fig, out, "fresh-splits")


# ------------------------------------------------------------ datasets overview
def figure_datasets(root: Path, out: Path) -> None:
    datasets = [d for d in _json(root / "addendum/v2/report/summary.json")["datasets"]
                if d["status"] == "ok"]
    datasets.sort(key=lambda d: d["imbalance_ratio"])
    fig, axes = plt.subplots(1, 2, figsize=(COLUMN, 1.95), sharey=True,
                             gridspec_kw={"wspace": 0.12})
    names = [d["dataset_id"] for d in datasets]
    colors = [BLUE if d["source"] == "canonical" else ORANGE for d in datasets]
    y = np.arange(len(datasets))
    axes[0].barh(y, [d["imbalance_ratio"] for d in datasets], color=colors, height=0.6)
    axes[0].set_xscale("log")
    axes[0].set_xlabel("Imbalance ratio (log)")
    axes[0].set_yticks(y, names)
    _tag(axes[0], "a")
    pos = [min(d["test_positives"]) for d in datasets]
    axes[1].barh(y, pos, color=colors, height=0.6)
    for i, p in enumerate(pos):
        axes[1].text(p * 1.12, i, str(p), va="center", fontsize=6)
    axes[1].set_xscale("log")
    axes[1].set_xlim(right=400)
    axes[1].set_xlabel("TEST positives per split (log)")
    _tag(axes[1], "b")
    handles = [Line2D([], [], color=c, marker="s", lw=0, markersize=4, label=lab)
               for lab, c in (("Main study", BLUE), ("Addendum", ORANGE))]
    fig.legend(handles=handles, loc="upper center", ncol=2, frameon=False,
               bbox_to_anchor=(0.55, 1.06))
    _save(fig, out, "datasets")


# --------------------------------------------------------- addendum: geometry vs utility
ADDENDUM_ORDER = ["Abalone19", "abalone9-18", "Ecoli4", "ecoli1", "page-blocks0", "segment0",
                  "yeast3", "yeast4"]


def figure_addendum_geometry(root: Path, out: Path) -> None:
    constructions = _json(root / "addendum/v1/report/constructions.json") + [
        c for c in _json(root / "artifacts/reports/empirical-v2/run-v2/constructions.json")
        if c.get("track") == "B"]
    geo: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for c in constructions:
        if c.get("status") != "ok" or c["method"] not in ("combined/quality-coverage",
                                                           "combined/random"):
            continue
        geo[(c["dataset_id"], c["method"])]["cov"].append(c["unique_train_feature_coverage"])
        if c.get("near_duplicate_rate") is not None:
            geo[(c["dataset_id"], c["method"])]["near"].append(c["near_duplicate_rate"])
    e4 = _json(root / "addendum/v1/report/summary.json")["E4"]["comparisons"]

    fig, axes = plt.subplots(1, 3, figsize=(FULL, 2.45), gridspec_kw={"wspace": 0.42})
    y = np.arange(len(ADDENDUM_ORDER))
    for ax, key, xlabel, letter in ((axes[0], "cov", "Distinct TRAIN coverage", "a"),
                                    (axes[1], "near", "Near-duplicate rate", "b")):
        for i, dataset in enumerate(ADDENDUM_ORDER):
            qc = geo[(dataset, "combined/quality-coverage")][key]
            rnd = geo[(dataset, "combined/random")][key]
            if not qc or not rnd:
                continue
            ax.plot([mean(rnd), mean(qc)], [i, i], color=GREY, lw=1, zorder=1)
            ax.scatter(mean(rnd), i, s=18, c=ORANGE, marker="v", zorder=2,
                       label="Admitted random" if i == 0 else None)
            ax.scatter(mean(qc), i, s=18, c=BLUE, marker="o", zorder=3,
                       label="Quality-coverage" if i == 0 else None)
        ax.set_yticks(y, ADDENDUM_ORDER if letter == "a" else [])
        ax.invert_yaxis()
        ax.set_xlabel(xlabel + " (5-split mean)")
        ax.grid(True, axis="x")
        _tag(ax, letter)

    ax = axes[2]
    for off, clf, color, marker in ((-0.15, "logistic_regression", BLUE, "o"),
                                    (0.15, "random_forest", ORANGE, "s")):
        datasets = e4[f"QC_minus_admitted_random|{clf}|f1"]["datasets"]
        for i, dataset in enumerate(ADDENDUM_ORDER):
            entry = datasets.get(dataset)
            if not entry or entry.get("status") != "ok":
                continue
            vals = [v for v in entry["per_split"].values() if v is not None]
            ax.scatter(vals, [i + off] * len(vals), s=8, c=color, marker=marker, alpha=0.85,
                       edgecolors="white", linewidths=0.2,
                       label=("LR" if clf.startswith("log") else "RF") if i == 0 else None)
    ax.axvline(0, color=INK, lw=0.6)
    ax.set_yticks(y, [])
    ax.invert_yaxis()
    ax.set_xlabel("F1: QC $-$ admitted random (per split)")
    ax.grid(True, axis="x")
    _tag(ax, "c")
    # One shared legend above the panels keeps markers off the per-split points.
    handles = axes[0].get_legend_handles_labels()[0] + ax.get_legend_handles_labels()[0]
    labels = axes[0].get_legend_handles_labels()[1] + ["LR (panel c)", "RF (panel c)"]
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False,
               bbox_to_anchor=(0.5, 1.07), handletextpad=0.2)
    _save(fig, out, "addendum-geometry")


# ------------------------------------------------------------- addendum: benchmark
CURATOR_LABELS = {
    "schema/random": "Schema random", "combined/random": "Admitted random",
    "combined/source-order": "Source order", "combined/farthest-first": "Farthest-first",
    "combined/coverage-greedy": "Coverage-greedy", "combined/quality-coverage": "Quality-coverage",
    "reimpl/cllm-style": "CLLM-style", "reimpl/discriminator-realism": "Discriminator",
}
COMBOS = [("logistic_regression|f1", "LR F1"), ("logistic_regression|average_precision", "LR AP"),
          ("random_forest|f1", "RF F1"), ("random_forest|average_precision", "RF AP")]


def _label(method: str) -> str:
    if method in CURATOR_LABELS:
        return CURATOR_LABELS[method]
    name = method.replace("REAL_TRAIN", "Real only").replace("RandomOverSampler", "ROS")
    name = name.replace("/full", " full").replace("/+b", "+b")
    return name.replace("+b", " $+b$") if name.endswith("+b") else name


def _heat(ax: Any, matrix: np.ndarray, rows: list[str], cols: list[str], cmap: str,
          fmt: str, highlight: int | None, vmin: float, vmax: float) -> Any:
    image = ax.imshow(matrix, cmap=cmap, aspect="auto", vmin=vmin, vmax=vmax)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            v = matrix[i, j]
            if np.isnan(v):
                ax.text(j, i, "--", ha="center", va="center", fontsize=5.5, color=MUTED)
                continue
            frac = (v - vmin) / (vmax - vmin)
            dark = frac < 0.4 if cmap.endswith("_r") else frac > 0.6
            ax.text(j, i, format(v, fmt), ha="center", va="center", fontsize=5.5,
                    color="white" if dark else INK)
    ax.set_xticks(range(len(cols)), cols, fontsize=6)
    ax.set_yticks(range(len(rows)), rows, fontsize=6)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    if highlight is not None:
        ax.add_patch(Rectangle((-0.5, highlight - 0.5), len(cols), 1, fill=False,
                                   edgecolor=INK, lw=0.9))
    return image


def figure_addendum_benchmark(root: Path, out: Path) -> None:
    summary = _json(root / "addendum/v2/report/summary.json")
    r1, r2 = summary["R1_curators"], summary["R2_all"]
    fig, axes = plt.subplots(1, 3, figsize=(FULL, 3.15),
                             gridspec_kw={"wspace": 0.95, "width_ratios": [1, 1, 1.25]})

    curators = list(CURATOR_LABELS)
    m1 = np.array([[r1[c]["average_rank"].get(k, np.nan) for c, _ in COMBOS] for k in curators])
    _heat(axes[0], m1, [CURATOR_LABELS[k] for k in curators], [lab for _, lab in COMBOS],
          "Blues_r", ".2f", curators.index("combined/quality-coverage"), 1, 8)
    axes[0].set_title("(a) Average rank, 8 curators", loc="left", fontsize=7, fontweight="bold")

    methods = sorted(r2[COMBOS[0][0]]["average_rank"],
                     key=lambda m: mean(r2[c]["average_rank"][m] for c, _ in COMBOS))
    m2 = np.array([[r2[c]["average_rank"][m] for c, _ in COMBOS] for m in methods])
    _heat(axes[1], m2, [_label(m) for m in methods], [lab for _, lab in COMBOS], "Blues_r",
          ".1f", methods.index("combined/quality-coverage"), 1, 16)
    axes[1].set_title("(b) Average rank, 16 methods", loc="left", fontsize=7, fontweight="bold")

    means = r2["random_forest|f1"]["dataset_means"]
    datasets = sorted(means)
    m3 = np.array([[means[d].get(m, np.nan) if means[d].get(m) is not None else np.nan
                    for d in datasets] for m in methods], dtype=float)
    _heat(axes[2], m3, [_label(m) for m in methods], datasets, "Blues", ".2f",
          methods.index("combined/quality-coverage"), 0, 1)
    axes[2].set_xticks(range(len(datasets)), datasets, rotation=35, ha="right", fontsize=6)
    axes[2].set_title("(c) RF F1, dataset means", loc="left", fontsize=7, fontweight="bold")
    _save(fig, out, "addendum-benchmark")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root: Path = args.root
    out = root / "paper/rcqasyn-ieee/figures"
    out.mkdir(parents=True, exist_ok=True)
    _style()
    figure_audit(root, out)
    figure_construction(root, out)
    figure_uncertainty(root, out)
    figure_fresh(root, out)
    figure_datasets(root, out)
    figure_addendum_geometry(root, out)
    figure_addendum_benchmark(root, out)


if __name__ == "__main__":
    main()
