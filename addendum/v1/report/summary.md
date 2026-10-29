# RC-QASyn exploratory addendum v1

> **Exploratory addendum, declared after the main study; not part of the canonical tables.** Settings were committed in `configs/empirical/addendum-v1.json` (commit `ce4d7fc`) before any score; one execution (implementation `a24d4e5`). Every row is counted, including unavailable rows. No significance or state-of-the-art claim.

Rows: {'A-reproduction': 72, 'E1': 930, 'E1-repair': 120, 'E2': 12, 'E3': 60}; status {'ok': 678, 'unavailable': 516}.

## E1: fresh-split curation on new datasets (HYBRID_MINORITY, five splits)

Mean over completed splits. QC = combined/quality-coverage; AR = combined/random (admitted random); Real = REAL_TRAIN. Coverage = TRAIN distinct-feature coverage at 0.05; Near = near-duplicate rate at 0.01.

| Dataset | b | gen | noncompliant/pool | QC cov | AR cov | QC near | AR near | LR F1 Real / QC / AR | RF F1 Real / QC / AR |
|---|---|---|---|---|---|---|---|---|---|
| yeast3 | 65 | SMOTE | 0/1300 | 0.640 | 0.549 | 0.043 | 0.357 | 0.776 / 0.782 / 0.769 | 0.775 / 0.801 / 0.790 |
| yeast4 | 30 | SMOTE | 0/600 | 0.549 | 0.457 | 0.120 | 0.320 | 0.101 / 0.158 / 0.150 | 0.236 / 0.268 / 0.245 |
| vehicle0 | 70 | SMOTE | 1400/1400 | n/a | n/a | n/a | n/a | 0.927 / n/a / n/a | 0.928 / n/a / n/a |
| segment0 | 70 | SMOTE | 0/1400 | 0.263 | 0.227 | 0.374 | 0.837 | 0.988 / 0.988 / 0.988 | 0.992 / 0.991 / 0.989 |
| ecoli1 | 31 | SMOTE | 0/620 | 0.343 | 0.262 | 0.000 | 0.194 | 0.751 / 0.758 / 0.745 | 0.726 / 0.754 / 0.736 |
| winequality-red-4 | - | - | - | unavailable: SOURCE_ARCHIVE_EMPTY: the supplied winequality-red-4.zip is ... | | | | | |
| abalone9-18 | 30 | SMOTENC | 0/600 | 0.677 | 0.461 | 0.000 | 0.327 | 0.672 / 0.679 / 0.677 | 0.347 / 0.388 / 0.373 |

TSTR is unavailable for every E1 curator (minority-only pools hold one class).

## E1-repair: bounded repair of fresh pools

| Dataset | split | repair eligible / candidates | schema pool after repair | b | constructions reaching b | utility rows ok (shortfall) |
|---|---|---|---|---|---|---|
| vehicle0 | 13 | 0 / 280 | 0 | 70 | 0/6 | 0 |
| vehicle0 | 29 | 0 / 280 | 0 | 70 | 0/6 | 0 |
| vehicle0 | 43 | 2 / 280 | 2 | 70 | 0/6 | 12 |
| vehicle0 | 61 | 4 / 280 | 4 | 70 | 0/6 | 12 |
| vehicle0 | 79 | 0 / 280 | 0 | 70 | 0/6 | 0 |

E1-repair utility rows: {'unavailable': 96, 'ok': 24}. Every E1-repair construction fell short of b, so its ok utility rows train on 2-4 repaired records instead of b and are MATCHED_BUDGET_SHORTFALL, not matched-budget results. Not applicable (no integer-declared features, repair NOT_NEEDED): yeast3, yeast4, segment0, ecoli1, abalone9-18.

## E2 and E3: historical Track A at fixed budgets

QC = canonical quality-coverage (quota 0.5b); QC-ratio = E2 quota floor(b x TRAIN minority fraction); AR = admitted random (mean of 5 seeds); B2 = E3 random subsets of the B2-accepted complete pool (mean of 5 seeds). Same-environment re-scores.

