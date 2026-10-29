# RC-QASyn exploratory addendum v2: published-method benchmark

> **Exploratory addendum, declared after the main study.** Settings committed in `addendum/v2/addendum-v2.json` (`8173ec8`) before any score; one execution (`58efb6c`). Re-implemented curators (marked with a dagger) follow published principles; they are not the authors' code. Every row counted.

Rows: {'classifier-training': 45, 'generation-augmentation': 180, 'offline-candidate-curation': 1080, 'published-oversampler': 550, 'real-training': 90, 'reimplemented-curation': 360}; status {'ok': 1505, 'unavailable': 800}. Pools identical to recorded: True. Reproduction: {'addendum-v1': {'max_abs_metric_difference': 0.0, 'prediction_fingerprints_matching': 930, 'rows_compared': 930, 'status_all_match': True}, 'run-v2': {'max_abs_metric_difference': 0.008419924429588721, 'prediction_fingerprints_matching': 266, 'rows_compared': 465, 'status_all_match': True}}.

## Average ranks (1 = best)

**R1_curators** (8 complete datasets: Abalone19, Ecoli4, page-blocks0, yeast3, yeast4, segment0, ecoli1, abalone9-18)

| Method | LR|f1 | LR|AP | RF|f1 | RF|AP |
|---|---|---|---|---|
| schema/random | 5.12 | 4.81 | 4.81 | 5.00 |
| combined/random | 5.12 | 5.12 | 4.50 | 5.12 |
| combined/source-order | 4.38 | 5.38 | 4.00 | 4.62 |
| combined/farthest-first | 4.69 | 3.50 | 3.62 | 4.25 |
| combined/coverage-greedy | 3.81 | 5.00 | 3.88 | 5.88 |
| combined/quality-coverage | 3.75 | 4.88 | 4.06 | 4.25 |
| reimpl/cllm-style | 5.12 | 2.44 | 5.88 | 4.00 |
| reimpl/discriminator-realism | 4.00 | 4.88 | 5.25 | 2.88 |
| Friedman p | 0.654 | 0.207 | 0.525 | 0.387 |

**R2_all** (5 complete datasets: Ecoli4, yeast3, yeast4, segment0, ecoli1)

| Method | LR|f1 | LR|AP | RF|f1 | RF|AP |
|---|---|---|---|---|
| combined/quality-coverage | 6.10 | 9.40 | 7.60 | 8.60 |
| combined/random | 10.30 | 9.80 | 10.80 | 9.00 |
| combined/farthest-first | 7.30 | 7.60 | 6.60 | 6.80 |
| reimpl/cllm-style | 8.90 | 6.80 | 11.20 | 7.80 |
| reimpl/discriminator-realism | 5.70 | 7.60 | 9.80 | 4.40 |
| REAL_TRAIN | 7.30 | 7.40 | 12.50 | 9.00 |
| RandomOverSampler+b | 9.80 | 9.20 | 10.00 | 8.60 |
| SMOTE(NC)+b | 8.30 | 7.00 | 10.70 | 10.20 |
| SMOTE-ENN/full | 8.50 | 13.20 | 7.20 | 10.40 |
| SMOTE-ENN/+b | 9.70 | 7.60 | 13.00 | 12.00 |
| SMOTE-Tomek/full | 7.20 | 10.20 | 3.70 | 7.80 |
| SMOTE-Tomek/+b | 8.10 | 5.40 | 9.80 | 7.00 |
| Borderline-SMOTE/full | 10.00 | 9.00 | 6.00 | 7.60 |
| Borderline-SMOTE/+b | 10.20 | 5.60 | 6.50 | 8.80 |
| ADASYN/full | 10.80 | 9.90 | 4.50 | 8.20 |
| ADASYN/+b | 7.80 | 10.30 | 6.10 | 9.80 |
| Friedman p | 0.904 | 0.578 | 0.031 | 0.826 |

## Wilcoxon: quality-coverage minus method (datasets QC better / worse, median diff, p)

