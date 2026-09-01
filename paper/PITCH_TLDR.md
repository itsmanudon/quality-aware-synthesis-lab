# RC-QASyn — Professor Pitch TL;DR

## 1. What are we trying to solve?

Synthetic-data systems are often evaluated as generators: can they produce a
plausible row? Our concern is the next question: do the accepted rows form a
useful dataset? A generator can emit records that look valid individually but
repeat the same examples, overuse prompt references, cover only a narrow part
of the target distribution, or provide weak downstream utility. RC-QASyn
studies how to construct the dataset using multiple kinds of evidence rather
than relying on generation plus one global filter.

## 2. One-line thesis

> **Generating valid synthetic records is not the same as constructing a
> high-quality synthetic dataset.**

RC-QASyn treats the second problem explicitly.

## 3. Key conceptual distinction

| Record quality | Dataset quality |
| --- | --- |
| Correct schema and types | Exact and near duplicates |
| Requested target is consistent | Prompt-reference copying |
| Locally supported values | Support and class coverage |
| Logical or semantic plausibility | Distributional fidelity and utility |

An intuitive example: a valid minority-class record repeated fifty times may
remain a valid record every time, while adding almost no new support to the
synthetic dataset. The validity judgment and the marginal dataset value must
therefore remain separate.

## 4. What have we actually built?

The repository currently contains:

- a versioned Python experiment pipeline;
- deterministic stratified TRAIN/TEST splits;
- TRAIN-only profiles and reference examples for generation;
- reproducible generator calls with unique deterministic per-batch seeds;
- a persisted candidate pool shared by B1, B2, and B3;
- intrinsic fidelity, diversity, class-conditional, and correlation metrics;
- TRTR and TSTR evaluation with logistic regression and random forest;
- exact-copy and TRAIN-support diagnostics;
- blinded human-review export, import, agreement, and adjudication
  infrastructure; and
- versioned prompts, configs, manifests, traces, and compact reports.

The current test suite passes **98 tests with 86% line coverage**. That is
engineering evidence that the pipeline is exercised and reproducible; it is
not evidence that the research hypothesis is correct.

## 5. Baselines

```text
                  SAME RAW POOL
                 /      |      \
               B1       B2      B3
```

**B1 — Raw generation:** accepts every parseable candidate.

**B2 — Deterministic filtering:** applies schema, domain, missing-value,
target-condition, and observed-range checks, then rejects repeated canonical
candidates after the first occurrence.

**B3 — Single LLM judge:** uses one static threshold and one uncalibrated
record-wise judge. In P1 the judge and generator use the same model, so their
errors may be correlated.

Sharing one persisted pool makes the comparison paired: every policy sees the
same candidate identities instead of receiving an easier or harder generation
sample.

## 6. What did the pilot reveal?

These are **development observations from one corrected P1 run per dataset**,
not final or statistically significant results.

| Dataset | P1 duplicate rate | Reference-copy rate |
| --- | ---: | ---: |
| page-blocks0 | 9.5% | 1.0% |
| Ecoli4 | 10.45% | 10.95% |
| Abalone19 | 28.5% | 24.5% |

- Duplication remained after correcting the seed confound.
- The duplicate rate was higher at the larger P1 request than at P0-v3 for
  all three development datasets; one run at each scale cannot establish a
  trend.
- Exact prompt-reference copying explained much of the duplication,
  especially for Abalone19.
- P1 contained zero exact matches to TRAIN records that were not shown as
  prompt references. This is a copying observation, not a privacy guarantee.
- The current same-model, record-wise B3 accepted 600 of 601 candidates and
  therefore exhibited little discrimination in this pilot. This does not show
  that LLM judges generally fail.
- B2 rejected redundancy and also flagged a small structural/domain tail: the
  disagreement summary classifies 5 Abalone19, 5 Ecoli4, and 6 page-blocks0
  cases in that category.
- Pilot downstream utility is nontrivial and unstable: there is one split per
  dataset, tiny minority TEST counts, and undefined logistic-regression TSTR
  entries in the committed reports.

## 7. What was the 75% duplicate issue?

Initial same-class generation batches accidentally reused one provider seed,
so the provider replayed raw batches. This created an artificial 75% duplicate
rate on all three datasets. We diagnosed the confound, derived a unique
deterministic seed from the root seed, dataset, requested class, and batch
index, and reran P0-v3/P1 under the corrected protocol. We do not treat the
P0-v2 result as model collapse or generator-quality evidence. The disclosure
is an example of experimental hygiene.

## 8. Why human annotation?

B2 and B3 make different decisions, but neither policy is ground truth. The
next gating evidence is a blinded audit of 120 unique-prioritized records:

- Reviewer A labels all 120 records.
- Reviewer B labels a deterministic 40-record overlap.

Reviewers do not see B2/B3 decisions, judge scores, duplicate or reference
flags, nearest-neighbour distances, or provider information. Human validity is
record-level: redundancy alone does not make an otherwise plausible record
invalid. Raw agreement and Cohen's kappa will be reported; disagreements will
be adjudicated manually. These labels will benchmark automated evidence before
the M2 design is frozen.

