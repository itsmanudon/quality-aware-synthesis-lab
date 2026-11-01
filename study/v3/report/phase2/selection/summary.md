# Phase 2: utility-aware selection on dev data (5-fold cross-fit inside TRAIN)

Pooled over the 5 held-out folds of each outer TRAIN; F1 at the cross-fitted threshold (each fold's threshold chosen on the other 4 folds, U2's rule). Differences are paired per dataset x split x classifier, averaged over the 5 split seeds, then the median over datasets (with counts above / below zero). `random` = mean of 5 random selections from the same admitted pool. Descriptive only; dev data; TEST never used.

## Pool `smote`: F1 (cross-fitted threshold)

| design | classifier | median F1 | minus random | +/- | minus QC | minus REAL | +/- | datasets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| boundary0.25/rho0.25+qc | logistic_regression | 0.7282 | -0.0002 | 3/4 | -0.0008 | +0.0004 | 4/3 | 7 |
| boundary0.25/rho0.5+qc | logistic_regression | 0.7437 | +0.0030 | 6/1 | -0.0000 | +0.0021 | 6/1 | 7 |
| boundary0.25/top | logistic_regression | 0.7282 | -0.0001 | 3/4 | -0.0008 | +0.0004 | 4/3 | 7 |
| boundary0.5/rho0.25+qc | logistic_regression | 0.7380 | -0.0032 | 2/5 | -0.0005 | +0.0014 | 4/3 | 7 |
| boundary0.5/rho0.5+qc | logistic_regression | 0.7384 | +0.0040 | 6/1 | +0.0062 | +0.0021 | 5/2 | 7 |
| boundary0.5/top | logistic_regression | 0.7380 | -0.0032 | 2/5 | -0.0004 | +0.0015 | 4/3 | 7 |
| boundary0.75/rho0.25+qc | logistic_regression | 0.7224 | -0.0039 | 1/6 | -0.0040 | -0.0027 | 3/4 | 7 |
| boundary0.75/rho0.5+qc | logistic_regression | 0.7394 | -0.0031 | 3/4 | +0.0051 | +0.0010 | 4/3 | 7 |
| boundary0.75/top | logistic_regression | 0.7224 | -0.0039 | 1/6 | -0.0040 | -0.0027 | 3/4 | 7 |
| boundary0/rho0.25+qc | logistic_regression | 0.7365 | -0.0051 | 2/5 | -0.0010 | +0.0009 | 4/3 | 7 |
| boundary0/rho0.5+qc | logistic_regression | 0.7309 | +0.0040 | 4/3 | -0.0004 | +0.0021 | 5/2 | 7 |
| boundary0/top | logistic_regression | 0.7368 | -0.0051 | 2/5 | -0.0008 | +0.0011 | 4/3 | 7 |
| quality-coverage | logistic_regression | 0.7345 | +0.0001 | 4/3 | +0.0000 | +0.0012 | 4/3 | 7 |
| random(mean of 5) | logistic_regression | 0.7432 | +0.0000 | 0/0 | -0.0001 | +0.0017 | 5/2 | 7 |
| u2/rho0.25+qc | logistic_regression | 0.7327 | -0.0008 | 3/4 | -0.0011 | +0.0002 | 4/3 | 7 |
| u2/rho0.5+qc | logistic_regression | 0.7426 | +0.0003 | 4/3 | +0.0000 | +0.0019 | 5/2 | 7 |
| u2/top | logistic_regression | 0.7327 | -0.0008 | 3/4 | -0.0011 | +0.0002 | 4/3 | 7 |
| boundary0.25/rho0.25+qc | random_forest | 0.7721 | +0.0117 | 5/2 | +0.0157 | +0.0077 | 4/3 | 7 |
| boundary0.25/rho0.5+qc | random_forest | 0.7665 | +0.0084 | 6/1 | +0.0034 | +0.0042 | 4/3 | 7 |
| boundary0.25/top | random_forest | 0.7714 | +0.0070 | 5/2 | +0.0068 | +0.0068 | 5/2 | 7 |
| boundary0.5/rho0.25+qc | random_forest | 0.7723 | +0.0041 | 4/3 | +0.0101 | +0.0001 | 4/3 | 7 |
| boundary0.5/rho0.5+qc | random_forest | 0.7719 | +0.0003 | 4/3 | +0.0008 | -0.0019 | 2/5 | 7 |
| boundary0.5/top | random_forest | 0.7635 | +0.0054 | 5/2 | +0.0133 | +0.0068 | 4/3 | 7 |
| boundary0.75/rho0.25+qc | random_forest | 0.7667 | -0.0032 | 1/6 | +0.0000 | -0.0019 | 3/4 | 7 |
| boundary0.75/rho0.5+qc | random_forest | 0.7613 | -0.0031 | 2/5 | -0.0033 | -0.0019 | 3/4 | 7 |
| boundary0.75/top | random_forest | 0.7685 | +0.0003 | 4/3 | -0.0011 | -0.0037 | 3/4 | 7 |
| boundary0/rho0.25+qc | random_forest | 0.7546 | -0.0047 | 2/5 | +0.0010 | -0.0032 | 2/5 | 7 |
| boundary0/rho0.5+qc | random_forest | 0.7316 | -0.0014 | 3/4 | +0.0023 | -0.0054 | 2/5 | 7 |
| boundary0/top | random_forest | 0.7557 | -0.0079 | 2/5 | -0.0038 | +0.0064 | 4/3 | 7 |
| quality-coverage | random_forest | 0.7623 | +0.0002 | 4/3 | +0.0000 | -0.0027 | 2/5 | 7 |
| random(mean of 5) | random_forest | 0.7644 | +0.0000 | 0/0 | -0.0002 | -0.0022 | 3/4 | 7 |
| u2/rho0.25+qc | random_forest | 0.7657 | -0.0013 | 2/5 | -0.0032 | -0.0029 | 3/4 | 7 |
| u2/rho0.5+qc | random_forest | 0.7661 | +0.0018 | 4/3 | +0.0015 | +0.0035 | 4/3 | 7 |
| u2/top | random_forest | 0.7602 | +0.0022 | 4/3 | +0.0027 | +0.0006 | 4/3 | 7 |

