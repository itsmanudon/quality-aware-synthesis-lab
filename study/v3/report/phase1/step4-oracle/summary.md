# Phase 1 step 4: oracle upper bound for selection from the admitted SMOTE pool

K = 100 random budget-sized subsets of the combined admitted pool per split; HYBRID_MINORITY scored on VALIDATION. In-sample gain = best minus mean F1 on full validation (optimistic by construction). Honest gain = subset chosen on validation half A, scored on half B, minus mean B F1. Means over 5 splits. Observed = step-1 QC minus random F1 (1x budget). Descriptive only.

| dataset | classifier | random mean F1 | SD across subsets | in-sample gain | honest gain | observed QC - random |
| --- | --- | --- | --- | --- | --- | --- |
| Abalone19 | logistic_regression | 0.0000 | 0.0000 | +0.0000 | +0.0000 | +0.0000 |
| Abalone19 | random_forest | 0.0000 | 0.0000 | +0.0000 | +0.0000 | +0.0000 |
| Ecoli4 | logistic_regression | 0.7846 | 0.0051 | +0.0201 | +0.0000 | -0.0086 |
| Ecoli4 | random_forest | 0.8467 | 0.0797 | +0.1133 | +0.0607 | -0.0830 |
| abalone9-18 | logistic_regression | 0.4095 | 0.0370 | +0.0594 | -0.0027 | -0.0500 |
| abalone9-18 | random_forest | 0.2113 | 0.0771 | +0.1511 | +0.0682 | -0.0330 |
| ecoli1 | logistic_regression | 0.7149 | 0.0166 | +0.0396 | +0.0053 | -0.0021 |
| ecoli1 | random_forest | 0.7543 | 0.0371 | +0.0925 | -0.0614 | -0.0062 |
| segment0 | logistic_regression | 0.9943 | 0.0000 | +0.0000 | +0.0000 | +0.0000 |
| segment0 | random_forest | 0.9917 | 0.0024 | +0.0046 | -0.0001 | +0.0015 |
| yeast3 | logistic_regression | 0.7416 | 0.0075 | +0.0166 | +0.0018 | -0.0021 |
| yeast3 | random_forest | 0.7303 | 0.0225 | +0.0460 | -0.0163 | +0.0074 |
| yeast4 | logistic_regression | 0.3360 | 0.0394 | +0.0791 | -0.0178 | -0.0546 |
| yeast4 | random_forest | 0.2638 | 0.0836 | +0.1639 | -0.0532 | -0.1215 |

Median over datasets:

- logistic_regression: in-sample +0.0201, honest +0.0000
- random_forest: in-sample +0.0925, honest -0.0001

Units not ok: 5
- vehicle0 s13: MATCHED_BUDGET_SHORTFALL
- vehicle0 s29: MATCHED_BUDGET_SHORTFALL
- vehicle0 s43: MATCHED_BUDGET_SHORTFALL
- vehicle0 s61: MATCHED_BUDGET_SHORTFALL
- vehicle0 s79: MATCHED_BUDGET_SHORTFALL
