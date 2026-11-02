# Phase 2 five-learner check (U2's five learners, cross-fitted selection)

8 dev datasets x 5 split seeds x 5 folds. Pool family: the rounded pool stands in where integer fields are declared (vehicle0). Medians over datasets of per-dataset means over split seeds; counts are datasets above / below zero. Descriptive only; dev data; TEST never used.

## F1: designs minus random / QC / REAL, per learner

| pool | design | learner | median | minus random | +/- | minus QC | +/- | minus REAL | +/- |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| - | SMOTE+b | logistic_regression | 0.8023 | +nan | 0/0 | +nan | 0/0 | +0.0012 | 4/2 |
| - | SMOTE+b | mlp | 0.7880 | +nan | 0/0 | +nan | 0/0 | +0.0001 | 4/2 |
| - | SMOTE+b | random_forest | 0.7773 | +nan | 0/0 | +nan | 0/0 | +0.0037 | 4/2 |
| - | SMOTE+b | svm | 0.8228 | +nan | 0/0 | +nan | 0/0 | -0.0011 | 3/3 |
| - | SMOTE+b | xgboost | 0.7614 | +nan | 0/0 | +nan | 0/0 | -0.0048 | 3/3 |
| - | SMOTENC+b | logistic_regression | 0.2936 | +nan | 0/0 | +nan | 0/0 | +0.0196 | 2/0 |
| - | SMOTENC+b | mlp | 0.2393 | +nan | 0/0 | +nan | 0/0 | +0.0100 | 1/1 |
| - | SMOTENC+b | random_forest | 0.2013 | +nan | 0/0 | +nan | 0/0 | -0.0094 | 0/2 |
| - | SMOTENC+b | svm | 0.2433 | +nan | 0/0 | +nan | 0/0 | +0.0004 | 1/1 |
| - | SMOTENC+b | xgboost | 0.2017 | +nan | 0/0 | +nan | 0/0 | -0.0065 | 1/1 |
| smote | boundary0.25/rho0.5+qc | logistic_regression | 0.7437 | -0.0006 | 4/4 | +0.0017 | 6/2 | +0.0039 | 6/2 |
| smote | boundary0.25/rho0.5+qc | mlp | 0.7682 | -0.0010 | 4/4 | +0.0054 | 6/2 | -0.0012 | 3/5 |
| smote | boundary0.25/rho0.5+qc | random_forest | 0.7734 | +0.0094 | 6/2 | +0.0001 | 4/4 | +0.0066 | 6/2 |
| smote | boundary0.25/rho0.5+qc | svm | 0.7740 | -0.0079 | 1/7 | +0.0009 | 4/4 | -0.0025 | 3/5 |
| smote | boundary0.25/rho0.5+qc | xgboost | 0.7687 | +0.0053 | 4/4 | +0.0097 | 6/2 | +0.0004 | 4/4 |
| smote | quality-coverage | logistic_regression | 0.7412 | +0.0030 | 5/3 | +0.0000 | 0/0 | +0.0012 | 6/2 |
| smote | quality-coverage | mlp | 0.7599 | -0.0005 | 4/4 | +0.0000 | 0/0 | -0.0007 | 3/5 |
| smote | quality-coverage | random_forest | 0.7726 | +0.0044 | 5/3 | +0.0000 | 0/0 | -0.0022 | 3/5 |
| smote | quality-coverage | svm | 0.7687 | -0.0044 | 3/5 | +0.0000 | 0/0 | -0.0025 | 4/4 |
| smote | quality-coverage | xgboost | 0.7456 | -0.0018 | 2/6 | +0.0000 | 0/0 | -0.0003 | 4/4 |
| smote | random/s13 | logistic_regression | 0.7410 | +0.0000 | 0/0 | -0.0030 | 3/5 | +0.0052 | 6/2 |
| smote | random/s13 | mlp | 0.7654 | +0.0000 | 0/0 | +0.0005 | 4/4 | -0.0016 | 3/5 |
| smote | random/s13 | random_forest | 0.7700 | +0.0000 | 0/0 | -0.0044 | 3/5 | -0.0072 | 4/4 |
| smote | random/s13 | svm | 0.7814 | +0.0000 | 0/0 | +0.0044 | 5/3 | -0.0002 | 4/4 |
| smote | random/s13 | xgboost | 0.7437 | +0.0000 | 0/0 | +0.0018 | 6/2 | -0.0056 | 2/6 |
| union | boundary0.5/rho0.5+qc | logistic_regression | 0.7479 | +0.0017 | 4/4 | +0.0027 | 6/2 | +0.0039 | 5/3 |
| union | boundary0.5/rho0.5+qc | mlp | 0.7600 | -0.0027 | 4/4 | -0.0116 | 3/5 | -0.0026 | 2/6 |
| union | boundary0.5/rho0.5+qc | random_forest | 0.7788 | +0.0043 | 5/3 | -0.0001 | 4/4 | +0.0066 | 5/3 |
| union | boundary0.5/rho0.5+qc | svm | 0.7695 | +0.0003 | 4/4 | -0.0033 | 3/5 | -0.0048 | 2/6 |
| union | boundary0.5/rho0.5+qc | xgboost | 0.7602 | -0.0037 | 2/6 | -0.0007 | 3/5 | -0.0045 | 4/4 |
| union | quality-coverage | logistic_regression | 0.7402 | -0.0001 | 4/4 | +0.0000 | 0/0 | +0.0017 | 5/3 |
| union | quality-coverage | mlp | 0.7740 | -0.0018 | 3/5 | +0.0000 | 0/0 | +0.0048 | 5/3 |
| union | quality-coverage | random_forest | 0.7623 | +0.0004 | 5/3 | +0.0000 | 0/0 | +0.0062 | 6/2 |
| union | quality-coverage | svm | 0.7672 | +0.0018 | 8/0 | +0.0000 | 0/0 | -0.0011 | 3/5 |
| union | quality-coverage | xgboost | 0.7569 | -0.0045 | 3/5 | +0.0000 | 0/0 | +0.0037 | 5/3 |
| union | random/s13 | logistic_regression | 0.7406 | +0.0000 | 0/0 | +0.0001 | 4/4 | +0.0009 | 5/3 |
| union | random/s13 | mlp | 0.7618 | +0.0000 | 0/0 | +0.0018 | 5/3 | +0.0023 | 4/4 |
| union | random/s13 | random_forest | 0.7611 | +0.0000 | 0/0 | -0.0004 | 3/5 | -0.0021 | 4/4 |
| union | random/s13 | svm | 0.7664 | +0.0000 | 0/0 | -0.0018 | 0/8 | -0.0059 | 3/5 |
| union | random/s13 | xgboost | 0.7655 | +0.0000 | 0/0 | +0.0045 | 5/3 | -0.0031 | 3/5 |
| union | u2/rho0.5+qc | logistic_regression | 0.7448 | -0.0005 | 4/4 | -0.0013 | 4/4 | -0.0002 | 4/4 |
| union | u2/rho0.5+qc | mlp | 0.7442 | -0.0042 | 3/5 | -0.0079 | 4/4 | -0.0063 | 1/7 |
| union | u2/rho0.5+qc | random_forest | 0.7819 | +0.0021 | 4/4 | -0.0024 | 3/5 | -0.0041 | 4/4 |
| union | u2/rho0.5+qc | svm | 0.7589 | +0.0020 | 5/3 | -0.0018 | 3/5 | -0.0013 | 4/4 |
| union | u2/rho0.5+qc | xgboost | 0.7423 | +0.0016 | 6/2 | +0.0003 | 4/4 | -0.0010 | 3/5 |