## Pool `smote+round`: F1 (cross-fitted threshold)

| design | classifier | median F1 | minus random | +/- | minus QC | minus REAL | +/- | datasets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| boundary0.25/rho0.5+qc | logistic_regression | 0.9287 | +0.0047 | 1/0 | +0.0045 | +0.0077 | 1/0 | 1 |
| boundary0.25/top | logistic_regression | 0.9182 | -0.0058 | 0/1 | -0.0060 | -0.0028 | 0/1 | 1 |
| boundary0.5/rho0.5+qc | logistic_regression | 0.9257 | +0.0016 | 1/0 | +0.0015 | +0.0046 | 1/0 | 1 |
| boundary0.5/top | logistic_regression | 0.9243 | +0.0002 | 1/0 | +0.0001 | +0.0032 | 1/0 | 1 |
| boundary0.75/rho0.5+qc | logistic_regression | 0.9264 | +0.0024 | 1/0 | +0.0022 | +0.0054 | 1/0 | 1 |
| boundary0.75/top | logistic_regression | 0.9254 | +0.0014 | 1/0 | +0.0012 | +0.0043 | 1/0 | 1 |
| boundary0/rho0.5+qc | logistic_regression | 0.9207 | -0.0033 | 0/1 | -0.0035 | -0.0004 | 0/1 | 1 |
| boundary0/top | logistic_regression | 0.9218 | -0.0023 | 0/1 | -0.0024 | +0.0007 | 1/0 | 1 |
| quality-coverage | logistic_regression | 0.9242 | +0.0002 | 1/0 | +0.0000 | +0.0031 | 1/0 | 1 |
| random(mean of 5) | logistic_regression | 0.9240 | +0.0000 | 0/0 | -0.0002 | +0.0030 | 1/0 | 1 |
| u2/rho0.5+qc | logistic_regression | 0.9212 | -0.0028 | 0/1 | -0.0030 | +0.0001 | 1/0 | 1 |
| u2/top | logistic_regression | 0.9272 | +0.0032 | 1/0 | +0.0030 | +0.0061 | 1/0 | 1 |
| boundary0.25/rho0.5+qc | random_forest | 0.9175 | +0.0024 | 1/0 | +0.0008 | +0.0029 | 1/0 | 1 |
| boundary0.25/top | random_forest | 0.9212 | +0.0061 | 1/0 | +0.0045 | +0.0066 | 1/0 | 1 |
| boundary0.5/rho0.5+qc | random_forest | 0.9050 | -0.0101 | 0/1 | -0.0117 | -0.0095 | 0/1 | 1 |
| boundary0.5/top | random_forest | 0.9196 | +0.0045 | 1/0 | +0.0030 | +0.0051 | 1/0 | 1 |
| boundary0.75/rho0.5+qc | random_forest | 0.9016 | -0.0135 | 0/1 | -0.0151 | -0.0129 | 0/1 | 1 |
| boundary0.75/top | random_forest | 0.9185 | +0.0034 | 1/0 | +0.0018 | +0.0039 | 1/0 | 1 |
| boundary0/rho0.5+qc | random_forest | 0.9190 | +0.0039 | 1/0 | +0.0023 | +0.0045 | 1/0 | 1 |
| boundary0/top | random_forest | 0.9123 | -0.0028 | 0/1 | -0.0044 | -0.0023 | 0/1 | 1 |
| quality-coverage | random_forest | 0.9167 | +0.0016 | 1/0 | +0.0000 | +0.0022 | 1/0 | 1 |
| random(mean of 5) | random_forest | 0.9151 | +0.0000 | 0/0 | -0.0016 | +0.0006 | 1/0 | 1 |
| u2/rho0.5+qc | random_forest | 0.9137 | -0.0014 | 0/1 | -0.0030 | -0.0009 | 0/1 | 1 |
| u2/top | random_forest | 0.9192 | +0.0041 | 1/0 | +0.0025 | +0.0047 | 1/0 | 1 |

