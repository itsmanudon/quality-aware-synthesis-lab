# Phase 1 step 2a: budget-size ablation (0.5x, 1x, 2x budget_rule) on validation

Scored on VALIDATION (stratified 20% of each outer TRAIN); TEST never used. Paired within dataset x split x classifier, averaged over 5 splits, then the median across datasets. Random curators are averaged over 5 selection seeds. Descriptive only; no test is run.

Rows: 3990; status counts: {'ok': 3780, 'unavailable': 210}.

## combined/quality-coverage minus combined/random

| budget scale | classifier | metric | median over datasets | datasets > 0 | datasets < 0 | n |
| --- | --- | --- | --- | --- | --- | --- |
| 0.5 | logistic_regression | f1 | -0.0000 | 2 | 4 | 7 |
| 0.5 | logistic_regression | average_precision | +0.0000 | 4 | 3 | 7 |
| 0.5 | logistic_regression | mcc | +0.0000 | 3 | 3 | 7 |
| 0.5 | random_forest | f1 | +0.0000 | 3 | 3 | 7 |
| 0.5 | random_forest | average_precision | -0.0091 | 3 | 4 | 7 |
| 0.5 | random_forest | mcc | -0.0009 | 2 | 4 | 7 |
| 1 | logistic_regression | f1 | -0.0021 | 0 | 5 | 7 |
| 1 | logistic_regression | average_precision | -0.0005 | 2 | 5 | 7 |
| 1 | logistic_regression | mcc | -0.0027 | 1 | 5 | 7 |
| 1 | random_forest | f1 | -0.0062 | 2 | 4 | 7 |
| 1 | random_forest | average_precision | -0.0128 | 1 | 6 | 7 |
| 1 | random_forest | mcc | -0.0118 | 2 | 4 | 7 |
| 2 | logistic_regression | f1 | +0.0000 | 2 | 2 | 7 |
| 2 | logistic_regression | average_precision | +0.0003 | 4 | 3 | 7 |
| 2 | logistic_regression | mcc | +0.0000 | 2 | 3 | 7 |
| 2 | random_forest | f1 | +0.0203 | 5 | 1 | 7 |
| 2 | random_forest | average_precision | +0.0089 | 5 | 2 | 7 |
| 2 | random_forest | mcc | +0.0142 | 6 | 1 | 7 |

## combined/quality-coverage minus schema/random

| budget scale | classifier | metric | median over datasets | datasets > 0 | datasets < 0 | n |
| --- | --- | --- | --- | --- | --- | --- |
| 0.5 | logistic_regression | f1 | +0.0000 | 3 | 3 | 7 |
| 0.5 | logistic_regression | average_precision | +0.0000 | 4 | 3 | 7 |
| 0.5 | logistic_regression | mcc | -0.0000 | 2 | 4 | 7 |
| 0.5 | random_forest | f1 | -0.0004 | 2 | 4 | 7 |
| 0.5 | random_forest | average_precision | -0.0093 | 0 | 7 | 7 |
| 0.5 | random_forest | mcc | -0.0004 | 2 | 4 | 7 |
| 1 | logistic_regression | f1 | -0.0043 | 0 | 5 | 7 |
| 1 | logistic_regression | average_precision | -0.0000 | 3 | 4 | 7 |
| 1 | logistic_regression | mcc | -0.0054 | 1 | 5 | 7 |
| 1 | random_forest | f1 | -0.0102 | 1 | 5 | 7 |
| 1 | random_forest | average_precision | -0.0088 | 1 | 6 | 7 |
| 1 | random_forest | mcc | -0.0063 | 2 | 5 | 7 |
| 2 | logistic_regression | f1 | +0.0000 | 2 | 2 | 7 |
| 2 | logistic_regression | average_precision | -0.0006 | 2 | 5 | 7 |
| 2 | logistic_regression | mcc | +0.0000 | 2 | 3 | 7 |
| 2 | random_forest | f1 | +0.0184 | 5 | 1 | 7 |
| 2 | random_forest | average_precision | +0.0006 | 5 | 2 | 7 |
| 2 | random_forest | mcc | +0.0184 | 6 | 1 | 7 |

