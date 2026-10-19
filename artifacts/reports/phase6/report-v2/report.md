# RC-QASyn: consolidated six-phase exploratory results

ENGINEERING COMPLETE; SCIENTIFIC ACCEPTANCE PENDING. All human-final labels remain pending.

## Dataset and evaluation populations

| Dataset | Rows | TRAIN | TEST | TRAIN class counts | TEST class counts | Candidates |
|---|---|---|---|---|---|---|
| Abalone19 | 4174 | 3340 | 834 | {'negative': 3314, 'positive': 26} | {'negative': 828, 'positive': 6} | 200 |
| Ecoli4 | 336 | 269 | 67 | {'negative': 253, 'positive': 16} | {'negative': 63, 'positive': 4} | 201 |
| page-blocks0 | 5472 | 4377 | 1095 | {'negative': 3930, 'positive': 447} | {'negative': 983, 'positive': 112} | 200 |

## Frozen controls and separately filtered utility populations

| control | dataset | original_accepted | original_n | symmetric_difference_from_combined_pass | utility_structural_complete_n |
|---|---|---|---|---|---|
| B1 | Abalone19 | 200 | 200 | 30 | 195 |
| B2 | Abalone19 | 138 | 200 | 78 | 138 |
| B3 | Abalone19 | 200 | 200 | 30 | 195 |
| B1 | Ecoli4 | 201 | 201 | 39 | 195 |
| B2 | Ecoli4 | 174 | 201 | 54 | 174 |
| B3 | Ecoli4 | 200 | 201 | 38 | 195 |
| B1 | page-blocks0 | 200 | 200 | 81 | 136 |
| B2 | page-blocks0 | 175 | 200 | 96 | 116 |
| B3 | page-blocks0 | 200 | 200 | 81 | 136 |

Historical unfiltered task utility is preserved in Phase-1 artifacts. It is not endorsed as a complete-record comparison: absent class can become the string 'nan' in the historical scorer. The new controls explicitly intersect recorded acceptance with authoritative structure compatibility and complete payloads. B1/B2/B3 themselves are unchanged.

## M2 and M4

Five M2 configurations each emit 1,803 evidence records. No evidence family establishes human validity. Full sensitivity rows are in m2.csv. Local/global dependence is measured, not assumed independent.

| Dataset | Paired | Spearman | Tail disagreement |
|---|---|---|---|
| Abalone19 | 200 | 0.907555 | 14 |
| Ecoli4 | 200 | 0.487607 | 30 |
| page-blocks0 | 200 | 0.620549 | 2 |

| ABSTAIN | PROVISIONAL_PASS | REJECT_STRUCTURAL | REVIEW_REQUIRED | dataset | policy |
|---|---|---|---|---|---|
| 0 | 170 | 5 | 25 | Abalone19 | combined-review |
| 0 | 148 | 5 | 47 | Abalone19 | combined-review-q80 |
| 0 | 184 | 5 | 11 | Abalone19 | combined-review-q95 |
| 0 | 177 | 5 | 18 | Abalone19 | global-review |
| 0 | 177 | 5 | 18 | Abalone19 | local-review |
| 0 | 195 | 5 | 0 | Abalone19 | structure-only |
| 0 | 162 | 6 | 33 | Ecoli4 | combined-review |
| 0 | 131 | 6 | 64 | Ecoli4 | combined-review-q80 |
| 0 | 178 | 6 | 17 | Ecoli4 | combined-review-q95 |
| 0 | 177 | 6 | 18 | Ecoli4 | global-review |
| 0 | 175 | 6 | 20 | Ecoli4 | local-review |
| 0 | 195 | 6 | 0 | Ecoli4 | structure-only |
| 0 | 119 | 64 | 17 | page-blocks0 | combined-review |
| 0 | 97 | 64 | 39 | page-blocks0 | combined-review-q80 |
| 0 | 126 | 64 | 10 | page-blocks0 | combined-review-q95 |
| 0 | 120 | 64 | 16 | page-blocks0 | global-review |
| 0 | 120 | 64 | 16 | page-blocks0 | local-review |
| 0 | 136 | 64 | 0 | page-blocks0 | structure-only |

## M6 repair audit