## 9. Proposed direction

```text
Specification
      ↓
Generation
      ↓
Record Evidence + Dataset Evidence
      ↓
Calibration / Fusion
      ↓
Risk-Aware Decision
      ↓
Accept / Repair / Regenerate / Reject
      ↓
Dataset Contribution Control
      ↓
Audit + Utility
```

**Implemented now:** generation, paired baselines, diagnostics, persisted
artifacts, and human-audit infrastructure.

**Next:** human-grounded record evidence and dataset evidence critics.

**Later core stage:** calibration, fusion, and decision control.

**Extensions:** localized repair, privacy/fairness or domain-factual modules,
and richer dataset optimization. They can be cut without losing the core
paper question.

## 10. What is potentially novel?

The potential contribution is the combination of:

1. separating record validity from dataset marginal value;
2. representing heterogeneous evidence with explicit scope and provenance;
3. calibrating evaluator evidence against human judgments;
4. using that evidence for risk-aware sequential acceptance decisions; and
5. retaining dataset-level marginal contribution rather than treating quality
   as a fixed per-record score.

Novelty is a research hypothesis to validate, not something we are claiming as
established yet.

## 11. What is unfinished?

- completed human annotation and adjudication;
- M2 record- and dataset-evidence validators;
- calibration and evidence fusion;
- the risk-aware controller;
- localized repair;
- a broader final benchmark;
- repeated generation seeds and real-data splits;
- statistical tests and uncertainty intervals; and
- component ablations.

## 12. Next milestone

```text
M1.6 Human Ground Truth
           ↓
M2A Record Evidence
     +
     Dataset Evidence
           ↓
M3 Calibration / Fusion
           ↓
M4 Decision Control
           ↓
Later repair / optimization if justified
```

## 13. 60-second pitch

We are studying a gap between generating plausible synthetic records and
constructing a useful synthetic dataset. A row can be structurally valid and
belong to the requested class, yet add almost nothing because it repeats a
prompt example or occupies support already covered. RC-QASyn separates those
two questions: record validity and dataset-level marginal value. So far, we
have built a reproducible pipeline with leakage-safe splits, deterministic
generation, three paired baselines, intrinsic and downstream metrics, copying
and support diagnostics, and a blinded human-audit workflow. In corrected P1
development runs, duplicate rates ranged from 9.5% to 28.5%, reference copying
was especially high for Abalone19, and the same-model B3 judge accepted 600 of
601 candidates. These are pilot observations, not final results. Our immediate
next step is to complete human annotation and use it to identify where rules
and the LLM judge actually fail. That evidence will freeze the M2 design for
scoped record and dataset evidence, followed by calibration and risk-aware
decision making.

## 14. 3-minute pitch

Our starting point is that synthetic-data generation and synthetic-dataset
construction are not the same problem. Most generation pipelines ask whether
a model can produce plausible records and then either accept everything,
apply rules, or ask one critic. But a collection of individually plausible
records can still be a poor dataset. It may repeat the same minority example,
copy the few references shown in the prompt, concentrate in a narrow support
region, distort class-conditional structure, or fail to support a downstream
classifier.

RC-QASyn makes the distinction explicit. Record evidence asks whether one
candidate has the right schema, target, support, and logical or semantic
plausibility. Dataset evidence asks what that candidate contributes relative
to the records already accepted: novelty, coverage, fidelity, and eventually
utility. We do not want to collapse these immediately into one quality score.
The core research direction is to preserve their scope, calibrate heterogeneous
evaluator evidence against human judgments, and use the calibrated evidence
for risk-aware acceptance decisions.

We have not built that novel decision layer yet. What we do have is the
experimental foundation needed to test it honestly: three real imbalanced
development datasets, deterministic stratified splits, TRAIN-only generation
context, versioned prompts, unique reproducible provider seeds, a shared raw
candidate pool, and three paired baselines. B1 accepts every parseable row. B2
uses deterministic checks and duplicate handling. B3 is one uncalibrated,
same-model LLM judge. We also persist intrinsic metrics, TRTR/TSTR utility,
copying categories, support distances, and full provenance.

The corrected P1 runs provide useful development clues. Duplicate rates were
9.5% on page-blocks0, 10.45% on Ecoli4, and 28.5% on Abalone19. Exact reference
copying was 1.0%, 10.95%, and 24.5%, respectively, while exact matches to
unshown TRAIN records were zero. B3 accepted 600 of 601 candidates, whereas B2
rejected duplicates and a small structural/domain tail. These observations do
not tell us which critic is correct, because duplicate-only rejection is a
dataset decision rather than a human record-validity judgment.

That is why human annotation is the next gate. Reviewer A labels 120
unique-prioritized records, and Reviewer B independently labels a blinded
40-record overlap. They do not see any model decision, copying flag, distance,
or provider metadata. After agreement and manual adjudication, we will measure
which failure types B2 and B3 detect or miss. Those results will determine the
M2 record- and dataset-evidence design. Calibration and decision control come
after that. Repair, privacy/fairness modules, and richer optimization remain
extensions if the core paper would otherwise become too broad.