## Pool `union`: F1 (cross-fitted threshold)

| design | classifier | median F1 | minus random | +/- | minus QC | minus REAL | +/- | datasets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| boundary0.25/rho0.25+qc | logistic_regression | 0.7342 | -0.0012 | 3/4 | -0.0062 | +0.0019 | 5/2 | 7 |
| boundary0.25/rho0.5+qc | logistic_regression | 0.7377 | -0.0001 | 3/4 | -0.0012 | +0.0015 | 4/3 | 7 |
| boundary0.25/top | logistic_regression | 0.7395 | +0.0036 | 5/2 | -0.0022 | +0.0036 | 6/1 | 7 |
| boundary0.5/rho0.25+qc | logistic_regression | 0.7312 | -0.0004 | 3/4 | -0.0058 | +0.0007 | 4/3 | 7 |
| boundary0.5/rho0.5+qc | logistic_regression | 0.7455 | +0.0077 | 5/2 | +0.0045 | +0.0035 | 5/2 | 7 |
| boundary0.5/top | logistic_regression | 0.7356 | -0.0019 | 2/5 | -0.0044 | +0.0002 | 4/3 | 7 |
| boundary0.75/rho0.25+qc | logistic_regression | 0.7238 | -0.0004 | 3/4 | -0.0067 | +0.0027 | 5/2 | 7 |
| boundary0.75/rho0.5+qc | logistic_regression | 0.7449 | -0.0004 | 3/4 | -0.0004 | +0.0023 | 5/2 | 7 |
| boundary0.75/top | logistic_regression | 0.7135 | -0.0036 | 2/5 | -0.0025 | -0.0036 | 3/4 | 7 |
| boundary0/rho0.25+qc | logistic_regression | 0.7267 | -0.0022 | 2/5 | -0.0062 | +0.0007 | 4/3 | 7 |
| boundary0/rho0.5+qc | logistic_regression | 0.7394 | +0.0016 | 5/2 | -0.0012 | +0.0036 | 5/2 | 7 |
| boundary0/top | logistic_regression | 0.7390 | +0.0001 | 5/2 | -0.0027 | +0.0031 | 6/1 | 7 |
| quality-coverage | logistic_regression | 0.7417 | +0.0039 | 4/3 | +0.0000 | +0.0058 | 5/2 | 7 |
| random(mean of 5) | logistic_regression | 0.7378 | +0.0000 | 0/0 | -0.0039 | +0.0021 | 5/2 | 7 |
| u2/rho0.25+qc | logistic_regression | 0.6072 | -0.0069 | 2/4 | -0.0105 | -0.0058 | 2/4 | 6 |
| u2/rho0.5+qc | logistic_regression | 0.7441 | -0.0015 | 2/5 | -0.0063 | +0.0008 | 5/2 | 7 |
| u2/top | logistic_regression | 0.7167 | -0.0069 | 1/6 | -0.0168 | -0.0059 | 3/4 | 7 |
| boundary0.25/rho0.25+qc | random_forest | 0.7683 | +0.0015 | 5/2 | +0.0151 | +0.0032 | 5/2 | 7 |
| boundary0.25/rho0.5+qc | random_forest | 0.7588 | +0.0047 | 4/3 | +0.0163 | +0.0138 | 5/2 | 7 |
| boundary0.25/top | random_forest | 0.7711 | +0.0031 | 5/2 | +0.0048 | +0.0045 | 4/3 | 7 |
| boundary0.5/rho0.25+qc | random_forest | 0.7757 | +0.0049 | 4/3 | +0.0088 | +0.0032 | 4/2 | 7 |
| boundary0.5/rho0.5+qc | random_forest | 0.7652 | +0.0032 | 5/2 | +0.0163 | +0.0162 | 5/2 | 7 |
| boundary0.5/top | random_forest | 0.7797 | +0.0027 | 4/3 | +0.0016 | -0.0025 | 3/4 | 7 |
| boundary0.75/rho0.25+qc | random_forest | 0.7626 | -0.0062 | 1/6 | +0.0005 | -0.0035 | 2/5 | 7 |
| boundary0.75/rho0.5+qc | random_forest | 0.7590 | -0.0084 | 3/4 | +0.0005 | -0.0023 | 3/4 | 7 |
| boundary0.75/top | random_forest | 0.7351 | -0.0018 | 2/5 | -0.0038 | -0.0058 | 2/5 | 7 |
| boundary0/rho0.25+qc | random_forest | 0.7571 | +0.0008 | 4/3 | +0.0032 | +0.0032 | 4/3 | 7 |
| boundary0/rho0.5+qc | random_forest | 0.7699 | +0.0047 | 5/2 | +0.0163 | +0.0046 | 5/2 | 7 |
| boundary0/top | random_forest | 0.7630 | -0.0035 | 2/5 | +0.0016 | -0.0025 | 3/4 | 7 |
| quality-coverage | random_forest | 0.7585 | -0.0017 | 3/4 | +0.0000 | -0.0031 | 2/5 | 7 |
| random(mean of 5) | random_forest | 0.7680 | +0.0000 | 0/0 | +0.0017 | -0.0001 | 3/4 | 7 |
| u2/rho0.25+qc | random_forest | 0.5686 | -0.0039 | 2/4 | +0.0019 | -0.0080 | 1/5 | 6 |
| u2/rho0.5+qc | random_forest | 0.7562 | -0.0051 | 2/5 | -0.0023 | -0.0031 | 3/4 | 7 |
| u2/top | random_forest | 0.7491 | -0.0167 | 1/6 | -0.0031 | -0.0038 | 3/4 | 7 |