### F1 across the five learners

| pool | design | minus random (median of 5) | learners > 0 | minus QC | learners > 0 | minus REAL | learners > 0 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| smote | boundary0.25/rho0.5+qc | -0.0006 | 2/5 | +0.0017 | 5/5 | +0.0004 | 3/5 |
| smote | quality-coverage | -0.0005 | 2/5 | +0.0000 | 0/5 | -0.0007 | 1/5 |
| smote | random/s13 | +0.0000 | 0/5 | +0.0005 | 3/5 | -0.0016 | 1/5 |
| union | boundary0.5/rho0.5+qc | +0.0003 | 3/5 | -0.0007 | 1/5 | -0.0026 | 2/5 |
| union | quality-coverage | -0.0001 | 2/5 | +0.0000 | 0/5 | +0.0037 | 4/5 |
| union | random/s13 | +0.0000 | 0/5 | +0.0001 | 3/5 | -0.0021 | 2/5 |
| union | u2/rho0.5+qc | +0.0016 | 3/5 | -0.0018 | 1/5 | -0.0013 | 0/5 |

## MCC: designs minus random / QC / REAL, per learner

| pool | design | learner | median | minus random | +/- | minus QC | +/- | minus REAL | +/- |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| - | SMOTE+b | logistic_regression | 0.7828 | +nan | 0/0 | +nan | 0/0 | +0.0018 | 5/1 |
| - | SMOTE+b | mlp | 0.7691 | +nan | 0/0 | +nan | 0/0 | +0.0001 | 4/2 |
| - | SMOTE+b | random_forest | 0.7587 | +nan | 0/0 | +nan | 0/0 | +0.0040 | 4/2 |
| - | SMOTE+b | svm | 0.8075 | +nan | 0/0 | +nan | 0/0 | -0.0015 | 3/3 |
| - | SMOTE+b | xgboost | 0.7346 | +nan | 0/0 | +nan | 0/0 | -0.0064 | 3/3 |
| - | SMOTENC+b | logistic_regression | 0.2822 | +nan | 0/0 | +nan | 0/0 | +0.0202 | 2/0 |
| - | SMOTENC+b | mlp | 0.2226 | +nan | 0/0 | +nan | 0/0 | +0.0067 | 1/1 |
| - | SMOTENC+b | random_forest | 0.1805 | +nan | 0/0 | +nan | 0/0 | -0.0105 | 0/2 |
| - | SMOTENC+b | svm | 0.2293 | +nan | 0/0 | +nan | 0/0 | +0.0071 | 2/0 |
| - | SMOTENC+b | xgboost | 0.1818 | +nan | 0/0 | +nan | 0/0 | -0.0112 | 1/1 |
| smote | boundary0.25/rho0.5+qc | logistic_regression | 0.6887 | -0.0001 | 4/4 | +0.0016 | 5/3 | +0.0035 | 6/2 |
| smote | boundary0.25/rho0.5+qc | mlp | 0.7183 | -0.0017 | 4/4 | +0.0069 | 6/2 | -0.0014 | 3/5 |
| smote | boundary0.25/rho0.5+qc | random_forest | 0.7246 | +0.0108 | 6/2 | -0.0001 | 4/4 | +0.0086 | 6/2 |
| smote | boundary0.25/rho0.5+qc | svm | 0.7242 | -0.0127 | 1/7 | +0.0013 | 4/4 | +0.0000 | 4/4 |
| smote | boundary0.25/rho0.5+qc | xgboost | 0.7248 | +0.0061 | 4/4 | +0.0106 | 6/2 | +0.0005 | 4/4 |
| smote | quality-coverage | logistic_regression | 0.6866 | +0.0053 | 6/2 | +0.0000 | 0/0 | +0.0013 | 6/2 |
| smote | quality-coverage | mlp | 0.7100 | -0.0005 | 4/4 | +0.0000 | 0/0 | -0.0014 | 3/5 |
| smote | quality-coverage | random_forest | 0.7311 | +0.0037 | 4/4 | +0.0000 | 0/0 | -0.0023 | 3/5 |
| smote | quality-coverage | svm | 0.7180 | -0.0045 | 2/6 | +0.0000 | 0/0 | -0.0034 | 4/4 |
| smote | quality-coverage | xgboost | 0.6960 | -0.0021 | 2/6 | +0.0000 | 0/0 | -0.0003 | 4/4 |
| smote | random/s13 | logistic_regression | 0.6842 | +0.0000 | 0/0 | -0.0053 | 2/6 | +0.0043 | 6/2 |
| smote | random/s13 | mlp | 0.7153 | +0.0000 | 0/0 | +0.0005 | 4/4 | -0.0020 | 3/5 |
| smote | random/s13 | random_forest | 0.7205 | +0.0000 | 0/0 | -0.0037 | 4/4 | -0.0059 | 4/4 |
| smote | random/s13 | svm | 0.7334 | +0.0000 | 0/0 | +0.0045 | 6/2 | -0.0006 | 4/4 |
| smote | random/s13 | xgboost | 0.6963 | +0.0000 | 0/0 | +0.0021 | 6/2 | -0.0103 | 2/6 |
| union | boundary0.5/rho0.5+qc | logistic_regression | 0.6938 | +0.0020 | 4/4 | +0.0021 | 5/3 | +0.0036 | 5/3 |
| union | boundary0.5/rho0.5+qc | mlp | 0.7090 | -0.0027 | 4/4 | -0.0170 | 3/5 | -0.0029 | 3/5 |
| union | boundary0.5/rho0.5+qc | random_forest | 0.7304 | +0.0062 | 5/3 | +0.0014 | 4/4 | +0.0081 | 5/3 |
| union | boundary0.5/rho0.5+qc | svm | 0.7181 | +0.0004 | 4/4 | -0.0083 | 3/5 | -0.0047 | 2/6 |
| union | boundary0.5/rho0.5+qc | xgboost | 0.7093 | -0.0039 | 2/6 | -0.0008 | 3/5 | -0.0035 | 4/4 |
| union | quality-coverage | logistic_regression | 0.6850 | -0.0004 | 4/4 | +0.0000 | 0/0 | +0.0019 | 5/3 |
| union | quality-coverage | mlp | 0.7272 | -0.0036 | 2/6 | +0.0000 | 0/0 | +0.0083 | 5/3 |
| union | quality-coverage | random_forest | 0.7200 | +0.0005 | 5/3 | +0.0000 | 0/0 | +0.0081 | 6/2 |
| union | quality-coverage | svm | 0.7155 | +0.0046 | 8/0 | +0.0000 | 0/0 | -0.0002 | 4/4 |
| union | quality-coverage | xgboost | 0.7098 | -0.0046 | 3/5 | +0.0000 | 0/0 | +0.0036 | 5/3 |
| union | random/s13 | logistic_regression | 0.6848 | +0.0000 | 0/0 | +0.0004 | 4/4 | +0.0009 | 5/3 |
| union | random/s13 | mlp | 0.7088 | +0.0000 | 0/0 | +0.0036 | 6/2 | +0.0025 | 4/4 |
| union | random/s13 | random_forest | 0.7113 | +0.0000 | 0/0 | -0.0005 | 3/5 | -0.0029 | 4/4 |
| union | random/s13 | svm | 0.7138 | +0.0000 | 0/0 | -0.0046 | 0/8 | -0.0072 | 3/5 |
| union | random/s13 | xgboost | 0.7144 | +0.0000 | 0/0 | +0.0046 | 5/3 | -0.0028 | 3/5 |
| union | u2/rho0.5+qc | logistic_regression | 0.6897 | -0.0007 | 4/4 | -0.0017 | 4/4 | -0.0009 | 4/4 |
| union | u2/rho0.5+qc | mlp | 0.6915 | -0.0031 | 3/5 | -0.0088 | 4/4 | -0.0077 | 2/6 |
| union | u2/rho0.5+qc | random_forest | 0.7352 | +0.0023 | 4/4 | -0.0030 | 3/5 | -0.0054 | 4/4 |
| union | u2/rho0.5+qc | svm | 0.7034 | +0.0025 | 5/3 | -0.0021 | 3/5 | +0.0020 | 5/3 |
| union | u2/rho0.5+qc | xgboost | 0.6995 | +0.0025 | 6/2 | +0.0006 | 4/4 | -0.0024 | 3/5 |

### MCC across the five learners

| pool | design | minus random (median of 5) | learners > 0 | minus QC | learners > 0 | minus REAL | learners > 0 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| smote | boundary0.25/rho0.5+qc | -0.0001 | 2/5 | +0.0016 | 4/5 | +0.0005 | 4/5 |
| smote | quality-coverage | -0.0005 | 2/5 | +0.0000 | 0/5 | -0.0014 | 1/5 |
| smote | random/s13 | +0.0000 | 0/5 | +0.0005 | 3/5 | -0.0020 | 1/5 |
| union | boundary0.5/rho0.5+qc | +0.0004 | 3/5 | -0.0008 | 2/5 | -0.0029 | 2/5 |
| union | quality-coverage | -0.0004 | 2/5 | +0.0000 | 0/5 | +0.0036 | 4/5 |
| union | random/s13 | +0.0000 | 0/5 | +0.0004 | 3/5 | -0.0028 | 2/5 |
| union | u2/rho0.5+qc | +0.0023 | 3/5 | -0.0021 | 1/5 | -0.0024 | 1/5 |