| Dataset | Original | Structural rejects | Eligible | Applied | Ineligible | Post actions | Violation categories (overlap) |
|---|---|---|---|---|---|---|---|
| Abalone19 | 200 | 5 | 0 | 0 | 5 | {} | {'MISSING_CLASS': 5} |
| Ecoli4 | 201 | 6 | 0 | 0 | 6 | {} | {'MISSING_CLASS': 5, 'MISSING_FEATURE': 1} |
| page-blocks0 | 200 | 64 | 54 | 54 | 10 | {'PROVISIONAL_PASS': 49, 'REVIEW_REQUIRED': 5} | {'FRACTIONAL_INTEGER_FIELD': 64, 'MISSING_CLASS': 5} |

75 structural rejects comprise 15 records missing class, one missing required features, and 64 with fractional integer fields; categories overlap. No invalid primitive or unsupported nominal value appears in this historical audit. There are 26 records with multiple field violations. Of the 64 integer-defect records, five also lack class and five require more than three edits; neither group is repaired.

Edit statistics: {'fields': 73, 'maximum': 0.5, 'mean': 0.31191780821917814, 'median': 0.2, 'minimum': 0.1, 'records_by_edited_fields': {'1': 39, '2': 11, '3': 4}}. All 54 attempts become structurally compatible; 49 pass the frozen shadow policy provisionally and five require review. The 21 ineligible original records remain invalid. This is not semantic validity or human approval. Repair runtime: 2.590 s (excludes context loading and construction).

## Fixed-budget construction comparison

M7 objectives, radius .05, near tolerance .01 and quota .5 remain frozen. Budgets are 56/70/49. Original results reproduce their Phase-5 counterparts exactly. Every selected set enforces source-parent exclusivity. Larger candidate pools do not imply larger compared datasets.

| Dataset | Strategy | Condition | Budget | Pool | Derived | Unique TRAIN coverage | Exact duplicates | Near duplicates |
|---|---|---|---|---|---|---|---|---|
| page-blocks0 | source-order | original | 49 | 119 | 0 | 0.913869 | 0.265306 | 0.591837 |
| page-blocks0 | source-order | repair-augmented | 49 | 168 | 11 | 0.909933 | 0.183673 | 0.591837 |
| page-blocks0 | farthest-first | original | 49 | 119 | 0 | 0.932392 | 0.000000 | 0.000000 |
| page-blocks0 | farthest-first | repair-augmented | 49 | 168 | 11 | 0.935865 | 0.000000 | 0.000000 |
| page-blocks0 | coverage-greedy | original | 49 | 119 | 0 | 0.932392 | 0.163265 | 0.448980 |
| page-blocks0 | coverage-greedy | repair-augmented | 49 | 168 | 9 | 0.937022 | 0.081633 | 0.408163 |
| page-blocks0 | quality-coverage | original | 49 | 119 | 0 | 0.932392 | 0.000000 | 0.326531 |
| page-blocks0 | quality-coverage | repair-augmented | 49 | 168 | 16 | 0.937022 | 0.000000 | 0.102041 |
| Ecoli4 | source-order | original | 70 | 162 | 0 | 0.416357 | 0.200000 | 0.385714 |
| Ecoli4 | source-order | repair-augmented | 70 | 162 | 0 | 0.416357 | 0.200000 | 0.385714 |
| Ecoli4 | farthest-first | original | 70 | 162 | 0 | 0.468401 | 0.000000 | 0.000000 |
| Ecoli4 | farthest-first | repair-augmented | 70 | 162 | 0 | 0.468401 | 0.000000 | 0.000000 |
| Ecoli4 | coverage-greedy | original | 70 | 162 | 0 | 0.505576 | 0.114286 | 0.242857 |
| Ecoli4 | coverage-greedy | repair-augmented | 70 | 162 | 0 | 0.505576 | 0.114286 | 0.242857 |
| Ecoli4 | quality-coverage | original | 70 | 162 | 0 | 0.505576 | 0.000000 | 0.000000 |
| Ecoli4 | quality-coverage | repair-augmented | 70 | 162 | 0 | 0.505576 | 0.000000 | 0.000000 |
| Abalone19 | source-order | original | 56 | 170 | 0 | 0.622455 | 0.357143 | 0.625000 |
| Abalone19 | source-order | repair-augmented | 56 | 170 | 0 | 0.622455 | 0.357143 | 0.625000 |
| Abalone19 | farthest-first | original | 56 | 170 | 0 | 0.940120 | 0.000000 | 0.000000 |
| Abalone19 | farthest-first | repair-augmented | 56 | 170 | 0 | 0.940120 | 0.000000 | 0.000000 |
| Abalone19 | coverage-greedy | original | 56 | 170 | 0 | 0.947904 | 0.107143 | 0.267857 |
| Abalone19 | coverage-greedy | repair-augmented | 56 | 170 | 0 | 0.947904 | 0.107143 | 0.267857 |
| Abalone19 | quality-coverage | original | 56 | 170 | 0 | 0.947904 | 0.000000 | 0.000000 |
| Abalone19 | quality-coverage | repair-augmented | 56 | 170 | 0 | 0.947904 | 0.000000 | 0.000000 |

