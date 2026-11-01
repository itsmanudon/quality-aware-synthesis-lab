# Phase 2: utility-aware selection on dev data (5-fold cross-fit inside TRAIN)

Pooled over the 5 held-out folds of each outer TRAIN; F1 at the cross-fitted threshold (each fold's threshold chosen on the other 4 folds, U2's rule). Differences are paired per dataset x split x classifier, averaged over the 5 split seeds, then the median over datasets (with counts above / below zero). `random` = mean of 5 random selections from the same admitted pool. Descriptive only; dev data; TEST never used.

## Pool `llm`: F1 (cross-fitted threshold)

| design | classifier | median F1 | minus random | +/- | minus QC | minus REAL | +/- | datasets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| qc-quota-0.5 | logistic_regression | 0.7413 | -0.0017 | 3/4 | +nan | -0.0077 | 2/5 | 7 |
| qc-quota-1.0 | logistic_regression | 0.7402 | +0.0068 | 5/2 | +nan | -0.0105 | 3/4 | 7 |
| qc-quota-real | logistic_regression | 0.7385 | +0.0063 | 4/3 | +nan | +0.0258 | 4/3 | 7 |
| random(mean of 5) | logistic_regression | 0.7393 | +0.0000 | 0/0 | +nan | -0.0140 | 3/4 | 7 |
| qc-quota-0.5 | random_forest | 0.7397 | +0.0060 | 5/2 | +nan | +0.0099 | 5/2 | 7 |
| qc-quota-1.0 | random_forest | 0.7509 | +0.0109 | 4/3 | +nan | +0.0167 | 6/1 | 7 |
| qc-quota-real | random_forest | 0.7383 | -0.0220 | 1/6 | +nan | -0.0170 | 3/4 | 7 |
| random(mean of 5) | random_forest | 0.7337 | +0.0000 | 0/0 | +nan | -0.0006 | 3/4 | 7 |

## Pool `llm+round`: F1 (cross-fitted threshold)

| design | classifier | median F1 | minus random | +/- | minus QC | minus REAL | +/- | datasets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| qc-quota-0.5 | logistic_regression | 0.9052 | +0.0063 | 1/0 | +nan | -0.0077 | 0/1 | 1 |
| qc-quota-1.0 | logistic_regression | 0.9024 | +0.0035 | 1/0 | +nan | -0.0105 | 0/1 | 1 |
| qc-quota-real | logistic_regression | 0.9052 | +0.0063 | 1/0 | +nan | -0.0077 | 0/1 | 1 |
| random(mean of 5) | logistic_regression | 0.8989 | +0.0000 | 0/0 | +nan | -0.0140 | 0/1 | 1 |
| qc-quota-0.5 | random_forest | 0.9016 | -0.0024 | 0/1 | +nan | -0.0041 | 0/1 | 1 |
| qc-quota-1.0 | random_forest | 0.9034 | -0.0005 | 0/1 | +nan | -0.0022 | 0/1 | 1 |
| qc-quota-real | random_forest | 0.8820 | -0.0220 | 0/1 | +nan | -0.0237 | 0/1 | 1 |
| random(mean of 5) | random_forest | 0.9040 | +0.0000 | 0/0 | +nan | -0.0017 | 0/1 | 1 |

## References minus REAL_INNER_TRAIN (F1, cross-fitted threshold)

| method | classifier | median F1 | minus REAL | +/- | datasets |
| --- | --- | --- | --- | --- | --- |

REAL_INNER_TRAIN median F1: logistic_regression 0.7498, random_forest 0.7120

## Tuning stability (split seeds {13, 29} vs {43, 61, 79})

Spearman correlation of the design rankings (median F1 minus random) between the two halves of the split seeds. Near 0 or negative: the ordering is noise.

| pool | classifier | designs | Spearman |
| --- | --- | --- | --- |

## Unavailable cells: 1

- segment0 llm/*: 1 (EMPTY_POOL)

## Pools (summed over 1 split(s) x 5 folds)

| dataset | pool | candidates | schema | combined admitted | budget sum | exact copy of inner train | exact copy of reference | exact duplicate within pool |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Abalone19 | llm | 591 | 591 | 510 | 150 | 0 | 0 | 3 |
| Ecoli4 | llm | 573 | 573 | 484 | 150 | 32 | 32 | 24 |
| abalone9-18 | llm | 591 | 591 | 513 | 150 | 0 | 0 | 0 |
| ecoli1 | llm | 591 | 591 | 507 | 150 | 31 | 31 | 29 |
| segment0 | llm | 0 | 0 | 0 | 350 | 0 | 0 | 0 |
| vehicle0 | llm | 1199 | 1199 | 1051 | 320 | 56 | 56 | 60 |
| vehicle0 | llm+round | 1199 | 1199 | 1051 | 320 | 56 | 56 | 60 |
| yeast3 | llm | 762 | 762 | 655 | 260 | 196 | 196 | 212 |
| yeast4 | llm | 456 | 456 | 396 | 150 | 47 | 47 | 47 |

## Repair variant integer-round-all-half-even-v3

- vehicle0 llm+round: complete_unchanged 1199
