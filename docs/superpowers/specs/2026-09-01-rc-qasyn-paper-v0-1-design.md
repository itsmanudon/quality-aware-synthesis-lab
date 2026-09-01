# RC-QASyn PAPER v0.1 design

Date: 2026-09-01

## Purpose

Create the first serious, collaboratively editable manuscript draft for
**Risk-Calibrated Quality-Aware Synthetic Dataset Construction (RC-QASyn)**.
The draft will state what the repository currently supports, distinguish
development evidence from final results, and leave explicit boundaries around
unfinished human evaluation and M2+ research.

## Author and document status

- Use `Anonymous Author(s)` in the draft.
- Use a neutral `article` document class so a venue template can replace it
  later without rewriting section content.
- Label the abstract provisional and exclude P1 numbers from it.
- Treat the manuscript as PAPER v0.1, not as a completed study.

## Source-of-truth rules

Use evidence in this order:

1. committed experiment artifacts and manifests;
2. current source code and configurations;
3. current documentation;
4. verified literature notes;
5. primary publication pages or original papers for citation verification.

Do not silently reconcile disagreements. Record them in the evidence map and,
when material to interpretation, in the manuscript. Known issues to disclose
include the Ecoli4 P1 pool containing 201 parseable records against a requested
200, P1 run manifests recording `git_dirty=true`, same-model generation and B3
judging, and the M1.4 repeated-provider-seed confound in P0-v2.

The implementation workbook is not manuscript evidence in this pass because
the required read-only spreadsheet runtime is unavailable. No unsupported
parser will be substituted.

## Manuscript architecture

Keep `paper/main.tex` thin. Substantive prose belongs in modular section files:

- provisional abstract;
- substantial Introduction;
- substantial, thematically organized Related Work;
- mathematical Problem Formulation;
- conceptual Proposed Framework with implementation-status boundaries;
- implemented Experimental Methodology;
- development observations plus future-results placeholders;
- partial Discussion;
- ablation placeholders;
- living Limitations;
- conservative provisional Conclusion;
- Declarations and author-contribution placeholders.

Place reusable tables under `paper/tables/` and the framework diagram under
`paper/figures/`. Maintain claim, evidence, citation, and writing-status notes
under `paper/notes/`.

## Claim states

Every major claim must map to one of:

- `VERIFIED_IMPLEMENTATION`;
- `DEVELOPMENT_OBSERVATION`;
- `LITERATURE_SUPPORTED`;
- `PROPOSED`;
- `FINAL_RESULT_PENDING`.

Proposed RC-QASyn components must not be phrased as experimentally validated.
Development diagnostics must not become superiority, significance, or
state-of-the-art claims.

## Content design

### Introduction and questions

Motivate synthetic-data construction as a multi-level quality problem, then
separate individually acceptable records from their marginal contribution to
an evolving dataset. Introduce RQ1--RQ5 carefully; mark RQ3--RQ5 as dependent on
future M2+ implementation and final evaluation.

### Related Work

Organize by theme rather than paper: tabular generators, LLM synthetic data,
quality evaluation, LLM critics, calibration/risk, refinement/repair, and the
research gap. Verify every cited reference against a primary publication
record. Placeholder literature notes are not evidence and belong in the
citation TODO ledger if still relevant.

### Formulation and framework

Define real training data, specification, generation condition, TRAIN-derived
context, candidate records, and the evolving accepted synthetic dataset.
Keep record quality, record risk, evaluator uncertainty, and dataset marginal
contribution separate. Represent evidence with explicit scope, dimension,
verdict or score, uncertainty or confidence, and provenance. Define the future
controller's actions without claiming that the controller exists.

Use a TikZ pipeline figure with status-aware styling: implemented M1 elements,
current M1.5 diagnostics, and dashed proposed M2+ elements.

### Experimental methodology

Describe the implemented registry, deterministic stratified splits, TRAIN-only
profiles and examples, untouched REAL TEST split, versioned prompts, shared
candidate pool, deterministic cryptographic seed derivation, per-batch provider
seeds, baseline definitions, metrics, diagnostics, provenance, and human-review
protocol.

Use exact committed values for the three development datasets and P1 protocol.
Keep the planned benchmark in a separate, explicitly future table.

### Results and interpretation

Only Results 6.1 may contain current observations. Source it from:

- `artifacts/reports/p1/p0v3_vs_p1_diversity.json`;
- `artifacts/reports/p1/p1_copying_diagnostics.json`;
- `artifacts/reports/p1/p1_b1_b2_b3.json`;
- `artifacts/reports/p1/p1_b2_b3_disagreements_summary.json`;
- `artifacts/reports/p1/p1_support_distance_summary.json`;
- `artifacts/reports/p1/p1_human_review_manifest.json`.

Report only cautious development diagnostics: corrected-protocol pool sizes,
duplicate and reference-match behavior, absence of exact matches to unshown
TRAIN records, B2/B3 disagreement, and human-audit sampling status. Do not use
pilot utility values as final evidence; some require resolution of undefined
TSTR entries and the Ecoli4 over-generation anomaly.

Human results, M2+ comparisons, final benchmarks, statistical tests,
ablations, repair comparisons, and final conclusions remain explicit
placeholders using `--` or `TODO`, never zero-valued stand-ins.

## Citation policy

Verify title, author order, year, publication status, venue, and persistent
identifier where available. Prefer official proceedings, publisher, DOI, and
arXiv records. Use stable BibTeX keys and omit unverified metadata rather than
fabricating it. Add `% TODO[CITATION]` at unsupported statements and track the
issue in `paper/notes/citation_todo.md`.

## Collaboration design

- Keep authors out of `main.tex` except for anonymous draft metadata.
- Assign prose ownership by section in `paper/README.md`.
- Recommend branches `paper/introduction`, `paper/related-work`, and
  `paper/methodology`.
- Avoid concurrent rewriting of `main.tex`.
- Keep all changes uncommitted for user review.

## Validation

Document `latexmk -pdf main.tex` as the reproducible build command and provide
a small `latexmkrc`. This machine has no LaTeX executable, so compilation cannot
be claimed. Perform static validation of included files, citation keys, labels,
TODO markers, and obvious syntax hazards. Inspect `git diff --check`, the full
diff summary, and Git status. Do not run unrelated Python quality gates or
expensive experiments.

## Non-goals

- Do not implement M2 validators, calibration, evidence fusion, control,
  repair, regeneration, or dataset optimization.
- Do not rerun experiments or alter scientific artifacts.
- Do not fabricate results, citations, statistical claims, or final benchmark
  coverage.
- Do not commit or push manuscript changes in this task.