## Pool `union+round`: F1 (cross-fitted threshold)

| design | classifier | median F1 | minus random | +/- | minus QC | minus REAL | +/- | datasets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| boundary0.25/rho0.25+qc | logistic_regression | 0.9240 | -0.0001 | 0/1 | -0.0004 | +0.0030 | 1/0 | 1 |
| boundary0.25/rho0.5+qc | logistic_regression | 0.9249 | +0.0008 | 1/0 | +0.0004 | +0.0038 | 1/0 | 1 |
| boundary0.25/top | logistic_regression | 0.9282 | +0.0040 | 1/0 | +0.0037 | +0.0071 | 1/0 | 1 |
| boundary0.5/rho0.25+qc | logistic_regression | 0.9222 | -0.0019 | 0/1 | -0.0023 | +0.0011 | 1/0 | 1 |
| boundary0.5/rho0.5+qc | logistic_regression | 0.9246 | +0.0005 | 1/0 | +0.0001 | +0.0035 | 1/0 | 1 |
| boundary0.5/top | logistic_regression | 0.9153 | -0.0088 | 0/1 | -0.0092 | -0.0058 | 0/1 | 1 |
| boundary0.75/rho0.25+qc | logistic_regression | 0.9209 | -0.0032 | 0/1 | -0.0036 | -0.0002 | 0/1 | 1 |
| boundary0.75/rho0.5+qc | logistic_regression | 0.9235 | -0.0006 | 0/1 | -0.0010 | +0.0024 | 1/0 | 1 |
| boundary0.75/top | logistic_regression | 0.9212 | -0.0029 | 0/1 | -0.0033 | +0.0001 | 1/0 | 1 |
| boundary0/rho0.25+qc | logistic_regression | 0.9225 | -0.0016 | 0/1 | -0.0019 | +0.0015 | 1/0 | 1 |
| boundary0/rho0.5+qc | logistic_regression | 0.9222 | -0.0019 | 0/1 | -0.0023 | +0.0011 | 1/0 | 1 |
| boundary0/top | logistic_regression | 0.9227 | -0.0014 | 0/1 | -0.0018 | +0.0016 | 1/0 | 1 |
| quality-coverage | logistic_regression | 0.9245 | +0.0003 | 1/0 | +0.0000 | +0.0034 | 1/0 | 1 |
| random(mean of 5) | logistic_regression | 0.9241 | +0.0000 | 0/0 | -0.0003 | +0.0031 | 1/0 | 1 |
| u2/rho0.25+qc | logistic_regression | 0.9197 | -0.0044 | 0/1 | -0.0048 | -0.0014 | 0/1 | 1 |
| u2/rho0.5+qc | logistic_regression | 0.9207 | -0.0034 | 0/1 | -0.0038 | -0.0004 | 0/1 | 1 |
| u2/top | logistic_regression | 0.9147 | -0.0094 | 0/1 | -0.0098 | -0.0064 | 0/1 | 1 |
| boundary0.25/rho0.25+qc | random_forest | 0.9194 | +0.0055 | 1/0 | +0.0074 | +0.0049 | 1/0 | 1 |
| boundary0.25/rho0.5+qc | random_forest | 0.9220 | +0.0081 | 1/0 | +0.0100 | +0.0075 | 1/0 | 1 |
| boundary0.25/top | random_forest | 0.9081 | -0.0058 | 0/1 | -0.0039 | -0.0064 | 0/1 | 1 |
| boundary0.5/rho0.25+qc | random_forest | 0.9257 | +0.0118 | 1/0 | +0.0137 | +0.0112 | 1/0 | 1 |
| boundary0.5/rho0.5+qc | random_forest | 0.9209 | +0.0070 | 1/0 | +0.0089 | +0.0064 | 1/0 | 1 |
| boundary0.5/top | random_forest | 0.9198 | +0.0058 | 1/0 | +0.0077 | +0.0052 | 1/0 | 1 |
| boundary0.75/rho0.25+qc | random_forest | 0.9263 | +0.0124 | 1/0 | +0.0143 | +0.0118 | 1/0 | 1 |
| boundary0.75/rho0.5+qc | random_forest | 0.9248 | +0.0109 | 1/0 | +0.0128 | +0.0103 | 1/0 | 1 |
| boundary0.75/top | random_forest | 0.9254 | +0.0115 | 1/0 | +0.0134 | +0.0109 | 1/0 | 1 |
| boundary0/rho0.25+qc | random_forest | 0.9145 | +0.0005 | 1/0 | +0.0025 | -0.0001 | 0/1 | 1 |
| boundary0/rho0.5+qc | random_forest | 0.9183 | +0.0044 | 1/0 | +0.0063 | +0.0038 | 1/0 | 1 |
| boundary0/top | random_forest | 0.9133 | -0.0006 | 0/1 | +0.0013 | -0.0012 | 0/1 | 1 |
| quality-coverage | random_forest | 0.9120 | -0.0019 | 0/1 | +0.0000 | -0.0025 | 0/1 | 1 |
| random(mean of 5) | random_forest | 0.9139 | +0.0000 | 0/0 | +0.0019 | -0.0006 | 0/1 | 1 |
| u2/rho0.25+qc | random_forest | 0.9163 | +0.0024 | 1/0 | +0.0043 | +0.0018 | 1/0 | 1 |
| u2/rho0.5+qc | random_forest | 0.9234 | +0.0094 | 1/0 | +0.0113 | +0.0088 | 1/0 | 1 |
| u2/top | random_forest | 0.9178 | +0.0038 | 1/0 | +0.0057 | +0.0032 | 1/0 | 1 |

