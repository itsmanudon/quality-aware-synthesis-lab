# Slide numbers: exploratory addendum v1

**Label every number on the slide: "Exploratory addendum, declared after the main study."**
These are not canonical results and carry no significance claim. Paths are relative to
`artifacts/reports/exploratory-addendum-v1/`. `summary.json` paths use `/`-separated keys.
`results.csv` line numbers count the header as line 1.

| # | Number | What it says | Source |
|---|---|---|---|
| 1 | **8 datasets: 4 up / 1 down / 3 tied (LR); 6 up / 2 down (RF)**. Median F1 difference **+0.001 (LR)** and **+0.013 (RF)**. Wilcoxon p = 0.19 / 0.31 | Quality-coverage did **not** reliably beat admitted-random selection on F1 | `summary.json` → `E4/comparisons/QC_minus_admitted_random|logistic_regression|f1` and `…|random_forest|f1` |
| 2 | **Split-level W/T/L 11/22/7 (LR), 15/15/10 (RF)** across 40 paired splits | Most per-split differences are ties or small. Wins and losses roughly balance | same keys: `total_wins`, `total_ties`, `total_losses` |
| 3 | **Coverage 0.677 vs 0.461** (abalone9-18); **0.640 vs 0.549** (yeast3); higher on **5/5** new datasets | Curation's geometric benefit replicates: more TRAIN support covered at equal budget | `summary.json` → `E1/<dataset>/geometry/combined/quality-coverage/unique_train_feature_coverage/mean` vs `…/combined/random/…` |
| 4 | **Near-duplicate rate 0.043 vs 0.357** (yeast3); **0.000 vs 0.327** (abalone9-18); lower on **5/5** | Curation removes redundancy | `summary.json` → `E1/<dataset>/geometry/<curator>/near_duplicate_rate/mean` |
| 5 | **Coverage QC 0.948 / 0.506 / 0.932 vs B2-random 0.853 / 0.419 / 0.905** (Abalone19 / Ecoli4 / page-blocks0) | At equal budget, curation covers more than the B2 rule-filter control. F1 is mixed, with no consistent winner | `summary.json` → `E2_E3/<dataset>/canonical_quality_coverage_same_environment/unique_train_feature_coverage/mean` vs `…/E3_b2_accepted_random/…` |
| 6 | **page-blocks0 TSTR F1 0.446 → 0.593 (LR), 0.342 → 0.631 (RF)**, but **Ecoli4 RF 0.296 → 0.250** | A real-ratio minority quota changes synthetic-only utility in **both directions**. Coverage is unchanged | `results.csv` lines 98 → 102, 100 → 104, 52 → 56 |
| 7 | **TEST positives per split: 4 (Ecoli4), 6 (Abalone19), 8 (abalone9-18), 10 (yeast4)** | Utility differences on these datasets rest on a handful of positive records | `summary.json` → `E4/per_dataset/<dataset>/test_positive_n_by_split` |
| 8 | **vehicle0: 1,400 / 1,400** unrounded SMOTE candidates structurally non-compliant; bounded repair rescued **6 / 1,400** | Interpolating integer data breaks the schema, and ≤3-field repair cannot fix 18-integer records | `pools.json` (track `E1`, vehicle0, `generated_noncompliant_n`); `repairs.json` (`REPAIR_ELIGIBLE`) |
| 9 | Best augmentation minus real-only, RF F1: **7 / 9 datasets up, median +0.035** (p = 0.020) | Some augmentation can help random forest. **Optimistic**: the best method is chosen on the same TEST splits | `summary.json` → `E4/comparisons/best_augmentation_minus_real_only|random_forest|f1` |
| 10 | **72 / 72** canonical comparator selections reproduced identically. Max metric drift from run-v2 **0.0097** | The addendum rebuilds the canonical selections exactly. Small cross-platform (macOS vs Windows) classifier drift | `manifest.json` → `reproduction_all_selected_ids_match`, `reproduction_max_abs_metric_difference`; `reproduction.json` |

Unavailable: winequality-red-4. The supplied archive and the authorized KEEL URL were both
empty (`unavailable.json`). vehicle0 has no curator comparison in E1 or E1-repair (row 8).
