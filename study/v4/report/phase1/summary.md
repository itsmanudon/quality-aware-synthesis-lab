# Study v4 Phase 1: audit of generated minority records (inner TRAIN only)

200 units, 40 datasets. Medians over units (each unit: one dataset x split, one pool of up to 4 x B records). Descriptive only: no test; exact matches are copying diagnostics, never privacy results; distances are exploratory. VALIDATION and TEST were never read.

## Per generator (median over units)

| metric | claude-haiku-5-5 | gpt-6-luna | muse-spark-1.3 | smote | u2_native | u2_flow_gate |
|---|---|---|---|---|---|---|
| complete (raw) | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| complete after integer rounding | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| not the requested class | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| exact copy of an inner-TRAIN row | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| exact copy of a prompt reference row | 0.000 | 0.000 | 0.000 |  |  |  |
| within-pool duplicate | 0.000 | 0.000 | 0.000 | 0.000 | 0.011 | 0.000 |
| categorical cells unseen in TRAIN | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| numeric cells outside the TRAIN range | 0.000 | 0.000 | 0.000 | 0.038 | 0.035 | 0.021 |
| mean KS (numeric) vs real minority | 0.260 | 0.248 | 0.257 | 0.172 | 0.208 | 0.238 |
| mean total variation (categorical) | 0.180 | 0.169 | 0.183 | 0.043 | 0.087 | 0.089 |
| mean |correlation difference| | 0.322 | 0.308 | 0.304 | 0.053 | 0.075 | 0.092 |
| discriminator AUC (0.5 = indistinguishable) | 0.982 | 0.985 | 0.982 | 0.460 | 0.565 | 0.670 |
| distance 0 to a TRAIN row | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| closer to TRAIN than real minority rows are to each other | 0.500 | 0.578 | 0.504 | 0.988 | 0.972 | 0.956 |
| within-pool spread / real-minority spread | 0.544 | 0.617 | 0.653 | 0.339 | 0.292 | 0.372 |
| real minority covered | 0.117 | 0.133 | 0.164 | 0.841 | 0.743 | 0.590 |
| gate admitted (combined) | 0.815 | 0.795 | 0.842 | 0.892 | 0.877 | 0.864 |
| gate local-support raw score (median) | 0.052 | 0.057 | 0.052 | 0.028 | 0.028 | 0.032 |
| units with a pool | 200 | 200 | 200 | 196 | 196 | 196 |

## LLM output health and cost

| generator | calls ok | parse failures / call | truncated calls | records returned / requested | complete records | spend | $ per 1,000 complete |
|---|---|---|---|---|---|---|---|
| claude-haiku-5-5 | 2730 | 0.077 | 202 | 0.785 | 37376 | $3.17 | $0.085 |
| gpt-6-luna | 2730 | 0.000 | 1 | 1.005 | 45469 | $2.60 | $0.057 |
| muse-spark-1.3 | 2465 | 0.005 | 12 | 0.995 | 44807 | $56.65 | $1.264 |

Spend is the provider's total Study v3 ledger spend (all Phase 3 calls of that model, pilots included), divided by complete records in the audited units; one model per provider.

## Discriminator AUC per dataset (median over splits)

