# Phase 1 step 3: RC-QASyn quality gate on U2, UGO and SMOTE-family pools

Pools exported by `u2_pools.py` (pinned ml_ugo, unmodified samplers, in-loop learner = U2 logistic regression at default parameters) on the same inner TRAIN / VALIDATION rows as step 1; target = minority + 4 x budget. Gate = frozen rcqasyn checks. Exact-copy counts are copying diagnostics, not privacy results. VALIDATION only; descriptive only.

## Gate totals over 8 dev datasets x 5 splits

| generator | candidates | structurally incomplete | repair-eligible | not repairable | duplicate within pool | exact copy of inner TRAIN | non-one-hot categorical | schema-admitted | combined-admitted (q=0.90) | splits with pool < budget |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| smote | 6720 | 1280 (19.0%) | 0 (0.0%) | 1280 (19.0%) | 8 (0.1%) | 0 (0.0%) | 0 (0.0%) | 5440 (81.0%) | 4652 (69.2%) | 5 of 40 |
| kmeans_smote | 6720 | 1280 (19.0%) | 0 (0.0%) | 1280 (19.0%) | 31 (0.5%) | 0 (0.0%) | 0 (0.0%) | 5440 (81.0%) | 4663 (69.4%) | 5 of 40 |
| rwo | 6720 | 1280 (19.0%) | 0 (0.0%) | 1280 (19.0%) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 5440 (81.0%) | 4690 (69.8%) | 5 of 40 |
| original_ugo | 5297 | 1280 (24.2%) | 0 (0.0%) | 1280 (24.2%) | 21 (0.4%) | 0 (0.0%) | 0 (0.0%) | 4017 (75.8%) | 3401 (64.2%) | 14 of 40 |
| u2_native | 4546 | 1026 (22.6%) | 0 (0.0%) | 1026 (22.6%) | 77 (1.7%) | 0 (0.0%) | 0 (0.0%) | 3520 (77.4%) | 2998 (65.9%) | 10 of 40 |
| u2_flow_gate | 4358 | 1001 (23.0%) | 0 (0.0%) | 1001 (23.0%) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 3357 (77.0%) | 2863 (65.7%) | 17 of 40 |

## Per dataset (sum over 5 splits): candidates / structurally complete / combined-admitted

| dataset | smote | kmeans_smote | rwo | original_ugo | u2_native | u2_flow_gate |
| --- | --- | --- | --- | --- | --- | --- |
| Abalone19 | 600 / 600 / 511 | 600 / 600 / 512 | 600 / 600 / 518 | 0 / 0 / 0 | 190 / 190 / 166 | 158 / 158 / 139 |
| Ecoli4 | 600 / 600 / 509 | 600 / 600 / 498 | 600 / 600 / 516 | 585 / 585 / 491 | 60 / 60 / 48 | 60 / 60 / 48 |
| abalone9-18 | 600 / 600 / 526 | 600 / 600 / 509 | 600 / 600 / 522 | 92 / 92 / 76 | 242 / 242 / 210 | 150 / 150 / 132 |
| ecoli1 | 600 / 600 / 526 | 600 / 600 / 532 | 600 / 600 / 535 | 420 / 420 / 353 | 286 / 286 / 252 | 326 / 326 / 287 |
| segment0 | 1400 / 1400 / 1183 | 1400 / 1400 / 1231 | 1400 / 1400 / 1190 | 1400 / 1400 / 1196 | 1400 / 1400 / 1186 | 1358 / 1358 / 1154 |
| vehicle0 | 1280 / 0 / 0 | 1280 / 0 / 0 | 1280 / 0 / 0 | 1280 / 0 / 0 | 1026 / 0 / 0 | 1001 / 0 / 0 |
| yeast3 | 1040 / 1040 / 880 | 1040 / 1040 / 866 | 1040 / 1040 / 893 | 1040 / 1040 / 876 | 1026 / 1026 / 866 | 1009 / 1009 / 855 |
| yeast4 | 600 / 600 / 517 | 600 / 600 / 515 | 600 / 600 / 516 | 480 / 480 / 409 | 316 / 316 / 270 | 296 / 296 / 248 |

## F1: combined/quality-coverage minus combined/random, per generator pool

