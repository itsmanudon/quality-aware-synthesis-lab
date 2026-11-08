# Phase 4: TEST results under the frozen protocol (a65e20f96d09)

Amendment applied: study-v3-amendment-1 (951c656983a1).

Amendment applied: study-v3-amendment-2 (f41ee997478e).

- oml41162 excluded from every test: U2_SIDE_COMPUTE_LIMIT.
- oml1597: stage eval-rest incomplete, its methods unavailable: EVALUATION_COMPUTE_LIMIT.

Units: 195; datasets: 39; cells: 19761; unavailable cells listed: 1009.

## Success family (F1; Wilcoxon two-sided, Holm over 2)

| merged vs | datasets | median diff | 95% CI | above/below/ties | p | p Holm |
| --- | --- | --- | --- | --- | --- | --- |
| no-oversampling | 38 | -0.0005 | [-0.0025, -0.0002] | 12/26/0 | 0.04137 | 0.0506 |
| u2 | 38 | -0.0007 | [-0.0047, +0.0002] | 15/23/0 | 0.0253 | 0.0506 |

MCC no-loss check (same family):

| merged vs | median MCC diff | p Holm | loss |
| --- | --- | --- | --- |
| no-oversampling | -0.0004 | 0.1992 | False |
| u2 | -0.0015 | 0.01913 | True |

**Success criterion met: False**

## Comparator family (F1; Wilcoxon two-sided, Holm over the family)

| merged vs | datasets | median diff | 95% CI | above/below/ties | p | p Holm |
| --- | --- | --- | --- | --- | --- | --- |
| adasyn | 12 | +0.0003 | [-0.0010, +0.0039] | 7/5/0 | 0.4697 | 1 |
| b2-equal-budget | 37 | +0.0005 | [-0.0007, +0.0032] | 21/16/0 | 0.3017 | 1 |
| borderline-smote | 22 | +0.0004 | [-0.0012, +0.0018] | 14/8/0 | 1 | 1 |
| class-weighted | 37 | +0.0003 | [-0.0062, +0.0016] | 20/17/0 | 0.3088 | 1 |
| cllm-style | 34 | -0.0006 | [-0.0040, +0.0004] | 15/19/0 | 0.2025 | 1 |
| discriminator-realism | 37 | -0.0005 | [-0.0052, +0.0000] | 14/23/0 | 0.06525 | 1 |
| kmeans_smote | 37 | +0.0005 | [-0.0005, +0.0019] | 21/16/0 | 0.5112 | 1 |
| merged[llm:claude-haiku-5-5] | 36 | +0.0002 | [-0.0006, +0.0011] | 22/14/0 | 0.6694 | 1 |
| merged[llm:claude-haiku-5-5][unrounded] | 6 | -0.0016 | [-0.0099, +0.0058] | 2/4/0 | 0.4375 | 1 |
| merged[llm:gpt-6-luna] | 37 | +0.0001 | [-0.0028, +0.0010] | 19/17/1 | 0.4414 | 1 |
| merged[llm:gpt-6-luna][unrounded] | 7 | +0.0005 | [-0.0032, +0.0048] | 4/3/0 | 0.8125 | 1 |
| merged[llm:muse-spark-1.3] | 37 | -0.0004 | [-0.0015, +0.0013] | 17/20/0 | 0.4284 | 1 |
| merged[llm:muse-spark-1.3][unrounded] | 8 | +0.0037 | [-0.0000, +0.0083] | 6/2/0 | 0.05469 | 1 |
| merged[no-llm] | 37 | +0.0003 | [-0.0015, +0.0012] | 21/16/0 | 0.9406 | 1 |
| merged[unrounded] | 9 | +0.0038 | [-0.0008, +0.0092] | 6/3/0 | 0.3008 | 1 |
| original_ugo | 37 | +0.0002 | [-0.0021, +0.0015] | 21/16/0 | 0.9287 | 1 |
| quality-coverage | 37 | +0.0001 | [-0.0011, +0.0010] | 19/18/0 | 0.8698 | 1 |
| random | 37 | +0.0005 | [-0.0005, +0.0016] | 21/16/0 | 0.4461 | 1 |
| ros | 37 | -0.0005 | [-0.0034, +0.0006] | 16/21/0 | 0.1534 | 1 |
| rwo | 37 | -0.0002 | [-0.0029, +0.0009] | 18/19/0 | 0.7429 | 1 |
| schema-random | 37 | +0.0005 | [-0.0016, +0.0040] | 22/15/0 | 0.7093 | 1 |
| smote | 37 | -0.0002 | [-0.0016, +0.0014] | 18/19/0 | 0.7093 | 1 |
| smote-tomek | 33 | -0.0002 | [-0.0025, +0.0014] | 16/17/0 | 0.6464 | 1 |