## Task-class utility

138 fixed comparisons: 114 ok and 24 explicitly unavailable. The complete utility.csv includes F1, AP (pr_auc alias), balanced accuracy, MCC and AUROC, source identities and unavailable reasons. No scores are human-validity metrics. TRTR trains real; TSTR trains synthetic only; HYBRID_MINORITY augments real TRAIN with synthetic positive-literal records. Single-class TSTR and empty-minority augmentation are unavailable.

| Dataset | Method | Regime | Classifier | F1 | AP | BA | MCC | Status |
|---|---|---|---|---|---|---|---|---|
| Abalone19 | REAL_TRAIN | TRTR | logistic_regression | 0.000000 | 0.025586 | 0.500000 | 0.000000 | ok |
| Abalone19 | REAL_TRAIN | TRTR | random_forest | 0.000000 | 0.023112 | 0.500000 | 0.000000 | ok |
| Abalone19 | quality-coverage:original | TSTR | logistic_regression | 0.031169 | 0.019120 | 0.774758 | 0.093271 | ok |
| Abalone19 | quality-coverage:original | HYBRID_MINORITY | logistic_regression | 0.000000 | 0.016962 | 0.500000 | 0.000000 | ok |
| Abalone19 | quality-coverage:repair-augmented | TSTR | logistic_regression | 0.031169 | 0.019120 | 0.774758 | 0.093271 | ok |
| Abalone19 | quality-coverage:repair-augmented | HYBRID_MINORITY | logistic_regression | 0.000000 | 0.016962 | 0.500000 | 0.000000 | ok |
| Ecoli4 | REAL_TRAIN | TRTR | logistic_regression | 1.000000 | 1.000000 | 1.000000 | 1.000000 | ok |
| Ecoli4 | REAL_TRAIN | TRTR | random_forest | 0.666667 | 1.000000 | 0.750000 | 0.696143 | ok |
| Ecoli4 | quality-coverage:original | TSTR | logistic_regression | 0.205128 | 0.135472 | 0.753968 | 0.240935 | ok |
| Ecoli4 | quality-coverage:original | HYBRID_MINORITY | logistic_regression | 1.000000 | 1.000000 | 1.000000 | 1.000000 | ok |
| Ecoli4 | quality-coverage:repair-augmented | TSTR | logistic_regression | 0.205128 | 0.135472 | 0.753968 | 0.240935 | ok |
| Ecoli4 | quality-coverage:repair-augmented | HYBRID_MINORITY | logistic_regression | 1.000000 | 1.000000 | 1.000000 | 1.000000 | ok |
| page-blocks0 | REAL_TRAIN | TRTR | logistic_regression | 0.715026 | 0.745587 | 0.801932 | 0.699139 | ok |
| page-blocks0 | REAL_TRAIN | TRTR | random_forest | 0.869159 | 0.921292 | 0.910601 | 0.856172 | ok |
| page-blocks0 | quality-coverage:original | TSTR | logistic_regression | 0.446429 | 0.555165 | 0.759033 | 0.389169 | ok |
| page-blocks0 | quality-coverage:original | HYBRID_MINORITY | logistic_regression | 0.715026 | 0.744361 | 0.801932 | 0.699139 | ok |
| page-blocks0 | quality-coverage:repair-augmented | TSTR | logistic_regression | 0.342105 | 0.571619 | 0.712914 | 0.277985 | ok |
| page-blocks0 | quality-coverage:repair-augmented | HYBRID_MINORITY | logistic_regression | 0.715026 | 0.742349 | 0.801932 | 0.699139 | ok |