## References minus REAL_INNER_TRAIN (F1, cross-fitted threshold)

| method | classifier | median F1 | minus REAL | +/- | datasets |
| --- | --- | --- | --- | --- | --- |
| SMOTE+b | logistic_regression | 0.8015 | +0.0019 | 4/2 | 6 |
| SMOTE+b | random_forest | 0.7933 | +0.0087 | 5/1 | 6 |
| SMOTENC+b | logistic_regression | 0.2635 | +0.0053 | 1/1 | 2 |
| SMOTENC+b | random_forest | 0.1894 | -0.0342 | 1/1 | 2 |

REAL_INNER_TRAIN median F1: logistic_regression 0.7396, random_forest 0.7496

## Tuning stability (split seeds {13, 29} vs {43, 61, 79})

Spearman correlation of the design rankings (median F1 minus random) between the two halves of the split seeds. Near 0 or negative: the ordering is noise.

| pool | classifier | designs | Spearman |
| --- | --- | --- | --- |
| smote | logistic_regression | 16 | +0.14 |
| smote | random_forest | 16 | +0.05 |
| smote+round | logistic_regression | 11 | +0.10 |
| smote+round | random_forest | 11 | +0.34 |
| union | logistic_regression | 16 | +0.49 |
| union | random_forest | 16 | +0.71 |
| union+round | logistic_regression | 16 | -0.34 |
| union+round | random_forest | 16 | +0.10 |

