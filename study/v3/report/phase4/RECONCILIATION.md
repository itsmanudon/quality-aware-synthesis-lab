# Study v3: reconciliation of plan, protocol and what was run (Phase 4, 2026-11-08)

What the frozen protocol planned, what was actually run, every deviation with its reason,
and the declared results. Read with `summary.md` (all declared tests and the full
unavailable list), `unavailable.csv`, `cells.csv` and `per_dataset_success_f1.csv` in this
folder. Descriptive except where a declared test is named; no claim beyond the protocol.

## 1. Protocol state

| Item | Value |
| --- | --- |
| Frozen protocol | `study/v3/protocol.json`, SHA-256 `a65e20f96d093c9f8f18190027429a0f78c02fbf58f08d88d3d5d7dd58f8cb30` (Gate 2, 2026-11-02); unchanged |
| Amendment 1 (gate 2a) | kick (oml41162) unavailable for every method, `U2_SIDE_COMPUTE_LIMIT`; SHA-256 `951c6569...4947` |
| Amendment 2 (gate 2b) | creditcard (oml1597) stage-2 comparators unavailable, `EVALUATION_COMPUTE_LIMIT`; its stage 1 kept; SHA-256 `f41ee997...ccd5` |
| Blinding | Both amendments were decided before any affected unit was evaluated (kick) or before Phase 4 was run (creditcard); no TEST result had been aggregated or read |
| Every TEST unit | evaluated under the frozen SHA-256; `u3_eval.py` and `phase4.py` refuse anything else |

## 2. Planned vs done