## Friedman over the main methods (F1; 37 complete datasets)

statistic 7.750724637681144, p 0.3550872172752867

| method | average rank (1 = best) |
| --- | --- |
| u2 | 3.92 |
| no-oversampling | 4.15 |
| merged | 4.23 |
| class-weighted | 4.27 |
| quality-coverage | 4.58 |
| smote | 4.82 |
| original_ugo | 4.89 |
| random | 5.14 |

## Unavailable cells (method, reason: count)

- *: U2_SIDE_COMPUTE_LIMIT: 1
- adasyn: FEWER_THAN_3_OF_5_SPLITS: 15
- adasyn: MATCHED_BUDGET_SHORTFALL: 40
- adasyn: Unavailable:: 80
- adasyn: ValueError:: 18
- b2-equal-budget: EVALUATION_COMPUTE_LIMIT: 4
- b2-equal-budget: SVM_SIZE_LIMIT: 16
- borderline-smote: EVALUATION_COMPUTE_LIMIT: 4
- borderline-smote: MATCHED_BUDGET_SHORTFALL: 1
- borderline-smote: SVM_SIZE_LIMIT: 6
- borderline-smote: Unavailable:: 80
- class-weighted: EVALUATION_COMPUTE_LIMIT: 3
- class-weighted: NO_CLASS_WEIGHT_IN_U2_MLP: 191
- class-weighted: SVM_SIZE_LIMIT: 16
- cllm-style: EVALUATION_COMPUTE_LIMIT: 4
- cllm-style: GATE_NO_COMPLETE_TRAIN_ROW: 5
- cllm-style: SVM_SIZE_LIMIT: 11
- cllm-style: ValueError:: 15
- discriminator-realism: EVALUATION_COMPUTE_LIMIT: 4
- discriminator-realism: GATE_NO_COMPLETE_TRAIN_ROW: 5
- discriminator-realism: SVM_SIZE_LIMIT: 16
- kmeans_smote: EVALUATION_COMPUTE_LIMIT: 4
- kmeans_smote: SVM_SIZE_LIMIT: 16
- merged: GATE_NO_COMPLETE_TRAIN_ROW: 5
- merged: SVM_SIZE_LIMIT: 20
- merged[llm:claude-haiku-5-5]: EVALUATION_COMPUTE_LIMIT: 4
- merged[llm:claude-haiku-5-5]: GATE_NO_COMPLETE_TRAIN_ROW: 5
- merged[llm:claude-haiku-5-5]: SVM_SIZE_LIMIT: 11
- merged[llm:claude-haiku-5-5][unrounded]: FEWER_THAN_3_OF_5_SPLITS: 5
- merged[llm:claude-haiku-5-5][unrounded]: MATCHED_BUDGET_SHORTFALL: 9
- merged[llm:gpt-6-luna]: EVALUATION_COMPUTE_LIMIT: 4
- merged[llm:gpt-6-luna]: GATE_NO_COMPLETE_TRAIN_ROW: 5
- merged[llm:gpt-6-luna]: SVM_SIZE_LIMIT: 16
- merged[llm:gpt-6-luna][unrounded]: FEWER_THAN_3_OF_5_SPLITS: 10
- merged[llm:gpt-6-luna][unrounded]: MATCHED_BUDGET_SHORTFALL: 6
- merged[llm:gpt-6-luna][unrounded]: SVM_SIZE_LIMIT: 5
- merged[llm:muse-spark-1.3]: EVALUATION_COMPUTE_LIMIT: 4
- merged[llm:muse-spark-1.3]: GATE_NO_COMPLETE_TRAIN_ROW: 5
- merged[llm:muse-spark-1.3]: SVM_SIZE_LIMIT: 16
- merged[llm:muse-spark-1.3][unrounded]: FEWER_THAN_3_OF_5_SPLITS: 5
- merged[llm:muse-spark-1.3][unrounded]: MATCHED_BUDGET_SHORTFALL: 4
- merged[llm:muse-spark-1.3][unrounded]: SVM_SIZE_LIMIT: 5
- merged[no-llm]: EVALUATION_COMPUTE_LIMIT: 4
- merged[no-llm]: GATE_NO_COMPLETE_TRAIN_ROW: 5
- merged[no-llm]: SVM_SIZE_LIMIT: 16
- merged[no-llm][unrounded]: MATCHED_BUDGET_SHORTFALL: 45
- merged[unrounded]: SVM_SIZE_LIMIT: 5
- no-oversampling: SVM_SIZE_LIMIT: 20
- original_ugo: EVALUATION_COMPUTE_LIMIT: 4
- original_ugo: SVM_SIZE_LIMIT: 16
- pool:llm:claude-haiku-5-5: NO_LLM_POOL: 5
- quality-coverage: EVALUATION_COMPUTE_LIMIT: 4
- quality-coverage: GATE_NO_COMPLETE_TRAIN_ROW: 5
- quality-coverage: SVM_SIZE_LIMIT: 16
- random: EVALUATION_COMPUTE_LIMIT: 4
- random: GATE_NO_COMPLETE_TRAIN_ROW: 5
- random: SVM_SIZE_LIMIT: 16
- ros: EVALUATION_COMPUTE_LIMIT: 4
- ros: SVM_SIZE_LIMIT: 16
- rwo: EVALUATION_COMPUTE_LIMIT: 4
- rwo: SVM_SIZE_LIMIT: 16
- schema-random: EVALUATION_COMPUTE_LIMIT: 4
- schema-random: GATE_NO_COMPLETE_TRAIN_ROW: 5
- schema-random: SVM_SIZE_LIMIT: 16
- smote: EVALUATION_COMPUTE_LIMIT: 4
- smote: SVM_SIZE_LIMIT: 16
- smote-tomek: EVALUATION_COMPUTE_LIMIT: 4
- smote-tomek: SVM_SIZE_LIMIT: 6
- smote-tomek: Unavailable:: 25
- u2: SVM_SIZE_LIMIT: 20