## 15. Numbers to remember

1. **3** real development datasets: page-blocks0, Ecoli4, and Abalone19.
2. **601** persisted P1 candidates from **600 requested**; Ecoli4 produced one
   extra record, which is disclosed rather than discarded.
3. Duplicate rates: **9.5% / 10.45% / 28.5%**.
4. Reference-copy rates: **1.0% / 10.95% / 24.5%**.
5. Exact matches to unshown TRAIN records: **0** in all three P1 pools.
6. B3 acceptance: **600/601** candidates.
7. Human-audit sample: **120** unique-prioritized records.
8. Double-reviewed blinded overlap: **40** records.

## 16. Professor questions

### 1. What exactly is the research contribution?

The current contribution is a precise record-versus-dataset formulation and a
reproducible human-audited evaluation framework. The proposed method contribution
is calibrated, scope-aware evidence for risk-aware sequential decisions; it
still requires implementation and validation.

### 2. Isn't this just filtering synthetic data?

Filtering makes a fixed per-record accept/reject decision. Our core question
also keeps dataset-level evidence conditional on the evolving accepted set, so
two individually valid records can have different marginal value.

### 3. Why use an LLM at all?

Rules cover declared schema and domain constraints well but may not capture
cross-field plausibility or task-specific semantics. An LLM is one candidate
evidence source, not the authority or the contribution by itself.

### 4. Why not just use deterministic validation?

Deterministic validation is precise where complete rules exist. It cannot
guarantee that all logical, statistical, or semantic defects have been
specified, so we test where additional evidence helps and where it does not.

### 5. Why not just ask another LLM judge?

One judge can be uncalibrated and correlated with the generator. We want to
measure it against blinded human labels and combine it only with independently
traceable evidence whose reliability is estimated.

### 6. How do you define quality?

We do not define it as one universal scalar. We separate desired properties
(quality), consequences of acceptance (risk), evaluator confidence or
disagreement (uncertainty), and marginal dataset contribution.

### 7. How is dataset quality different from record quality?

Record quality concerns one row. Dataset quality concerns relationships among
rows and the real-data task: redundancy, coverage, fidelity, subgroup
representation, and utility.

### 8. Why are you using imbalanced datasets?

They stress the exact setting where synthetic augmentation is attractive and
where repeating a few minority examples can look successful while adding
little support. They are development stress tests, not yet the final benchmark.

### 9. Why these three datasets?

They provide moderate, severe, and extreme imbalance, small- and larger-sample
settings, and both numerical-only and mixed-type data. They were chosen for
pipeline development, not to claim broad generalization.

### 10. What is TRTR/TSTR?

TRTR trains on REAL TRAIN and evaluates on untouched REAL TEST. TSTR trains on
accepted synthetic data and evaluates on that same REAL TEST. TRTR is a
reference condition; TSTR probes downstream usefulness.

### 11. What happened with the 75% duplicate result?

Same-class batches reused a provider seed, causing raw batch replay. We fixed
the derivation, added a uniqueness guard, reran the pilots, disclosed the
confound, and excluded P0-v2 diversity from generator-quality interpretation.

### 12. How will human labels be used?

They will benchmark B2/B3 record-validity decisions by failure type, measure
agreement and adjudicated outcomes, and reveal which M2 evidence sources are
needed. Automated labels will never substitute for missing human labels.

### 13. How will you prove calibration works?

We will separate calibration and evaluation records, predefine the target and
loss, compare reliability and selective-risk behavior against raw scores, and
report uncertainty. We will claim only the guarantees supported by the chosen
method and its assumptions.

### 14. Isn't the project too large?

It is large as a research program, so the paper core is narrower: record
evidence, dataset evidence, and calibrated decision making. Repair,
privacy/fairness modules, and richer optimization are extensions.

### 15. What will you cut if the full architecture becomes too broad?

We will keep the human-grounded record/dataset evidence comparison and
calibrated decision layer. Localized repair goes first, followed by specialized
privacy/fairness modules and sophisticated dataset optimization if they are not
required for the core result.

## 17. What NOT to claim

- “RC-QASyn is already better than baselines.”
- “We achieved state of the art.”
- “Our results are statistically significant.”
- “LLM judges do not work.”
- “No TRAIN copying means privacy is guaranteed.”
- “The full risk controller is implemented.”
- “Repair has been shown to improve efficiency.”
- “The final benchmark is complete.”

## 18. If professor asks “What do you have right now?”

We have a reproducible experimental pipeline, three paired baselines, three
real development datasets, corrected local-LLM experiments, intrinsic and
downstream diagnostics, copying and support analysis, and a blinded human-audit
protocol. The novel calibrated decision layer is the next phase.

## 19. If professor asks “What will be ready next?”

Completed human labels and adjudication will produce a human-grounded B2/B3
critic benchmark. We will use the observed failure modes to freeze the M2
record- and dataset-evidence design rather than choosing validators in advance
of the ground truth.