The quality-coverage page-blocks0 logistic TSTR F1 decreases after repair-pool expansion while AP increases slightly. Hybrid F1 is unchanged for that comparison. These mixed outcomes do not support a uniform utility-improvement claim. The fixed TEST set was already evaluated historically and has documented exact-value TRAIN/TEST overlap. No TEST result selected a policy, repair rule, budget, classifier or seed. No independent inner TRAIN validation is claimed because frozen generation/evidence used full TRAIN. Replays are not repetitions; no confidence interval or significance claim is made.

Utility runtime: 24.127 s including context loading and all 138 rows. registry.csv contains 258 experiment entries with shared exact source/split/model bindings in artifact.json and upstream sealed artifacts.

## Representative large-shift cases

- Parent `occ-0dff1cacd137fcd70af5fc2df31a9c3f285f90d301a105eb6e69c96a649df6a6`; derived `m6:646ee5d8fd1c433ef8788bd572942a710ea874a20640b40195c798080f097f34`; edits [{'absolute_change': 0.5, 'absolute_change_decimal': '0.5', 'field': 'height', 'justification': 'Approved integer compatibility correction; not semantic validation', 'original_value': 4.5, 'repaired_value': 4, 'rule_id': 'page-blocks0:schema', 'source_declaration': 'integer [1, 804]'}, {'absolute_change': 0.5, 'absolute_change_decimal': '0.5', 'field': 'Lenght', 'justification': 'Approved integer compatibility correction; not semantic validation', 'original_value': 32.5, 'repaired_value': 32, 'rule_id': 'page-blocks0:schema', 'source_declaration': 'integer [1, 553]'}]; percentile changes {'cross_feature': 0.007499999999999951, 'local_support': 0.02749999999999997}; action PROVISIONAL_PASS; source {'source_artifact': 'artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/candidates_raw.jsonl', 'source_artifact_sha256': 'f22ba0456ce2eb0233cf3548944ed0ca2edff3dace18e3786b2d41e8b323ee06', 'source_occurrence_ordinal': 131}.
- Parent `occ-fdca9a4e3e1f6e97290555b1a52dd7bd30011768f9a788156b08c6b995b588c8`; derived `m6:fd665241ebe69dad071ce0e8632b97cd6c1de54132e1b912178451bf2ccc595e`; edits [{'absolute_change': 0.5, 'absolute_change_decimal': '0.5', 'field': 'height', 'justification': 'Approved integer compatibility correction; not semantic validation', 'original_value': 1.5, 'repaired_value': 2, 'rule_id': 'page-blocks0:schema', 'source_declaration': 'integer [1, 804]'}]; percentile changes {'cross_feature': -0.0025000000000000022, 'local_support': -0.017500000000000016}; action PROVISIONAL_PASS; source {'source_artifact': 'artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/candidates_raw.jsonl', 'source_artifact_sha256': 'f22ba0456ce2eb0233cf3548944ed0ca2edff3dace18e3786b2d41e8b323ee06', 'source_occurrence_ordinal': 154}.
- Parent `occ-96efa127cc1a74600436b64ef87d65f091f36bd214489824810e147db44e9605`; derived `m6:bf8d4c022a235980024c5d6ea04be7fe0a93bbef70559402fe349bb5a2a098ef`; edits [{'absolute_change': 0.3, 'absolute_change_decimal': '0.3', 'field': 'Lenght', 'justification': 'Approved integer compatibility correction; not semantic validation', 'original_value': 38.7, 'repaired_value': 39, 'rule_id': 'page-blocks0:schema', 'source_declaration': 'integer [1, 553]'}]; percentile changes {'cross_feature': -0.01749999999999996, 'local_support': -0.0024999999999999467}; action PROVISIONAL_PASS; source {'source_artifact': 'artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/candidates_raw.jsonl', 'source_artifact_sha256': 'f22ba0456ce2eb0233cf3548944ed0ca2edff3dace18e3786b2d41e8b323ee06', 'source_occurrence_ordinal': 51}.
- Parent `occ-f6972e7838641985c6fd3d422b899f97249a63229c89aaf7951c99d0de642928`; derived `m6:9474e637455b7409b93a69f8c9ecb20a22e80224373325bbd4ec560580c76b5c`; edits [{'absolute_change': 0.5, 'absolute_change_decimal': '0.5', 'field': 'height', 'justification': 'Approved integer compatibility correction; not semantic validation', 'original_value': 1.5, 'repaired_value': 2, 'rule_id': 'page-blocks0:schema', 'source_declaration': 'integer [1, 804]'}, {'absolute_change': 0.2, 'absolute_change_decimal': '0.2', 'field': 'Lenght', 'justification': 'Approved integer compatibility correction; not semantic validation', 'original_value': 7.8, 'repaired_value': 8, 'rule_id': 'page-blocks0:schema', 'source_declaration': 'integer [1, 553]'}]; percentile changes {'cross_feature': -0.0025000000000000022, 'local_support': -0.012500000000000011}; action PROVISIONAL_PASS; source {'source_artifact': 'artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/candidates_raw.jsonl', 'source_artifact_sha256': 'f22ba0456ce2eb0233cf3548944ed0ca2edff3dace18e3786b2d41e8b323ee06', 'source_occurrence_ordinal': 132}.
- Parent `occ-efaf030916cfe23366e4475e3ca8d1e9f95023756e634d0a7ba3009c3af3cb29`; derived `m6:75bfb2a4ef042e4567f9ebf50eb63da21ff64923da25b3de7fcbf461210216d1`; edits [{'absolute_change': 0.5, 'absolute_change_decimal': '0.5', 'field': 'height', 'justification': 'Approved integer compatibility correction; not semantic validation', 'original_value': 1.5, 'repaired_value': 2, 'rule_id': 'page-blocks0:schema', 'source_declaration': 'integer [1, 804]'}]; percentile changes {'cross_feature': -0.012500000000000011, 'local_support': -0.0025000000000000022}; action PROVISIONAL_PASS; source {'source_artifact': 'artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/candidates_raw.jsonl', 'source_artifact_sha256': 'f22ba0456ce2eb0233cf3548944ed0ca2edff3dace18e3786b2d41e8b323ee06', 'source_occurrence_ordinal': 150}.