## Per-dataset F1 differences, success family (descriptive)

| dataset | merged - no-oversampling | merged - u2 |
| --- | --- | --- |
| oml1016 | +0.0106 | +0.0039 |
| oml1019 | -0.0004 | -0.0004 |
| oml1020 | +0.0017 | +0.0010 |
| oml1021 | -0.0020 | -0.0079 |
| oml1049 | +0.0065 | +0.0030 |
| oml1050 | -0.0081 | -0.0122 |
| oml1053 | +0.0039 | -0.0049 |
| oml1067 | +0.0004 | +0.0042 |
| oml1068 | -0.0114 | -0.0224 |
| oml1464 | -0.0106 | -0.0013 |
| oml1487 | -0.0022 | -0.0073 |
| oml1506 | -0.0136 | +0.0109 |
| oml1558 | -0.0006 | -0.0040 |
| oml1590 | -0.0003 | -0.0003 |
| oml1597 | +0.0007 | -0.0009 |
| oml310 | +0.0060 | -0.0003 |
| oml40713 | +0.0056 | -0.0112 |
| oml40900 | -0.0004 | -0.0191 |
| oml40983 | +0.0068 | +0.0050 |
| oml41946 | -0.0027 | +0.0003 |
| oml42477 | -0.0005 | +0.0004 |
| oml43 | -0.0064 | -0.0053 |
| oml43893 | -0.0083 | -0.0269 |
| oml44232 | -0.0017 | -0.0054 |
| oml45558 | +0.0011 | +0.0006 |
| oml45560 | -0.0002 | +0.0012 |
| oml45562 | -0.0098 | -0.0035 |
| oml46281 | -0.0070 | +0.0132 |
| oml46911 | -0.0014 | -0.0006 |
| oml46929 | +0.0009 | +0.0002 |
| oml46938 | -0.0054 | -0.0045 |
| oml46940 | -0.0125 | -0.0127 |
| oml949 | -0.0305 | -0.0187 |
| oml971 | +0.0011 | +0.0000 |
| oml976 | -0.0002 | +0.0008 |
| oml977 | -0.0036 | -0.0034 |
| oml980 | -0.0005 | +0.0010 |
| oml995 | -0.0004 | -0.0075 |
