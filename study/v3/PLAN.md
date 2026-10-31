# Study v3 plan: merged U2 + RC-QASyn paper

Agent-facing version of the team's plan. Human-facing version: the "RC-QASyn Study v3 Plan"
doc. Read this file and `STATUS.md` at the start of every session. Rules for unattended
work are in `CLAUDE.md`, section "Autonomous operation (Study v3)".

## Question

Does the merged method improve minority F1 over tuned no oversampling and over U2 alone,
across 40 datasets? The merged method takes candidates from U2, LLMs and SMOTE, passes them
through RC-QASyn's quality gate (schema checks, support evidence, admission, bounded
repair), and selects with a utility term built from U2's difficulty and stability scores.

This is ONE merged paper (approved by the professor): RC-QASyn plus the team's U2 paper
("Real-support-constrained uncertainty-guided oversampling with a frozen flow compatibility
gate", which extends UGO, Saglam and Cengiz 2026, KBS 342:115886). The U2 draft is frozen;
do not change its code or results.

Starting points. RC-QASyn (Empirical v2, addenda v1/v2): coverage gains but no reliable
F1/AP gain over random selection (median QC minus random F1: +0.001 LR, +0.013 RF;
exploratory p 0.19-1.00). U2 over 30 OpenML datasets: minority F1 0.6376 vs UGO 0.6247
(Holm p 0.029) but tuned no oversampling reaches 0.6369, with higher AP.

## Limitations this study must close

The IEEE draft proposes the pipeline but its results are incomplete. Every task below
traces to one of these; report each as fixed, partly fixed or still open.

| Limitation in the current paper | Fix | Phase |
| --- | --- | --- |
| Coverage gains, no F1/AP gain over random selection | Utility term in selection, tuned on validation | 1-2 |
| Few minority TEST records (Ecoli4 4, Abalone19 6) | Datasets with >= 30 minority TEST records, 5 splits | 0, 3 |
| Only 3 KEEL datasets in the main study | 40 datasets: U2's 30 OpenML plus 10 new | 0, 3 |
| U2: no direct validity checks on synthetic samples | RC-QASyn quality gate applied to U2, UGO and SMOTE output | 2-3 |
| U2: no better than tuned no oversampling | Utility-aware selection over gated candidates | 2-3 |
| Repair tested only on the historical LLM stream | Fresh generation from 8 generators; repair rules for interpolated output (vehicle0) | 2-3 |
| B1-B3 at unequal budgets | All comparators at the same record budget | 3 |
| No human validity labels | Team labels a blinded sample; the agent never fills these | alongside 3 |
| Unbuilt stages: calibration, risk-aware controller, regenerate loop | Scope decided by the user before Gate 1 | - |

## Layout

```
study/v3/
  PLAN.md  STATUS.md      this plan; status updated every session
  protocol.json           declared settings; frozen (with SHA-256) at Gate 2
  sources.json            declared datasets: source, ID, version, role (dev | benchmark)
  budget.jsonl            one line per provider call batch: model, tokens, cost
  src/ or *.py            v3 code; reuse rcqasyn and addendum code by import, never edit it
  runs/   data/           gitignored: run outputs and fetched raw data
  report/                 committed compact reports and tables
```

## Fixed design (change only with user approval)

- **Datasets** (40 benchmark + dev):
  - Dev: the 9 Empirical v2/addendum v1 datasets. All method design and tuning happens here.
  - Benchmark, U2 core: U2's 30 OpenML datasets exactly as in its catalogue
    (`notebooks/portable_catalogue.json` in ml_ugo, IDs 1-32 excluding 10 and 26), kept
    as they are for comparability; datasets with < 30 minority TEST records are flagged.
  - Benchmark, untouched: 10 new datasets used by neither draft. Inclusion: binary or
    source-defined one-vs-rest; imbalance ratio >= 3; >= 30 minority TEST records at
    80/20; <= 60 features; open licence; not a re-binarization of an included table.
  - No merged-method metric on any benchmark TEST before Gate 2.
- **Splits**: 5 stratified 80/20 splits, seeds 13, 29, 43, 61, 79. Validation = 20% of
  TRAIN, stratified, for every tuning choice. TEST only for final evaluation.
- **Generators**: SMOTE-family pools (non-LLM); API (Batch API, 50% off): Claude Haiku
  5.5 (all benchmark datasets), Claude Sonnet 5.5 (3-4 datasets, as budget allows), one
  low-cost OpenAI model such as gpt-6-luna (all benchmark datasets; verify name and price
  on OpenAI's pricing page at Gate 0); no Opus. Local via Ollama, 4-bit, 8 GB GPU:
  Gemma 4 E4B (the Empirical v2 generator), Llama 3.1 8B, Qwen2.5 7B, Mistral 7B v0.3,
  Phi-3.5 mini. Exact versions pinned at Gate 0. Pool = 4 x budget per dataset/split.
  Same versioned prompt and TRAIN-only context for all; per-batch seeds; raw responses
  persisted before parsing.
- **API budget cap**: $5 Anthropic, $4 OpenAI, tracked per provider in `budget.jsonl`.
  Estimated full run at list prices with Batch: about $1.20 each for Haiku 5.5 and the
  OpenAI model; Sonnet 5.5 about $0.60 per dataset. The pilot replaces these estimates.
- **U2 code**: use ml_ugo (https://github.com/d3vd5k/ml_ugo) pinned at commit a6710ea,
  installed or vendored read-only under `study/v3/`; never modify it. UGO and U2 runs use
  the GPU, so schedule them apart from local LLM generation.
- **Comparators**: tuned no oversampling, class-weighted, ROS, SMOTE/SMOTENC,
  Borderline-SMOTE, ADASYN, SMOTE-Tomek, KMeansSMOTE, RWO; generators from the U2 draft:
  paper-derived UGO, U2 with FlowGMM gate; curators at equal budget: random, schema-random,
  current quality-coverage, CLLM-style, discriminator-realism, B2 at equal budget; merged
  method: U2/LLM/SMOTE candidates -> RC-QASyn quality gate -> utility-aware selection.
- **Utility-term candidates** (Phase 2): U2 anchor difficulty percentile x group stability
  (U2 eqs. 5-8); FlowGMM compatibility as a separate admission evidence column (never
  merged into the concern index); KNN-Shapley on validation; boundary score.
- **Classifiers**: U2's five: logistic regression, random forest, XGBoost, MLP, RBF SVM,
  with U2's hyperparameter search spaces.
- **Primary metric**: minority-class F1 on REAL TEST, decision threshold selected on
  validation (as in U2). Secondary: MCC, AP, minority recall, coverage, redundancy.
- **Statistics**: average ranks + Friedman; Wilcoxon signed-rank vs each comparator with
  Holm correction; median paired difference with bootstrap 95% interval (Demsar 2006).
- **Proposed success criterion** (final wording and size target fixed at Gate 2): median
  F1 gain of the merged method over tuned no oversampling and over U2 alone is positive with
  Holm-adjusted p < 0.05 across the 40 benchmark datasets, with no significant MCC loss
  against either. A miss is reported as found.

## Phases and gates

Each phase ends at a gate: write findings and proposal into `STATUS.md`, commit, stop.

### Phase 0 - Setup (week 1, Nov 2-8)
- [ ] Verify environment: Python 3.12 venv, `pip install -e '.[dev,research]'`, tests,
      ruff and pyright pass on a clean checkout (record the baseline failure set).
- [ ] Ollama reachable at its OpenAI-compatible endpoint; pull the five local models; one
      smoke generation each through the existing OpenAI-compatible adapter.
- [ ] Native Anthropic Messages adapter and an OpenAI adapter path, both with Batch API
      support, behind the existing provider gate, with token and cost accounting into
      `budget.jsonl` per provider; tests with recorded fixtures, no network in tests.
- [ ] Declared dataset fetcher: refuses anything not in `sources.json`; records URL,
      version, SHA-256; empty or failed download = unavailable.
- [ ] Declare U2's 30 OpenML datasets in `sources.json`; shortlist 10 new ones against the
      inclusion rules using metadata only (no
      modelling); propose the dev/benchmark split in `sources.json`.
- [ ] Draft `protocol.json`.
- **Gate 0**: user approves protocol draft, dataset shortlist, model list, API budget cap.

### Phase 1 - Diagnose (weeks 2-3, Nov 9-22), dev datasets only
- [ ] Carve validation splits; reproduce current QC vs random on validation.
- [ ] Ablate: minority quota (50% vs real ratio), budget size, classifier (add
      HistGradientBoosting), pool generator (SMOTE vs stored LLM stream where available).
- [ ] Measure an upper bound: how much an oracle selection on validation could gain.
- **Gate 1**: user picks which utility terms go forward, given the diagnosis.

### Phase 2 - Utility-aware selection (weeks 4-6, Nov 23-Dec 13), dev datasets only
- [ ] Implement candidate terms: boundary/borderline score; KNN-Shapley value on
      validation; CLLM-style confidence filter; combine with the existing quality gate.
- [ ] Repair for interpolated output: a declared, still-bounded rule for integer fields
      broken by SMOTE-style interpolation (the vehicle0 case: all 1,400 candidates broke
      integer declarations; the <=3-field rule rescued 6). Report how many it recovers and
      whether repaired records change utility; never widen the bound silently.
- [ ] Export a blinded labelling sample (fresh LLM candidates) for the team's human
      validity labels; the agent prepares files only and never fills label columns.
- [ ] Tune every hyperparameter on validation splits of dev datasets.
- [ ] Freeze: method, hyperparameters, primary metric, success criterion, benchmark list.
      Write them into `protocol.json`, record its SHA-256 and the commit in `STATUS.md`.
- **Gate 2**: user (and the professor) approve the frozen protocol. Only after this may
  any benchmark TEST metric be computed.

### Phase 3 - Benchmark runs (weeks 7-11, Dec 14-Jan 17)
- [ ] Pilot: 5 benchmark datasets x Haiku + one local model; measure tokens/record, cost,
      local throughput, parse failure rate. Extrapolate full-run cost into `STATUS.md`;
      stop if it exceeds 80% of the cap.
- [ ] Full generation, resumable, background; then curation and evaluation for every
      method x dataset x split x classifier. Every row reported, unavailable rows with reasons.
- **Gate 3**: all runs complete; row counts reconcile with the declared design.

### Phase 4 - Analysis (weeks 12-13, Jan 18-31)
- [ ] Declared tests only; tables and figures into `report/`; per-generator and
      per-dataset breakdowns; failure analysis.
- **Gate 4**: results review with the user and the professor.

### Phase 5 - Paper (weeks 14-16, Feb 1-21)
- [ ] Update the IEEE draft on a branch, from `report/` only; claims limited to declared
      tests; no state-of-the-art wording.

## Never

Tune on TEST; peek at benchmark TEST before Gate 2; rerun to get better numbers; drop
unfavourable rows; edit protected paths or historical artifacts; "improve" B1/B2/B3; fill
human-review columns; claim privacy, semantic validity or significance beyond the protocol.