## combined/random minus schema/random

| budget scale | classifier | metric | median over datasets | datasets > 0 | datasets < 0 | n |
| --- | --- | --- | --- | --- | --- | --- |
| 0.5 | logistic_regression | f1 | +0.0004 | 4 | 1 | 7 |
| 0.5 | logistic_regression | average_precision | -0.0000 | 1 | 5 | 7 |
| 0.5 | logistic_regression | mcc | +0.0004 | 4 | 1 | 7 |
| 0.5 | random_forest | f1 | -0.0044 | 2 | 4 | 7 |
| 0.5 | random_forest | average_precision | -0.0004 | 3 | 4 | 7 |
| 0.5 | random_forest | mcc | +0.0000 | 3 | 3 | 7 |
| 1 | logistic_regression | f1 | +0.0000 | 3 | 2 | 7 |
| 1 | logistic_regression | average_precision | +0.0010 | 5 | 1 | 7 |
| 1 | logistic_regression | mcc | +0.0000 | 3 | 2 | 7 |
| 1 | random_forest | f1 | +0.0004 | 4 | 2 | 7 |
| 1 | random_forest | average_precision | -0.0001 | 3 | 4 | 7 |
| 1 | random_forest | mcc | +0.0005 | 5 | 2 | 7 |
| 2 | logistic_regression | f1 | +0.0000 | 2 | 2 | 7 |
| 2 | logistic_regression | average_precision | -0.0008 | 1 | 5 | 7 |
| 2 | logistic_regression | mcc | +0.0000 | 3 | 2 | 7 |
| 2 | random_forest | f1 | -0.0019 | 1 | 5 | 7 |
| 2 | random_forest | average_precision | -0.0063 | 2 | 5 | 7 |
| 2 | random_forest | mcc | -0.0022 | 3 | 4 | 7 |

## combined/quality-coverage minus REAL_INNER_TRAIN

| budget scale | classifier | metric | median over datasets | datasets > 0 | datasets < 0 | n |
| --- | --- | --- | --- | --- | --- | --- |
| 0.5 | logistic_regression | f1 | +0.0019 | 4 | 2 | 7 |
| 0.5 | logistic_regression | average_precision | +0.0000 | 3 | 3 | 7 |
| 0.5 | logistic_regression | mcc | +0.0022 | 4 | 2 | 7 |
| 0.5 | random_forest | f1 | +0.0107 | 4 | 2 | 7 |
| 0.5 | random_forest | average_precision | -0.0003 | 3 | 4 | 7 |
| 0.5 | random_forest | mcc | +0.0100 | 4 | 2 | 7 |
| 1 | logistic_regression | f1 | +0.0019 | 4 | 2 | 7 |
| 1 | logistic_regression | average_precision | -0.0020 | 2 | 4 | 7 |
| 1 | logistic_regression | mcc | +0.0022 | 4 | 2 | 7 |
| 1 | random_forest | f1 | +0.0048 | 5 | 1 | 7 |
| 1 | random_forest | average_precision | -0.0002 | 3 | 4 | 7 |
| 1 | random_forest | mcc | +0.0022 | 4 | 2 | 7 |
| 2 | logistic_regression | f1 | +0.0019 | 4 | 2 | 7 |
| 2 | logistic_regression | average_precision | +0.0000 | 3 | 3 | 7 |
| 2 | logistic_regression | mcc | +0.0022 | 4 | 3 | 7 |
| 2 | random_forest | f1 | +0.0442 | 6 | 0 | 7 |
| 2 | random_forest | average_precision | +0.0030 | 5 | 2 | 7 |
| 2 | random_forest | mcc | +0.0425 | 6 | 0 | 7 |

## combined/random minus REAL_INNER_TRAIN