## Unavailable cells: 115

- Ecoli4 union/boundary0.25/rho0.25+qc: 8
- Ecoli4 union/boundary0.5/rho0.25+qc: 8
- Ecoli4 union/boundary0.75/rho0.25+qc: 8
- Ecoli4 union/boundary0/rho0.25+qc: 6
- Ecoli4 union/u2/rho0.25+qc: 10
- ecoli1 union/u2/rho0.25+qc: 2
- segment0 smote/boundary0.25/rho0.25+qc: 2
- segment0 smote/boundary0.5/rho0.25+qc: 2
- segment0 smote/boundary0.75/rho0.25+qc: 2
- segment0 smote/boundary0/rho0.25+qc: 2
- segment0 smote/u2/rho0.25+qc: 6
- vehicle0 smote+round/boundary0.25/rho0.25+qc: 10
- vehicle0 smote+round/boundary0.5/rho0.25+qc: 10
- vehicle0 smote+round/boundary0.75/rho0.25+qc: 10
- vehicle0 smote+round/boundary0/rho0.25+qc: 8
- vehicle0 smote+round/boundary0/rho0.25+qc: 1 (MATCHED_BUDGET_SHORTFALL)
- vehicle0 smote+round/u2/rho0.25+qc: 6
- vehicle0 smote+round/u2/rho0.25+qc: 2 (MATCHED_BUDGET_SHORTFALL)
- vehicle0 smote/*: 5 (MATCHED_BUDGET_SHORTFALL)
- vehicle0 union/*: 5 (MATCHED_BUDGET_SHORTFALL)
- yeast3 smote/boundary0/rho0.25+qc: 2

## Pools (summed over 5 split(s) x 5 folds)

| dataset | pool | candidates | schema | combined admitted | budget sum |
| --- | --- | --- | --- | --- | --- |
| Abalone19 | smote | 3000 | 3000 | 2612 | 750 |
| Abalone19 | union | 4704 | 4704 | 4089 | 750 |
| Ecoli4 | smote | 3000 | 3000 | 2504 | 750 |
| Ecoli4 | union | 3436 | 3436 | 2865 | 750 |
| abalone9-18 | smote | 3000 | 3000 | 2658 | 750 |
| abalone9-18 | union | 5230 | 5230 | 4616 | 750 |
| ecoli1 | smote | 3000 | 3000 | 2622 | 750 |
| ecoli1 | union | 5968 | 5968 | 5234 | 750 |
| segment0 | smote | 7000 | 7000 | 5906 | 1750 |
| segment0 | union | 20890 | 20890 | 17665 | 1750 |
| vehicle0 | smote | 6400 | 0 | 0 | 1600 |
| vehicle0 | smote+round | 6400 | 6400 | 5386 | 1600 |
| vehicle0 | union | 16496 | 0 | 0 | 1600 |
| vehicle0 | union+round | 16496 | 16496 | 13881 | 1600 |
| yeast3 | smote | 5200 | 5200 | 4408 | 1300 |
| yeast3 | union | 15412 | 15412 | 13094 | 1300 |
| yeast4 | smote | 3000 | 3000 | 2591 | 750 |
| yeast4 | union | 6038 | 6038 | 5199 | 750 |

## Repair variant integer-round-all-half-even-v3

- vehicle0 smote+round: recovered 6400
- vehicle0 union+round: recovered 16496