| Method | LR F1 | LR AP | RF F1 | RF AP |
|---|---|---|---|---|
| schema/random | 4/1, +0.001, p=0.12 | 4/4, +0.000, p=0.64 | 4/2, +0.000, p=0.31 | 5/3, +0.000, p=0.95 |
| combined/random | 4/1, +0.001, p=0.19 | 3/4, -0.001, p=0.58 | 6/2, +0.013, p=0.31 | 5/3, +0.002, p=1.00 |
| combined/source-order | 4/1, +0.000, p=0.44 | 4/3, +0.000, p=0.81 | 3/4, -0.003, p=0.58 | 4/4, +0.001, p=0.84 |
| combined/farthest-first | 4/1, +0.000, p=0.62 | 3/4, -0.001, p=0.22 | 3/3, +0.000, p=0.84 | 5/3, +0.000, p=0.74 |
| combined/coverage-greedy | 1/2, +0.000, p=1.00 | 3/4, -0.000, p=0.58 | 2/4, -0.001, p=1.00 | 5/3, +0.000, p=0.95 |
| reimpl/cllm-style | 4/2, +0.001, p=1.00 | 2/6, -0.006, p=0.08 | 5/2, +0.004, p=0.38 | 3/5, -0.002, p=0.84 |
| reimpl/discriminator-realism | 2/3, +0.000, p=0.81 | 4/4, -0.001, p=0.46 | 4/3, +0.000, p=0.94 | 3/5, -0.004, p=0.38 |
| REAL_TRAIN | 5/1, +0.006, p=0.44 | 3/5, -0.000, p=0.46 | 5/2, +0.027, p=0.08 | 5/3, +0.003, p=0.46 |
| CLASS_WEIGHTED_LR | 6/2, +0.027, p=0.31 | 3/5, -0.001, p=0.74 | n/a | n/a |
| RandomOverSampler+b | 5/1, +0.007, p=0.06 | 6/2, +0.001, p=0.38 | 5/1, +0.007, p=0.16 | 5/3, +0.007, p=0.38 |
| SMOTE(NC)+b | 5/0, +0.003, p=0.06 | 3/5, -0.000, p=0.64 | 4/2, +0.007, p=0.56 | 6/2, +0.004, p=0.31 |
| SMOTE-ENN/full | 4/2, +0.027, p=0.44 | 5/1, +0.017, p=0.09 | 3/3, -0.016, p=0.69 | 4/2, +0.010, p=0.31 |
| SMOTE-ENN/+b | 3/1, +0.001, p=0.62 | 3/3, +0.001, p=1.00 | 5/1, +0.019, p=0.16 | 5/1, +0.024, p=0.31 |
| SMOTE-Tomek/full | 4/2, +0.011, p=0.44 | 4/2, +0.006, p=0.31 | 2/4, -0.008, p=0.31 | 3/3, +0.001, p=0.84 |
| SMOTE-Tomek/+b | 2/2, +0.000, p=1.00 | 2/4, -0.004, p=0.16 | 2/3, -0.001, p=0.81 | 4/2, +0.002, p=0.56 |
| Borderline-SMOTE/full | 4/2, +0.057, p=0.44 | 3/3, +0.004, p=0.56 | 3/3, +0.004, p=1.00 | 3/3, +0.007, p=0.69 |
| Borderline-SMOTE/+b | 4/2, +0.001, p=0.56 | 2/4, -0.003, p=0.44 | 2/4, -0.004, p=1.00 | 3/3, +0.000, p=0.69 |
| ADASYN/full | 5/1, +0.060, p=0.16 | 4/2, +0.019, p=0.22 | 2/4, -0.008, p=0.56 | 3/3, +0.008, p=0.69 |
| ADASYN/+b | 3/2, +0.006, p=0.81 | 3/2, +0.000, p=1.00 | 2/3, -0.003, p=1.00 | 3/2, +0.011, p=0.62 |

## Literature sanity check (context only; Newaz & Haq Table 7, RF, 10-fold CV)

| Dataset | Theirs unsampled / SMOTE | Ours RF real / SMOTE(NC)+b | Ours LR real / SMOTE(NC)+b | sign agrees RF, LR |
|---|---|---|---|---|
| yeast3 | 83.8 / 90.0 | 96.8 / 97.5 | 96.8 / 96.8 | True, False |
| page-blocks0 | 90.8 / 92.7 | 98.7 / 98.7 | 94.6 / 94.6 | False, True |
| Ecoli4 | 85.0 / 89.3 | 97.5 / 96.8 | 99.4 / 99.4 | False, False |
| abalone9-18 | 57.1 / 71.8 | 87.2 / 89.8 | 95.3 / 96.2 | True, True |
| yeast4 | 56.8 / 72.0 | 91.0 / 89.8 | 85.3 / 85.4 | False, True |
| Abalone19 | 50.0 / 50.0 | 71.9 / 70.5 | 84.7 / 81.1 | False, False |

## Unavailable (every occurrence counted)

