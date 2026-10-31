# Phase 1: U2's five learners on dev VALIDATION (2-fold cross-fit over halves)

Parameters (U2 search spaces, 10 candidates, default first) and the F1 threshold chosen on one validation half, scored on the other, then swapped and averaged. No outer refit, no TEST. Training sets from the step-1 SMOTE pool. Paired per dataset x split x learner, averaged over 5 splits; median over datasets. Descriptive only.

## combined/quality-coverage minus combined/random

| learner | metric | median over datasets | datasets > 0 | datasets < 0 | n |
| --- | --- | --- | --- | --- | --- |
| logistic_regression | f1 | +0.0000 | 3 | 3 | 7 |
| logistic_regression | average_precision | +0.0000 | 3 | 3 | 7 |
| logistic_regression | mcc | +0.0000 | 3 | 3 | 7 |
| mlp | f1 | +0.0007 | 4 | 1 | 7 |
| mlp | average_precision | +0.0024 | 4 | 3 | 7 |
| mlp | mcc | +0.0128 | 4 | 1 | 7 |
| random_forest | f1 | -0.0077 | 2 | 4 | 7 |
| random_forest | average_precision | -0.0232 | 2 | 5 | 7 |
| random_forest | mcc | -0.0058 | 2 | 4 | 7 |
| svm | f1 | -0.0065 | 3 | 4 | 7 |
| svm | average_precision | +0.0004 | 4 | 3 | 7 |
| svm | mcc | -0.0041 | 3 | 4 | 7 |
| xgboost | f1 | -0.0030 | 3 | 4 | 7 |
| xgboost | average_precision | -0.0003 | 2 | 4 | 7 |
| xgboost | mcc | -0.0074 | 2 | 5 | 7 |

## combined/random minus REAL_INNER_TRAIN

| learner | metric | median over datasets | datasets > 0 | datasets < 0 | n |
| --- | --- | --- | --- | --- | --- |
| logistic_regression | f1 | -0.0241 | 2 | 4 | 7 |
| logistic_regression | average_precision | +0.0000 | 3 | 3 | 7 |
| logistic_regression | mcc | -0.0187 | 2 | 4 | 7 |
| mlp | f1 | -0.0013 | 3 | 4 | 7 |
| mlp | average_precision | -0.0057 | 1 | 6 | 7 |
| mlp | mcc | -0.0049 | 3 | 4 | 7 |
| random_forest | f1 | +0.0063 | 4 | 3 | 7 |
| random_forest | average_precision | +0.0002 | 4 | 3 | 7 |
| random_forest | mcc | +0.0056 | 4 | 3 | 7 |
| svm | f1 | -0.0112 | 3 | 4 | 7 |
| svm | average_precision | +0.0194 | 4 | 3 | 7 |
| svm | mcc | -0.0093 | 3 | 4 | 7 |
| xgboost | f1 | +0.0003 | 4 | 3 | 7 |
| xgboost | average_precision | +0.0038 | 5 | 2 | 7 |
| xgboost | mcc | +0.0012 | 4 | 3 | 7 |

## combined/quality-coverage minus REAL_INNER_TRAIN

| learner | metric | median over datasets | datasets > 0 | datasets < 0 | n |
| --- | --- | --- | --- | --- | --- |
| logistic_regression | f1 | -0.0316 | 2 | 4 | 7 |
| logistic_regression | average_precision | +0.0000 | 3 | 3 | 7 |
| logistic_regression | mcc | -0.0259 | 2 | 4 | 7 |
| mlp | f1 | +0.0059 | 4 | 3 | 7 |
| mlp | average_precision | -0.0033 | 3 | 4 | 7 |
| mlp | mcc | +0.0067 | 4 | 3 | 7 |
| random_forest | f1 | +0.0053 | 4 | 3 | 7 |
| random_forest | average_precision | -0.0031 | 1 | 5 | 7 |
| random_forest | mcc | +0.0014 | 4 | 3 | 7 |
| svm | f1 | +0.0018 | 4 | 3 | 7 |
| svm | average_precision | -0.0206 | 3 | 4 | 7 |
| svm | mcc | +0.0022 | 4 | 3 | 7 |
| xgboost | f1 | -0.0039 | 3 | 4 | 7 |
| xgboost | average_precision | +0.0051 | 5 | 2 | 7 |
| xgboost | mcc | -0.0044 | 3 | 4 | 7 |

## SMOTE(NC)+b minus REAL_INNER_TRAIN

| learner | metric | median over datasets | datasets > 0 | datasets < 0 | n |
| --- | --- | --- | --- | --- | --- |
| logistic_regression | f1 | -0.0050 | 2 | 5 | 8 |
| logistic_regression | average_precision | +0.0006 | 4 | 2 | 8 |
| logistic_regression | mcc | -0.0061 | 3 | 4 | 8 |
| mlp | f1 | -0.0149 | 4 | 4 | 8 |
| mlp | average_precision | -0.0028 | 4 | 4 | 8 |
| mlp | mcc | -0.0169 | 4 | 4 | 8 |
| random_forest | f1 | -0.0008 | 3 | 4 | 8 |
| random_forest | average_precision | -0.0040 | 3 | 4 | 8 |
| random_forest | mcc | -0.0079 | 3 | 4 | 8 |
| svm | f1 | +0.0001 | 4 | 4 | 8 |
| svm | average_precision | +0.0211 | 6 | 2 | 8 |
| svm | mcc | -0.0019 | 3 | 5 | 8 |
| xgboost | f1 | -0.0019 | 4 | 4 | 8 |
| xgboost | average_precision | +0.0014 | 5 | 3 | 8 |
| xgboost | mcc | -0.0053 | 4 | 4 | 8 |

## REAL_INNER_TRAIN median F1 over datasets, by learner

- logistic_regression: 0.6744
- mlp: 0.7367
- random_forest: 0.7145
- svm: 0.7147
- xgboost: 0.6251

## Unavailable training sets: 15

- vehicle0 s13 combined/quality-coverage: MATCHED_BUDGET_SHORTFALL
- vehicle0 s13 combined/random/s13: MATCHED_BUDGET_SHORTFALL
- vehicle0 s13 combined/random/s29: MATCHED_BUDGET_SHORTFALL
- vehicle0 s29 combined/quality-coverage: MATCHED_BUDGET_SHORTFALL
- vehicle0 s29 combined/random/s13: MATCHED_BUDGET_SHORTFALL
- vehicle0 s29 combined/random/s29: MATCHED_BUDGET_SHORTFALL
- vehicle0 s43 combined/quality-coverage: MATCHED_BUDGET_SHORTFALL
- vehicle0 s43 combined/random/s13: MATCHED_BUDGET_SHORTFALL
- vehicle0 s43 combined/random/s29: MATCHED_BUDGET_SHORTFALL
- vehicle0 s61 combined/quality-coverage: MATCHED_BUDGET_SHORTFALL
- vehicle0 s61 combined/random/s13: MATCHED_BUDGET_SHORTFALL
- vehicle0 s61 combined/random/s29: MATCHED_BUDGET_SHORTFALL
- vehicle0 s79 combined/quality-coverage: MATCHED_BUDGET_SHORTFALL
- vehicle0 s79 combined/random/s13: MATCHED_BUDGET_SHORTFALL
- vehicle0 s79 combined/random/s29: MATCHED_BUDGET_SHORTFALL
