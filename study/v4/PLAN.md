# Study v4 plan: what LLM-generated tabular data is like, and when quality control matters

Agent-facing plan. Read this file and `STATUS.md` at the start of every session. The rules
of `CLAUDE.md` (no test leakage, raw before parsed, missing accounting null, B1/B2/B3
untouched, no human column filled, protected paths untouched, no significance beyond the
frozen protocol) apply unchanged. Study v4 opened 2026-11-09 at the user's request after
Study v3 closed with a negative result.

## Questions

**A. Audit (descriptive).** Across 3 LLM generators (Claude Haiku 5.5, GPT-6 luna, Muse
Spark 1.3) and 3 statistical/U2 generators (SMOTE, U2 native, U2 with FlowGMM gate) on 40
benchmark datasets x 5 splits: how valid, faithful, diverse and original are the generated
minority records, and what do they cost? Where do the generators differ, and which dataset
properties predict failure?

**B. When does quality control matter?** Study v3 added synthetic rows equal to a median 1.9%
of TRAIN, so selection could hardly change a classifier. Study B trains with **real majority
+ synthetic minority only** (the real minority is replaced, not augmented): every synthetic
minority record now carries the whole minority class. Does the RC-QASyn gate, quality-coverage
selection or the merged method then beat random selection from the same pool, and how close
does each generator come to training on the same number of real minority records?

## Inputs (read-only, reused from Study v3; never modified)

- Benchmark root `study/v3/runs/benchroot` (40 converted datasets, conversion records).
- LLM pools `study/v3/runs/phase3/llm/<model>/<dataset>__s<seed>/` (raw, calls, candidates).
- U2-side pools `study/v3/runs/phase3/u2/units/*.json` (kick: s13 only).
- Splits: the v3 outer split + 20% VALIDATION carve (`study.v3.phase3.split_frames`).
- Code: `rcqasyn` and `study.v3` by import; v4 code lives in `study/v4/`.
Phase 0 records the SHA-256 of every input file used (`report/phase0/inputs.json`).

## Fixed design (change only with user approval)

- **Reference for every audit metric: inner TRAIN only** (outer TRAIN minus VALIDATION).
  Part A never reads VALIDATION or TEST.
- **Compute limits declared before any result** (lesson from v3): gate-based audit metrics
  and Part B run on datasets with outer TRAIN <= 50,000 rows; larger datasets (kick,
  GiveMeSomeCredit, creditcard, and any other above the line) get the cheap audit metrics
  only and are listed as `SIZE_LIMIT` for the rest.
- **Part B design** (details frozen at Gate 2): per unit, k = min(real inner-TRAIN minority
  count, smallest admitted pool size among the compared generators); every method trains
  on all real inner-TRAIN majority rows + exactly k minority rows. Methods: real minority
  subsampled to k (reference), and for each generator pool: random k from the raw pool,
  random k from the gate-admitted pool, quality-coverage k, merged-method k. Learners:
  logistic regression, random forest, XGBoost (U2 search spaces and threshold rule, as v3).
- **Primary metric (Part B):** minority F1 on REAL TEST at the validation-chosen threshold;
  statistics fixed at Gate 2 (paired Wilcoxon + Holm over a pre-declared family).
- Spend: no new API calls are planned (all LLM pools exist). Any new call needs a gate.

## Phases and gates

### Phase 0 - Setup
- [ ] `PLAN.md`, `STATUS.md`, `protocol.json` draft; input manifest with SHA-256.
- **Gate 0**: user confirms the plan (scope, size limit, Part B design).

### Phase 1 - Audit (Part A; inner TRAIN only)
- [ ] Output health: requests, parse success, records returned vs requested, truncation,
      schema mismatch, cost per valid record (from v3 ledgers and call logs).
- [ ] Validity: declared-schema completeness, category domain, range (B2 validators as
      descriptive counts; B2 itself untouched).
- [ ] Copying diagnostics: exact copies of inner TRAIN rows, of prompt reference rows
      (LLM), within-pool duplicates. Copying diagnostics, never privacy claims.
- [ ] Fidelity vs inner-TRAIN minority: per-feature distances (numeric KS / scaled
      Wasserstein, categorical total variation), correlation-matrix difference,
      discriminator AUC (real vs synthetic, cross-validated inside inner TRAIN).
- [ ] Support and diversity: RC-QASyn gate admission and raw support scores (one model fit
      per unit, all generators scored against it), nearest-neighbour distance to TRAIN and
      within the pool, coverage of real minority rows.
- [ ] Report `report/phase1/`: per generator, per dataset, by dataset properties
      (rows, features, categorical share, missing cells). Descriptive only.
- **Gate 1**: findings; user confirms Part B details.

### Phase 2 - Part B design on VALIDATION (no TEST)
- [ ] Run Part B on the VALIDATION carve; check k, availability and run time.
- [ ] Freeze protocol (SHA-256 in STATUS) before any TEST metric.
- **Gate 2**: protocol frozen.

### Phase 3 - Part B on TEST
- [ ] Final evaluation (U2 protocol: choose on VALIDATION, refit on TRAIN, score TEST),
      claim-locked workers launched outside Claude Code.
- **Gate 3**: runs complete.

### Phase 4 - Analysis and report
- [ ] Declared tests only; per-generator and per-dataset breakdowns; reconciliation.
- **Gate 4**: results review with the user.

## Never

Read VALIDATION or TEST in Part A; peek at TEST before Gate 2; rerun to get better numbers;
drop unfavourable rows; modify v3 runs or reports; edit protected paths; "improve" B1/B2/B3;
fill human-review columns; describe exact-match copying as a privacy result.