- Abalone19 / ADASYN/+b: NO_NOMINAL_PATH_IN_IMBALANCED_LEARN (x5)
- Abalone19 / ADASYN/full: NO_NOMINAL_PATH_IN_IMBALANCED_LEARN (x5)
- Abalone19 / Borderline-SMOTE/+b: NO_NOMINAL_PATH_IN_IMBALANCED_LEARN (x5)
- Abalone19 / Borderline-SMOTE/full: NO_NOMINAL_PATH_IN_IMBALANCED_LEARN (x5)
- Abalone19 / SMOTE: INCOMPATIBLE_DECLARED_FEATURE_TYPES; use declared counterpart (x5)
- Abalone19 / SMOTE-ENN/+b: LIBRARY_ERROR ValueError: could not convert string to float: 'M' (x5)
- Abalone19 / SMOTE-ENN/full: LIBRARY_ERROR ValueError: could not convert string to float: 'M' (x5)
- Abalone19 / SMOTE-Tomek/+b: LIBRARY_ERROR ValueError: could not convert string to float: 'M' (x5)
- Abalone19 / SMOTE-Tomek/full: LIBRARY_ERROR ValueError: could not convert string to float: 'M' (x5)
- Ecoli4 / SMOTENC: INCOMPATIBLE_DECLARED_FEATURE_TYPES; use declared counterpart (x5)
- abalone9-18 / ADASYN/+b: NO_NOMINAL_PATH_IN_IMBALANCED_LEARN (x5)
- abalone9-18 / ADASYN/full: NO_NOMINAL_PATH_IN_IMBALANCED_LEARN (x5)
- abalone9-18 / Borderline-SMOTE/+b: NO_NOMINAL_PATH_IN_IMBALANCED_LEARN (x5)
- abalone9-18 / Borderline-SMOTE/full: NO_NOMINAL_PATH_IN_IMBALANCED_LEARN (x5)
- abalone9-18 / SMOTE: INCOMPATIBLE_DECLARED_FEATURE_TYPES; use declared counterpart (x5)
- abalone9-18 / SMOTE-ENN/+b: LIBRARY_ERROR ValueError: could not convert string to float: 'F' (x5)
- abalone9-18 / SMOTE-ENN/full: LIBRARY_ERROR ValueError: could not convert string to float: 'F' (x5)
- abalone9-18 / SMOTE-Tomek/+b: LIBRARY_ERROR ValueError: could not convert string to float: 'F' (x5)
- abalone9-18 / SMOTE-Tomek/full: LIBRARY_ERROR ValueError: could not convert string to float: 'F' (x5)
- ecoli1 / SMOTENC: INCOMPATIBLE_DECLARED_FEATURE_TYPES; use declared counterpart (x5)
- page-blocks0 / ADASYN/+b: LIBRARY_ERROR ValueError: No samples will be generated with the provided ratio settings. (x5)
- page-blocks0 / SMOTENC: INCOMPATIBLE_DECLARED_FEATURE_TYPES; use declared counterpart (x5)
- segment0 / SMOTENC: INCOMPATIBLE_DECLARED_FEATURE_TYPES; use declared counterpart (x5)
- vehicle0 / SMOTENC: INCOMPATIBLE_DECLARED_FEATURE_TYPES; use declared counterpart (x5)
- winequality-red-4 / all: SOURCE_ARCHIVE_EMPTY (addendum v1) (x1)
- yeast3 / SMOTENC: INCOMPATIBLE_DECLARED_FEATURE_TYPES; use declared counterpart (x5)
- yeast4 / SMOTENC: INCOMPATIBLE_DECLARED_FEATURE_TYPES; use declared counterpart (x5)

## Conclusion

**Quality-coverage did not beat the published methods.** None of its exploratory Wilcoxon comparisons against the four published oversamplers, the re-implemented CLLM-style and discriminator-realism curators, or the existing selectors reached even nominal p < 0.05 (smallest p = 0.06), and its dataset-level differences were small and mixed in sign. Among the eight curators it had the best average rank only for logistic-regression F1 (3.75 of 8), and the Friedman tests found no consistent separation among curators (p = 0.21 to 0.65). Across all sixteen methods on the five datasets where every method ran, full-balancing SMOTE-Tomek and ADASYN ranked best for random-forest F1 (average ranks 3.7 and 4.5 against 7.6 for quality-coverage; Friedman p = 0.03, exploratory), mainly through large gains on yeast4 and ecoli1, while the same full-balancing oversamplers often lowered logistic-regression F1 (for example 0.63 to 0.68 against 0.78 on yeast3). Several published methods could not run everywhere: Borderline-SMOTE and ADASYN have no nominal-feature path, SMOTE-ENN and SMOTE-Tomek failed on nominal columns, ADASYN +b generated no samples on page-blocks0, and no curator could run on vehicle0. Our AUROC values are much higher than those in Newaz and Haq and the sign of the SMOTE effect matched theirs in only 5 of 12 dataset-classifier pairs, which is consistent with their different protocol (10-fold cross-validation, and an unsampled Abalone19 AUC of exactly 50.0 that suggests hard-label scoring), so this check is context rather than validation.