| dataset | rows | features | categorical | claude-haiku-5-5 | gpt-6-luna | muse-spark-1.3 | smote | u2_native | u2_flow_gate |
|---|---|---|---|---|---|---|---|---|---|
| oml43 | 245 | 3 | 0.33 | 0.77 | 0.74 | 0.80 | 0.32 | 0.28 | 0.51 |
| oml1506 | 376 | 16 | 0.81 | 0.90 | 0.79 | 0.85 | 0.30 | 0.42 | 0.47 |
| oml949 | 447 | 4 | 0.25 | 0.90 | 0.91 | 0.90 | 0.39 | 0.30 | 0.44 |
| oml1464 | 598 | 4 | 0.00 | 0.96 | 0.93 | 0.92 | 0.50 | 0.59 | 0.81 |
| oml1016 | 792 | 12 | 0.17 | 0.96 | 0.94 | 0.97 | 0.32 | 0.33 | 0.33 |
| oml1068 | 888 | 21 | 0.00 | 0.96 | 0.94 | 0.95 | 0.44 | 0.35 | 0.68 |
| oml1049 | 1166 | 37 | 0.00 | 0.99 | 0.99 | 1.00 | 0.45 | 0.54 | 0.60 |
| oml43893 | 1176 | 26 | 0.00 | 0.98 | 0.97 | 0.95 | 0.69 | 0.79 | 0.82 |
| oml1050 | 1250 | 37 | 0.00 | 0.98 | 0.99 | 0.99 | 0.48 | 0.47 | 0.60 |
| oml46938 | 1379 | 13 | 0.62 | 0.98 | 0.99 | 0.97 | 0.38 | 0.42 | 0.46 |
| oml1020 | 1600 | 64 | 0.00 | 1.00 | 0.99 | 1.00 | 0.37 | 0.38 | 0.38 |
| oml971 | 1600 | 76 | 0.00 | 1.00 | 0.99 | 1.00 | 0.33 | 0.45 | 0.46 |
| oml995 | 1600 | 47 | 0.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.52 | 0.48 |
| oml1067 | 1687 | 21 | 0.00 | 0.99 | 0.99 | 0.98 | 0.47 | 0.54 | 0.70 |
| oml46940 | 1792 | 24 | 0.33 | 1.00 | 1.00 | 0.99 | 0.52 | 0.59 | 0.67 |
| oml1487 | 2027 | 72 | 0.00 | 0.99 | 0.99 | 0.98 | 0.47 | 0.50 | 0.54 |
| oml45562 | 2067 | 18 | 0.22 | 0.96 | 0.97 | 0.96 | 0.39 | 0.40 | 0.66 |
| oml44232 | 2666 | 16 | 0.00 | 0.95 | 0.96 | 0.98 | 0.68 | 0.73 | 0.71 |
| oml40713 | 3017 | 29 | 0.79 | 0.97 | 0.96 | 0.91 | 0.37 | 0.30 | 0.46 |
| oml41946 | 3018 | 29 | 0.00 | 0.98 | 0.98 | 0.99 | 0.48 | 0.54 | 0.64 |
| oml1558 | 3617 | 16 | 0.56 | 0.95 | 0.96 | 0.96 | 0.49 | 0.60 | 0.62 |
| oml40983 | 3871 | 5 | 0.00 | 0.97 | 0.96 | 0.97 | 0.30 | 0.46 | 0.45 |
| oml40900 | 4080 | 36 | 0.00 | 0.91 | 0.94 | 0.93 | 0.32 | 0.44 | 0.38 |
| oml1021 | 4378 | 10 | 0.00 | 0.99 | 1.00 | 0.99 | 0.43 | 0.66 | 0.69 |
| oml980 | 4496 | 64 | 0.00 | 1.00 | 1.00 | 1.00 | 0.74 | 0.75 | 0.74 |
| oml1018 | 7075 | 56 | 0.73 | 1.00 | 1.00 | 0.99 | 0.41 | 0.68 | 0.69 |
| oml46281 | 7858 | 85 | 0.73 | 0.98 | 0.99 | 0.99 | 0.37 | 0.53 | 0.55 |
| oml976 | 7969 | 14 | 0.00 | 1.00 | 0.99 | 1.00 | 0.48 | 0.72 | 0.69 |
| oml46911 | 8000 | 10 | 0.40 | 0.89 | 0.83 | 0.90 | 0.55 | 0.77 | 0.78 |
| oml1053 | 8708 | 21 | 0.00 | 1.00 | 0.99 | 0.99 | 0.57 | 0.88 | 0.93 |
| oml1019 | 8793 | 16 | 0.00 | 1.00 | 1.00 | 1.00 | 0.68 | 0.77 | 0.75 |
| oml310 | 8946 | 6 | 0.00 | 0.98 | 0.98 | 0.99 | 0.40 | 0.52 | 0.59 |
| oml45560 | 9864 | 17 | 0.41 | 0.98 | 0.98 | 0.96 | 0.57 | 0.81 | 0.84 |
| oml45558 | 14318 | 8 | 0.00 | 0.98 | 0.97 | 0.97 | 0.43 | 0.78 | 0.79 |
| oml977 | 16000 | 16 | 0.00 | 1.00 | 1.00 | 1.00 | 0.67 | 0.81 | 0.80 |
| oml42477 | 24000 | 23 | 0.00 | 0.98 | 0.99 | 0.97 | 0.63 | 0.92 | 0.88 |
| oml1590 | 39074 | 14 | 0.57 | 0.91 | 0.90 | 0.91 | 0.52 | 0.86 | 0.78 |
| oml41162 | 58387 | 32 | 0.56 | 0.73 | 0.99 | 0.98 | 0.47 | 0.80 | 0.70 |
| oml46929 | 120000 | 10 | 0.00 |  | 0.98 | 0.97 | 0.70 | 0.94 | 0.96 |
| oml1597 | 227846 | 29 | 0.00 | 1.00 | 1.00 | 1.00 | 0.40 | 0.68 | 0.69 |

## Spearman correlation with dataset properties (over units)

| generator | metric | rows | features | categorical share |
|---|---|---|---|---|
| claude-haiku-5-5 | discriminator_auc | +0.21 | +0.46 | -0.36 |
| claude-haiku-5-5 | train_copy_rate | +0.06 | -0.13 | +0.04 |
| claude-haiku-5-5 | complete_rate | -0.26 | -0.26 | -0.50 |
| gpt-6-luna | discriminator_auc | +0.32 | +0.47 | -0.36 |
| gpt-6-luna | train_copy_rate | -0.24 | -0.09 | +0.13 |
| gpt-6-luna | complete_rate | -0.26 | -0.10 | -0.43 |
| muse-spark-1.3 | discriminator_auc | +0.27 | +0.46 | -0.43 |
| muse-spark-1.3 | train_copy_rate | -0.18 | -0.23 | +0.09 |
| muse-spark-1.3 | complete_rate | -0.42 | -0.17 | -0.41 |
| smote | discriminator_auc | +0.40 | -0.01 | -0.22 |
| smote | train_copy_rate | +0.08 | -0.16 | +0.08 |
| smote | complete_rate | -0.06 | +0.14 | -0.32 |
| u2_native | discriminator_auc | +0.72 | -0.07 | -0.22 |
| u2_native | train_copy_rate | -0.01 | -0.24 | +0.14 |
| u2_native | complete_rate | -0.06 | +0.14 | -0.32 |
| u2_flow_gate | discriminator_auc | +0.52 | -0.24 | -0.18 |
| u2_flow_gate | train_copy_rate | +0.04 | +0.20 | +0.27 |
| u2_flow_gate | complete_rate | -0.06 | +0.14 | -0.32 |

## Unavailable

- claude-haiku-5-5: NO_PARSED_RECORDS: 7 units
- gate: GATE_NO_COMPLETE_TRAIN_ROW: 5 units
- gate: SIZE_LIMIT: 15 units
- smote: NO_U2_UNIT: 4 units
- u2_flow_gate: NO_U2_UNIT: 4 units
- u2_native: NO_U2_UNIT: 4 units