| budget scale | classifier | metric | median over datasets | datasets > 0 | datasets < 0 | n |
| --- | --- | --- | --- | --- | --- | --- |
| 0.5 | logistic_regression | f1 | +0.0004 | 4 | 2 | 7 |
| 0.5 | logistic_regression | average_precision | +0.0000 | 4 | 3 | 7 |
| 0.5 | logistic_regression | mcc | +0.0004 | 4 | 2 | 7 |
| 0.5 | random_forest | f1 | +0.0175 | 5 | 1 | 7 |
| 0.5 | random_forest | average_precision | +0.0138 | 4 | 3 | 7 |
| 0.5 | random_forest | mcc | +0.0093 | 5 | 1 | 7 |
| 1 | logistic_regression | f1 | +0.0019 | 4 | 2 | 7 |
| 1 | logistic_regression | average_precision | +0.0000 | 4 | 3 | 7 |
| 1 | logistic_regression | mcc | +0.0022 | 4 | 3 | 7 |
| 1 | random_forest | f1 | +0.0296 | 6 | 0 | 7 |
| 1 | random_forest | average_precision | +0.0010 | 4 | 3 | 7 |
| 1 | random_forest | mcc | +0.0347 | 6 | 0 | 7 |
| 2 | logistic_regression | f1 | +0.0019 | 4 | 2 | 7 |
| 2 | logistic_regression | average_precision | +0.0000 | 4 | 3 | 7 |
| 2 | logistic_regression | mcc | +0.0022 | 4 | 3 | 7 |
| 2 | random_forest | f1 | +0.0479 | 5 | 1 | 7 |
| 2 | random_forest | average_precision | +0.0049 | 4 | 3 | 7 |
| 2 | random_forest | mcc | +0.0378 | 5 | 2 | 7 |

## SMOTE+b minus REAL_INNER_TRAIN

| budget scale | classifier | metric | median over datasets | datasets > 0 | datasets < 0 | n |
| --- | --- | --- | --- | --- | --- | --- |
| 0.5 | logistic_regression | f1 | +0.0006 | 3 | 3 | 6 |
| 0.5 | logistic_regression | average_precision | -0.0001 | 2 | 3 | 6 |
| 0.5 | logistic_regression | mcc | -0.0007 | 3 | 3 | 6 |
| 0.5 | random_forest | f1 | +0.0037 | 3 | 3 | 6 |
| 0.5 | random_forest | average_precision | -0.0007 | 2 | 4 | 6 |
| 0.5 | random_forest | mcc | +0.0032 | 3 | 3 | 6 |
| 1 | logistic_regression | f1 | -0.0043 | 3 | 3 | 6 |
| 1 | logistic_regression | average_precision | -0.0001 | 2 | 3 | 6 |
| 1 | logistic_regression | mcc | -0.0077 | 2 | 4 | 6 |
| 1 | random_forest | f1 | +0.0254 | 5 | 1 | 6 |
| 1 | random_forest | average_precision | -0.0033 | 2 | 4 | 6 |
| 1 | random_forest | mcc | +0.0146 | 5 | 1 | 6 |
| 2 | logistic_regression | f1 | -0.0052 | 3 | 3 | 6 |
| 2 | logistic_regression | average_precision | -0.0009 | 2 | 3 | 6 |
| 2 | logistic_regression | mcc | -0.0063 | 3 | 3 | 6 |
| 2 | random_forest | f1 | +0.0313 | 4 | 2 | 6 |
| 2 | random_forest | average_precision | -0.0013 | 3 | 3 | 6 |
| 2 | random_forest | mcc | +0.0222 | 4 | 2 | 6 |

## SMOTENC+b minus REAL_INNER_TRAIN