## Deferred decisions

| Question | Status | Evidence | Options |
|---|---|---|---|
| Personal review of all 120 labels | HUMAN_DECISION_PENDING | 0/27/93 agent VALID/INVALID/INDETERMINATE; no human-final approvals | Review/correct every label and explicitly confirm reviewed ledger fingerprint |
| Original target mappings and physical/cross-field semantics | HUMAN_DECISION_PENDING | Dataset specifications distinguish literal source declarations from missing domain meaning | Supply authoritative semantics, or retain unresolved limitations |
| Official calibration eligibility | HUMAN_DECISION_PENDING | Actual cohort unapproved; no validity-positive reference class | Only reconsider after approved independent labels with both classes |
| Scientific acceptance and final claims | HUMAN_DECISION_PENDING | Six engineering phases and exploratory evidence; single historical split/seed with prior TEST use | Supervisor accepts or revises interpretation; no automatic freeze |
| Authors, contributions and institutional declarations | HUMAN_DECISION_PENDING | Placeholders and explicit AI assistance statement in draft | Human authors supply accurate affiliations, funding, conflicts and venue-policy wording |

## Reproduction and interpretation

See docs/phase6-m6-m9-methods.md for exact commands/formulas. Core and utility replays match substantive fingerprints. Runtime-bearing envelopes intentionally differ; no fabricated identical wall time. Every original occurrence is preserved, derived records bind authoritative parents, and no provider is called. Stage-6 structural correction, percentile concern, provisional admission, TRAIN geometry and task utility remain distinct quantities. Calibration and official B2/B3-versus-human analysis remain inactive. Final QA and historical-byte verification are recorded separately in the closeout bundle.