| Dataset | Design | quota | minority selected | cov | near | exact | LR TSTR F1 | LR HYB F1 | RF TSTR F1 | RF HYB F1 | LR HYB AP | LR HYB MCC |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Abalone19 | QC | 28 | 35 | 0.948 | 0.000 | 0.000 | 0.031 | 0.000 | 0.030 | 0.000 | 0.017 | 0.000 |
| Abalone19 | QC-ratio (E2) | 0 | 32 | 0.948 | 0.000 | 0.000 | 0.029 | 0.000 | 0.027 | 0.000 | 0.018 | 0.000 |
| Abalone19 | AR x5 | - | 22/25/28/26/24 | 0.833 | 0.493 | 0.236 | 0.022 | 0.000 | 0.030 | 0.000 | 0.021 | 0.000 |
| Abalone19 | B2 x5 (E3) | - | 31/27/31/32/32 | 0.853 | 0.232 | 0.000 | 0.026 | 0.000 | 0.030 | 0.000 | 0.015 | 0.000 |
| Ecoli4 | QC | 35 | 35 | 0.506 | 0.000 | 0.000 | 0.205 | 1.000 | 0.296 | 1.000 | 1.000 | 1.000 |
| Ecoli4 | QC-ratio (E2) | 4 | 32 | 0.506 | 0.000 | 0.000 | 0.190 | 1.000 | 0.250 | 1.000 | 1.000 | 1.000 |
| Ecoli4 | AR x5 | - | 31/30/31/32/33 | 0.439 | 0.197 | 0.117 | 0.217 | 0.933 | 0.231 | 1.000 | 1.000 | 0.932 |
| Ecoli4 | B2 x5 (E3) | - | 38/40/40/42/41 | 0.419 | 0.049 | 0.000 | 0.213 | 0.933 | 0.271 | 1.000 | 1.000 | 0.932 |
| page-blocks0 | QC | 24 | 24 | 0.932 | 0.327 | 0.000 | 0.446 | 0.715 | 0.342 | 0.863 | 0.744 | 0.699 |
| page-blocks0 | QC-ratio (E2) | 5 | 15 | 0.932 | 0.000 | 0.000 | 0.593 | 0.722 | 0.631 | 0.873 | 0.747 | 0.705 |
| page-blocks0 | AR x5 | - | 26/22/26/23/24 | 0.914 | 0.702 | 0.082 | 0.535 | 0.715 | 0.475 | 0.869 | 0.743 | 0.699 |
| page-blocks0 | B2 x5 (E3) | - | 25/23/24/21/26 | 0.905 | 0.506 | 0.000 | 0.421 | 0.715 | 0.438 | 0.867 | 0.744 | 0.699 |

Pools: Abalone19: combined-review 170, B2-accepted complete 138, TRAIN minority fraction 0.0078; Ecoli4: combined-review 162, B2-accepted complete 174, TRAIN minority fraction 0.0595; page-blocks0: combined-review 119, B2-accepted complete 116, TRAIN minority fraction 0.1021.
Same-environment re-scoring of canonical comparators: selected records identical (True); maximum absolute metric difference from run-v2 0.0097 (cross-platform).

## E4: across-dataset summary (fresh splits)

Dataset-level mean difference over paired splits (W/T/L over splits). Canonical datasets come from run-v2 Track B unchanged.

| Dataset | TEST pos/split | LR F1 QC-AR | RF F1 QC-AR | LR F1 QC-Real | RF F1 QC-Real | LR F1 Best-Real (method) | RF F1 Best-Real (method) |
|---|---|---|---|---|---|---|---|
| Abalone19 | 6/6/6/6/6 | +0.000 (0/5/0) | -0.057 (0/4/1) | +0.000 (0/5/0) | +0.000 (0/5/0) | +0.000 (0/5/0) schema/random | +0.057 (1/4/0) combined/random |
| Ecoli4 | 4/4/4/4/4 | +0.000 (0/5/0) | +0.038 (1/4/0) | -0.090 (0/3/2) | +0.186 (5/0/0) | -0.090 (0/3/2) schema/random | +0.219 (5/0/0) combined/source-order |
| page-blocks0 | 112/112/112/112/112 | -0.003 (1/1/3) | -0.007 (2/0/3) | +0.010 (5/0/0) | -0.011 (1/0/4) | +0.013 (5/0/0) combined/random | +0.006 (5/0/0) SMOTE+b |
| yeast3 | 33/33/33/33/33 | +0.013 (3/1/1) | +0.011 (3/0/2) | +0.006 (3/0/2) | +0.026 (4/0/1) | +0.006 (3/0/2) combined/quality-coverage | +0.035 (5/0/0) combined/coverage-greedy |
| yeast4 | 10/10/10/10/10 | +0.008 (2/3/0) | +0.023 (2/2/1) | +0.057 (2/2/1) | +0.031 (2/1/2) | +0.102 (3/1/1) combined/farthest-first | +0.031 (2/1/2) combined/quality-coverage |
| vehicle0 | 40/40/40/40/40 | n/a | n/a | n/a | n/a | +0.004 (2/2/1) RandomOverSampler+b | -0.001 (3/0/2) RandomOverSampler+b |
| segment0 | 66/66/66/66/66 | +0.000 (0/5/0) | +0.002 (1/4/0) | +0.000 (0/5/0) | -0.002 (0/4/1) | +0.000 (0/5/0) schema/random | -0.002 (0/4/1) combined/quality-coverage |
| ecoli1 | 15/15/15/15/15 | +0.013 (3/1/1) | +0.018 (3/0/2) | +0.006 (2/0/3) | +0.028 (3/1/1) | +0.011 (2/0/3) combined/coverage-greedy | +0.056 (4/0/1) combined/farthest-first |
| winequality-red-4 | - | unavailable | | | | | |
| abalone9-18 | 8/8/8/8/8 | +0.002 (2/1/2) | +0.015 (3/1/1) | +0.007 (3/0/2) | +0.041 (3/0/2) | +0.013 (3/1/1) combined/source-order | +0.059 (3/0/2) combined/coverage-greedy |