| budget scale | classifier | metric | median over datasets | datasets > 0 | datasets < 0 | n |
| --- | --- | --- | --- | --- | --- | --- |
| 0.5 | logistic_regression | f1 | +0.0150 | 1 | 0 | 2 |
| 0.5 | logistic_regression | average_precision | -0.0050 | 0 | 2 | 2 |
| 0.5 | logistic_regression | mcc | +0.0047 | 1 | 0 | 2 |
| 0.5 | random_forest | f1 | -0.0044 | 0 | 1 | 2 |
| 0.5 | random_forest | average_precision | +0.0474 | 2 | 0 | 2 |
| 0.5 | random_forest | mcc | -0.0098 | 0 | 1 | 2 |
| 1 | logistic_regression | f1 | +0.0406 | 1 | 0 | 2 |
| 1 | logistic_regression | average_precision | +0.0032 | 1 | 1 | 2 |
| 1 | logistic_regression | mcc | +0.0233 | 1 | 0 | 2 |
| 1 | random_forest | f1 | +0.0797 | 1 | 0 | 2 |
| 1 | random_forest | average_precision | +0.0159 | 2 | 0 | 2 |
| 1 | random_forest | mcc | +0.0691 | 1 | 0 | 2 |
| 2 | logistic_regression | f1 | +0.0749 | 1 | 0 | 2 |
| 2 | logistic_regression | average_precision | +0.0109 | 1 | 1 | 2 |
| 2 | logistic_regression | mcc | +0.0552 | 1 | 1 | 2 |
| 2 | random_forest | f1 | +0.0332 | 1 | 0 | 2 |
| 2 | random_forest | average_precision | +0.0104 | 2 | 0 | 2 |
| 2 | random_forest | mcc | +0.0195 | 1 | 1 | 2 |

## Validation minority rows per dataset (min-max over splits)

| dataset | min | max |
| --- | --- | --- |
| Abalone19 | 5 | 5 |
| Ecoli4 | 3 | 3 |
| abalone9-18 | 7 | 7 |
| ecoli1 | 12 | 12 |
| segment0 | 53 | 53 |
| vehicle0 | 32 | 32 |
| yeast3 | 26 | 26 |
| yeast4 | 8 | 8 |

## Rows not ok: 210

- ('vehicle0', 'combined/coverage-greedy', 'unavailable', 'MATCHED_BUDGET_SHORTFALL'): 15
- ('vehicle0', 'combined/farthest-first', 'unavailable', 'MATCHED_BUDGET_SHORTFALL'): 15
- ('vehicle0', 'combined/quality-coverage', 'unavailable', 'MATCHED_BUDGET_SHORTFALL'): 15
- ('vehicle0', 'combined/random/s13', 'unavailable', 'MATCHED_BUDGET_SHORTFALL'): 15
- ('vehicle0', 'combined/random/s29', 'unavailable', 'MATCHED_BUDGET_SHORTFALL'): 15
- ('vehicle0', 'combined/random/s43', 'unavailable', 'MATCHED_BUDGET_SHORTFALL'): 15
- ('vehicle0', 'combined/random/s61', 'unavailable', 'MATCHED_BUDGET_SHORTFALL'): 15
- ('vehicle0', 'combined/random/s79', 'unavailable', 'MATCHED_BUDGET_SHORTFALL'): 15
- ('vehicle0', 'combined/source-order', 'unavailable', 'MATCHED_BUDGET_SHORTFALL'): 15
- ('vehicle0', 'schema/random/s13', 'unavailable', 'MATCHED_BUDGET_SHORTFALL'): 15
- ('vehicle0', 'schema/random/s29', 'unavailable', 'MATCHED_BUDGET_SHORTFALL'): 15
- ('vehicle0', 'schema/random/s43', 'unavailable', 'MATCHED_BUDGET_SHORTFALL'): 15
- ('vehicle0', 'schema/random/s61', 'unavailable', 'MATCHED_BUDGET_SHORTFALL'): 15
- ('vehicle0', 'schema/random/s79', 'unavailable', 'MATCHED_BUDGET_SHORTFALL'): 15

## Pool failures: 0

