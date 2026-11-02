# Phase 2 five-learner check: findings and the merged_method decision

Dev data only (8 KEEL datasets x 5 split seeds x 5 folds), U2's five learners (LR, RF,
XGBoost, MLP, RBF SVM) via the pinned ml_ugo code, cross-fitted candidate and threshold
selection. 40/40 splits, 1,800 cells, none unavailable. TEST never used. Descriptive only.

## What it shows (F1, median over the five learners of per-learner dataset medians)

| design | minus random | learners > 0 | minus QC | learners > 0 | minus REAL | learners > 0 |
| --- | --- | --- | --- | --- | --- | --- |
| union, boundary beta 0.5, rho 0.5 + QC (Phase 2 screen pick) | +0.0003 | 3/5 | -0.0007 | 1/5 | -0.0026 | 2/5 |
| union, U2 difficulty x stability, rho 0.5 + QC | +0.0016 | 3/5 | -0.0018 | 1/5 | -0.0013 | 0/5 |
| smote, boundary beta 0.25, rho 0.5 + QC | -0.0006 | 2/5 | +0.0017 | 5/5 | +0.0004 | 3/5 |
| union, quality-coverage | -0.0001 | 2/5 | 0 | - | +0.0037 | 4/5 |

Every design is within about +/-0.003 F1 of random selection from the same pool and of
plain quality-coverage, for every learner; MCC shows the same picture. Random is a single
selection seed (13) here, so it is itself noisy at this scale. Utility-aware selection is
about neutral on dev data under five learners, as the LR/RF screen already suggested.

## Decision (agent, under the user's authorisation to complete the plan)

`merged_method` keeps the design pre-selected by the Phase 2 LR/RF screen: union pool,
boundary-share band beta = 0.5, keep fraction rho = 0.5, then quality-coverage to budget B.
The five-learner check was declared as a filter on that pick, not a second selection round:
the pick stays at or above random for 3 of 5 learners and is not overturned. Choosing the
U2 term instead on these numbers would pick a winner from a second look at near-zero
differences (it was negative in the screen: -0.007 LR, -0.017 RF). The near-null result is
carried into the paper as found; the frozen success criterion is unchanged.
