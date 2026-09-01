# RC-QASyn — One-Page Professor Brief

## Problem

Synthetic generation can produce plausible records without constructing a
good dataset. Accepted rows may be valid individually but repeat prompt
examples, cover little new support, distort the distribution, or provide weak
downstream utility.

## Core insight

> **Generating valid synthetic records is not the same as constructing a
> high-quality synthetic dataset.**

Record evidence concerns schema, target consistency, local support, and
logical or semantic plausibility. Dataset evidence concerns redundancy,
reference copying, coverage, fidelity, and utility. A valid minority record
repeated fifty times can remain valid while adding almost no new dataset
support.

## What is built

- Deterministic stratified TRAIN/TEST splits and TRAIN-only generation context.
- Versioned prompts/configs and unique deterministic per-batch provider seeds.
- One persisted candidate pool shared by B1 raw generation, B2 deterministic
  filtering, and B3 one uncalibrated same-model LLM judge.
- Intrinsic metrics, TRTR/TSTR, exact-copy diagnostics, support diagnostics,
  and reproducible manifests/traces.
- Blinded human-audit infrastructure: 120 records for Reviewer A and a
  40-record Reviewer B overlap.
- Engineering check: 98 tests pass with 86% coverage; this is not research
  evidence.

## Three strongest pilot findings

These are descriptive observations from one corrected P1 run per development
dataset, not final results.

1. Exact duplicate rates were **9.5%** (page-blocks0), **10.45%** (Ecoli4), and
   **28.5%** (Abalone19).
2. Exact reference-copy rates were **1.0%**, **10.95%**, and **24.5%**,
   respectively; exact matches to unshown TRAIN records were zero.
3. The current same-model B3 accepted **600/601** candidates, while B2 also
   identified redundancy and a small structural/domain tail. Human labels are
   needed before calling either critic more correct.

The earlier 75% duplicate result was a provider-seed replay confound. It was
diagnosed, corrected with unique deterministic batch seeds, and excluded from
generator-quality interpretation.

## Proposed pipeline

```text
Specification → Generation
              → Record Evidence + Dataset Evidence
              → Calibration / Fusion
              → Risk-Aware Decision
              → Audit + Utility
```

The core paper focus is record evidence, dataset evidence, and calibrated
decision making. Localized repair, privacy/fairness or factual modules, and
richer dataset optimization are extensions, not current capabilities.

## Next step

Complete and adjudicate the blinded human audit, benchmark B2/B3 against human
record validity, and freeze M2 evidence design from the observed failure modes.
RC-QASyn has not yet been shown to outperform the baselines, and the full
risk-aware controller is not implemented.