| Component | Planned (protocol) | Done |
| --- | --- | --- |
| Benchmark datasets | 40 (30 U2 core + 10 new) | 39 in the analysis; kick excluded (amendment 1) |
| Units (dataset x split) | 200 | 195 curated; stage 1 195/195; stage 2 191/195 (creditcard 1 of 5) |
| LLM generators | Haiku, gpt-6-luna, Muse Spark on all units | all three complete (2,730 / 2,730 / 2,465 requests ok) |
| LLM subsets | Sonnet ~5 datasets, GPT-6.1-terra ~8-10 | not run: Haiku and luna used the Anthropic/OpenAI headroom under the 80% lines (declared before the freeze) |
| Local LLMs | Phase 2 ablation | done for qwen2.5:7b (40/40 folds); not in Phase 3 (declared) |
| Methods | merged + 25 comparators/variants | 26 methods evaluated |
| Learners | LR, RF, XGBoost, MLP, RBF SVM | all five |
| Final-evaluation design | U2 protocol, 20% validation | as declared at the freeze (compute deviation from Gate 1's cross-fitting, declared then) |

## 3. Deviations and incidents, with how each was handled

| # | What happened | Effect | Handling |
| --- | --- | --- | --- |
| 1 | kick: U2-side generation took ~70 h / 529 CPU-hours for 1 of 5 splits | 9-10 more days projected | Amendment 1; deferred to a cloud run, to be reported as supplementary |
| 2 | creditcard: one stage-2 unit took 48 h | 4 of 5 stage-2 units unfinished | Amendment 2; stage 1 kept; deferred to the cloud run |
| 3 | ipums (oml1018): 0 of 5,660 TRAIN rows complete (14 of 56 columns with missing cells) | the RC-QASyn gate (fitted on complete TRAIN rows) cannot be built | gated methods recorded `GATE_NO_COMPLETE_TRAIN_ROW`; non-gated comparators evaluated; ipums leaves the merged comparisons (38 datasets). **A finding about the gate** |
| 4 | KEEL `?` missing marker read literally by the U2 bridge | jm1 crashed; adult's nominal `?` became a category | fixed (`e0ed118`); adult's 5 U2 units regenerated at the user's decision, old ones kept in `runs/phase3/u2/superseded/` |
| 5 | NaN reached the gate's JSON fingerprints (jm1, GiveMeSomeCredit) | curation crashes | missing cells passed as null (`c290d9e`, `67ce669`); datasets without missing cells unchanged |
| 6 | Haiku on GiveMeSomeCredit: every reply hit `max_tokens`, JSON truncated | no Haiku pool on its 5 units (`NO_LLM_POOL`) | replies never repaired (project rule); merged built from the other generators there |
| 7 | A Haiku batch was collected twice by two drivers | duplicate lines | per-model lock; readers count once; ledger repeat annotated, not double-counted (`df6e732`, `4fb86d0`) |
| 8 | qwen on segment0 (Phase 2 dev) never returned the records object | no qwen pool there | reported `EMPTY_POOL` in the Phase 2 ablation |
| 9 | Five-learner check (Phase 2): every design within about +/-0.003 F1 of random | utility-aware selection about neutral on dev data | merged_method kept as pre-selected (beta 0.5, rho 0.5); declared before the freeze |
| 10 | Claude Code's low-memory reaping stopped background jobs repeatedly | lost time only (every job resumed from its last unit) | WSL/Docker and Ollama stopped at the user's request; jobs launched outside Claude Code (`run_phase3.ps1`) with per-unit claim locks |

## 4. Unavailable cells (each listed in `unavailable.csv`)

| Reason | Count | Meaning |
| --- | --- | --- |
| SVM_SIZE_LIMIT | 333 | RBF SVM on > 20,000 training rows (declared at the freeze) |
| NO_CLASS_WEIGHT_IN_U2_MLP | 191 | U2's MLP has no class weight (declared) |
| Unavailable (addendum v2 rules) | 185 | e.g. ADASYN / Borderline-SMOTE without a nominal path or with missing cells |
| MATCHED_BUDGET_SHORTFALL | 105 | fewer admitted rows than the budget B |
| EVALUATION_COMPUTE_LIMIT | 71 | creditcard stage 2 (amendment 2) |
| GATE_NO_COMPLETE_TRAIN_ROW | 50 | ipums, gated methods |
| FEWER_THAN_3_OF_5_SPLITS | 35 | frozen 3-of-5 rule |
| ValueError (comparator could not run) | 33 | e.g. CLLM-style's gradient boosting rejects NaN |
| NO_LLM_POOL | 5 | GiveMeSomeCredit, Haiku |
| U2_SIDE_COMPUTE_LIMIT | 1 | kick (all methods) |

## 5. Results (declared tests only; `summary.md` has every number)

**Success criterion: not met.**

| Merged vs | Datasets | Median F1 difference | 95% bootstrap CI | Above / below | Holm p |
| --- | --- | --- | --- | --- | --- |
| tuned no oversampling | 38 | -0.0005 | [-0.0025, -0.0002] | 12 / 26 | 0.051 |
| U2 | 38 | -0.0007 | [-0.0047, +0.0002] | 15 / 23 | 0.051 |

- The merged method's median F1 is slightly **below** both success comparators. Neither
  difference reaches Holm-adjusted p < 0.05, so the success test fails on its first
  condition (a positive median difference with p < 0.05).
- The MCC no-loss check finds a **significant MCC loss against U2** (median -0.0015, Holm
  p 0.019); none against tuned no oversampling (Holm p 0.20).
- Comparator family (merged vs 23 other methods): no Holm-adjusted difference; every median
  difference lies within about +/-0.004 F1.
- Friedman over the 8 main methods (37 complete datasets): p 0.36. Average ranks, best
  first: U2 3.92, tuned no oversampling 4.15, merged 4.23, class-weighted 4.27,
  quality-coverage 4.58, SMOTE 4.82, paper-derived UGO 4.89, random 5.14.

Reading, as the protocol requires: on this benchmark the merged pipeline does not improve
minority-class F1 over tuned no oversampling or over U2; differences between all methods
are small. This matches the Phase 2 dev finding that utility-aware selection is about
neutral (deviation 9). The miss is reported as found (scope decision, Gate 1).

## 6. Spend (all under the 80% stop lines)

| Provider | Spent | Cap | 80% line |
| --- | --- | --- | --- |
| Anthropic | $3.17 | $5 | $4.00 |
| OpenAI | $2.60 | $4 | $3.20 |
| Meta | $56.65 | $140 | $112.00 |

No unknown-cost ledger lines remain (one bounded by reconciliation; one repeated batch line
annotated).

## 7. Deferred work

- **Cloud run (supplementary):** kick (all 5 units) and creditcard stage 2 (s13, s43, s61,
  s79), with the same code, frozen protocol and SHA-256 check. Results are reported beside
  this analysis, not in place of it.
- **Human labels:** the blinded Phase 2 sample (`report/phase2/label-sample/`) awaits the
  team; the agent fills no human column.
- **Gate 4:** results review with the user and the professor before Phase 5 (the paper).