| generator | classifier | median over datasets | datasets > 0 | datasets < 0 | n |
| --- | --- | --- | --- | --- | --- |
| kmeans_smote | logistic_regression | +0.0000 | 1 | 3 | 7 |
| kmeans_smote | random_forest | +0.0024 | 5 | 1 | 7 |
| original_ugo | logistic_regression | +0.0000 | 3 | 0 | 6 |
| original_ugo | random_forest | -0.0061 | 2 | 4 | 6 |
| rwo | logistic_regression | +0.0000 | 3 | 2 | 7 |
| rwo | random_forest | +0.0000 | 3 | 3 | 7 |
| smote | logistic_regression | -0.0021 | 1 | 4 | 7 |
| smote | random_forest | +0.0000 | 3 | 3 | 7 |
| u2_flow_gate | logistic_regression | +0.0000 | 1 | 2 | 5 |
| u2_flow_gate | random_forest | +0.0014 | 3 | 1 | 5 |
| u2_native | logistic_regression | +0.0016 | 3 | 1 | 6 |
| u2_native | random_forest | +0.0010 | 3 | 2 | 6 |

## F1: combined/random from each generator pool minus REAL_INNER_TRAIN

| generator | classifier | median over datasets | datasets > 0 | datasets < 0 | n |
| --- | --- | --- | --- | --- | --- |
| kmeans_smote | logistic_regression | +0.0000 | 3 | 2 | 7 |
| kmeans_smote | random_forest | +0.0209 | 4 | 2 | 7 |
| original_ugo | logistic_regression | -0.0007 | 3 | 3 | 6 |
| original_ugo | random_forest | +0.0031 | 3 | 3 | 6 |
| rwo | logistic_regression | +0.0019 | 4 | 2 | 7 |
| rwo | random_forest | +0.0250 | 6 | 0 | 7 |
| smote | logistic_regression | +0.0019 | 4 | 2 | 7 |
| smote | random_forest | +0.0288 | 6 | 0 | 7 |
| u2_flow_gate | logistic_regression | +0.0019 | 3 | 1 | 5 |
| u2_flow_gate | random_forest | +0.0269 | 3 | 1 | 5 |
| u2_native | logistic_regression | +0.0089 | 4 | 1 | 6 |
| u2_native | random_forest | +0.0177 | 4 | 1 | 6 |

## F1: combined/quality-coverage from each generator pool minus REAL_INNER_TRAIN

| generator | classifier | median over datasets | datasets > 0 | datasets < 0 | n |
| --- | --- | --- | --- | --- | --- |
| kmeans_smote | logistic_regression | +0.0000 | 3 | 2 | 7 |
| kmeans_smote | random_forest | +0.0328 | 5 | 1 | 7 |
| original_ugo | logistic_regression | -0.0007 | 3 | 3 | 6 |
| original_ugo | random_forest | +0.0102 | 4 | 2 | 6 |
| rwo | logistic_regression | +0.0019 | 4 | 2 | 7 |
| rwo | random_forest | +0.0019 | 4 | 2 | 7 |
| smote | logistic_regression | +0.0019 | 4 | 2 | 7 |
| smote | random_forest | +0.0048 | 5 | 1 | 7 |
| u2_flow_gate | logistic_regression | +0.0019 | 3 | 1 | 5 |
| u2_flow_gate | random_forest | +0.0318 | 3 | 1 | 5 |
| u2_native | logistic_regression | +0.0151 | 4 | 1 | 6 |
| u2_native | random_forest | +0.0359 | 5 | 0 | 6 |

## Curator rows not ok: 619

- ('kmeans_smote', 'vehicle0', 'unavailable', 'MATCHED_BUDGET_SHORTFALL'): 70
- ('original_ugo', 'vehicle0', 'unavailable', 'MATCHED_BUDGET_SHORTFALL'): 70
- ('rwo', 'vehicle0', 'unavailable', 'MATCHED_BUDGET_SHORTFALL'): 70
- ('smote', 'vehicle0', 'unavailable', 'MATCHED_BUDGET_SHORTFALL'): 70
- ('u2_flow_gate', 'Abalone19', 'unavailable', 'MATCHED_BUDGET_SHORTFALL'): 28
- ('u2_flow_gate', 'Ecoli4', 'unavailable', 'MATCHED_BUDGET_SHORTFALL'): 56
- ('u2_flow_gate', 'abalone9-18', 'unavailable', 'MATCHED_BUDGET_SHORTFALL'): 55
- ('u2_flow_gate', 'vehicle0', 'unavailable', 'MATCHED_BUDGET_SHORTFALL'): 70
- ('u2_native', 'Abalone19', 'unavailable', 'MATCHED_BUDGET_SHORTFALL'): 4
- ('u2_native', 'Ecoli4', 'unavailable', 'MATCHED_BUDGET_SHORTFALL'): 56
- ('u2_native', 'vehicle0', 'unavailable', 'MATCHED_BUDGET_SHORTFALL'): 70

## Pools not ok: 0