| Comparison | Clf | Metric | datasets (+/-/0) | split W/T/L | median diff | Wilcoxon n, p (exploratory) |
|---|---|---|---|---|---|---|
| QC_minus_admitted_random | LR | f1 | 4/1/3 | 11/22/7 | +0.001 | 8, 0.188 |
| QC_minus_real_only | LR | f1 | 5/1/2 | 15/15/10 | +0.006 | 8, 0.438 |
| best_augmentation_minus_real_only | LR | f1 | 6/1/2 | 18/17/10 | +0.006 | 9, 0.219 |
| QC_minus_admitted_random | LR | average_precision | 3/4/1 | 17/7/16 | -0.001 | 8, 0.469 |
| QC_minus_real_only | LR | average_precision | 3/5/0 | 18/6/16 | -0.000 | 8, 0.461 |
| best_augmentation_minus_real_only | LR | average_precision | 6/2/1 | 25/9/11 | +0.003 | 9, 0.055 |
| QC_minus_admitted_random | RF | f1 | 6/2/0 | 15/15/10 | +0.013 | 8, 0.312 |
| QC_minus_real_only | RF | f1 | 5/2/1 | 18/11/11 | +0.027 | 8, 0.078 |
| best_augmentation_minus_real_only | RF | f1 | 7/2/0 | 28/9/8 | +0.035 | 9, 0.020 |
| QC_minus_admitted_random | RF | average_precision | 5/3/0 | 19/6/15 | +0.002 | 8, 1.000 |
| QC_minus_real_only | RF | average_precision | 5/3/0 | 17/5/18 | +0.002 | 8, 0.461 |
| best_augmentation_minus_real_only | RF | average_precision | 8/1/0 | 23/6/16 | +0.021 | 9, 0.012 |

Excluded from QC comparisons: vehicle0, winequality-red-4. best_augmentation is chosen on the same TEST splits and is optimistic by construction.

## Conclusion

**Curation did not beat random selection on classifier performance.** On the eight datasets where it could be evaluated (three canonical, five new), quality-coverage minus admitted-random differences were small and mixed in sign (median F1 difference +0.001 for logistic regression and +0.013 for random forest; exploratory Wilcoxon p between 0.19 and 1.00 for F1 and AP). Its geometric benefit did hold up: on all five new datasets with usable pools, quality-coverage covered more of the training data with fewer near-duplicates than random selection from the same admitted pool (for example 0.677 vs 0.461 coverage on abalone9-18), and on the historical pools it also covered more than equal-budget random subsets of B2-accepted records. Setting the minority quota to the real class ratio left coverage unchanged, raised pure synthetic-only F1 on page-blocks0 but lowered it on Ecoli4 and Abalone19, and barely moved hybrid results, while the equal-budget B2 control was neither consistently better nor worse than quality-coverage. These results are exploratory: several datasets have only 4-10 positive test records per split, vehicle0's unrounded SMOTE candidates were all structurally non-compliant (bounded repair rescued 6 of 1,400), winequality-red-4 could not be obtained, and the occasional advantage of the best augmentation over real-only training is selected on the same test splits and is therefore optimistic.
