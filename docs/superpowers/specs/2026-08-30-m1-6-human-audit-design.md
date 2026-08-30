# M1.6 Human Ground-Truth Audit Analysis Design

## Purpose

M1.6 adds measurement-only infrastructure for comparing external human validity
annotations with the existing B2 deterministic validator, B3 single-judge critic,
copying diagnostics, and TRAIN-support distances. It must preserve the current P1
review sample and must never infer, populate, or rewrite human annotations.

The operational definition is:

> A record is human-valid if it conforms to known schema/domain semantics and
> represents a plausible member of the requested target class.

Dataset redundancy does not by itself make a record invalid. Consequently,
`human_valid=true` may coexist with `human_failure_type=DUPLICATE`.

## Scope and constraints

The milestone is restricted to audit validation, descriptive analysis, and report
generation. It does not add or alter validators, judge thresholds, calibration,
repair, generation, privacy claims, or acceptance decisions. It does not regenerate
P1 and does not call Ollama or any other network service.

The existing file `artifacts/reports/p1/p1_human_review.csv` remains the annotation
source. The implementation reads it but never edits it. Missing human labels remain
missing; an incomplete file produces an explicit incomplete-analysis status rather
than inferred results.

## Architecture

Create a focused `rcqasyn.experiments.human_audit` module. It owns immutable review
loading, validation, taxonomy parsing, agreement calculations, metric calculations,
and report assembly. Its public functions accept paths or parsed rows and return
plain dictionaries and row lists, keeping calculations independently testable and
free of CLI concerns.

Add a `human-review` Typer command group:

- `rcqasyn human-review status <csv>` reads only the supplied annotation file and
  reports row, label, validity, taxonomy, dataset, and requested-class counts. It
  validates required columns, human-label syntax, unique canonical hashes, diagnostic
  coverage, and provider lineage. It never infers labels.
- `rcqasyn human-review analyze <csv>` validates annotations, joins existing B2
  evidence where required, and writes the M1.6 report bundle. If any primary
  `human_valid` labels are missing or invalid, it exits without writing evaluation
  results and reports the incomplete state.

The analyzer locates detailed B2 evidence beneath
`artifacts/runs/<run_id>/baselines/b2/evidence.jsonl`, keyed by `run_id` and
`record_id`. This is necessary because the P1 review CSV contains generic B2 decision
reasons. Missing or ambiguous evidence is reported; it is never guessed from the
candidate, B3, copying flags, or distances.

## Annotation model

`human_valid` accepts explicit case-insensitive `true` or `false`. Blank means
unlabelled. Other values are invalid annotations and are reported.

`human_failure_type` is multi-label. Semicolon is the documented canonical delimiter;
for compatibility, existing comma and vertical-bar separators are parsed without
rewriting the source. Tokens are trimmed, retained in source order, and validated
against the taxonomy. Unknown labels appear in validation output and are never
dropped. Repeated labels count once per row in taxonomy summaries.

Record-level categories are:

- `SCHEMA`
- `MISSING_FIELD`
- `INVALID_CATEGORY`
- `TARGET_MISMATCH`
- `NUMERIC_OUTLIER`
- `LOGICAL_INCONSISTENCY`
- `STATISTICAL_IMPLAUSIBILITY`
- `SEMANTIC_IMPLAUSIBILITY`
- `OTHER`

`DUPLICATE` is the sole dataset-level category. Legacy `NONE` and `PARSE` remain
recognized for compatibility; `PARSE` is reported separately as a legacy category
rather than silently mapped to a record-level category.

## Multiple annotators and adjudication

The analyze command accepts repeatable `--annotator ID=PATH` inputs. Agreement is
calculated for each supplied annotator pair only on rows where both have explicit
`human_valid` labels, matched by the stable identity tuple `run_id`, `record_id`, and
`canonical_hash`. Reports include overlap count, raw agreement, and Cohen's kappa.
Partial overlap is valid. Zero-overlap and single-class cases return an explicit
not-computable reason rather than a fabricated statistic.

An optional `--adjudicated PATH` input is an explicit final-label source for analysis.
It is validated and used as supplied. The implementation never merges annotator
disagreements or synthesizes adjudicated labels.

## B2 record-validity view

The positive evaluation class is `human_invalid`.

B2 rejection evidence is classified into structural/domain, dataset redundancy, or
other/ambiguous categories. A rejection supported only by duplicate/redundancy
evidence is treated as an acceptance in the B2 record-validity view. A rejection with
any structural/domain evidence remains a rejection even if duplicate evidence is also
present. Ambiguous or missing evidence is counted and exposed separately; it is not
reclassified using human labels.

For evaluable rows, report TP, FP, TN, FN, precision, recall, F1, specificity,
balanced accuracy, false-accept rate, and false-reject rate. Zero-denominator metrics
are `null` with supporting counts retained.

## B3 evaluation and score semantics

B3 rejection predicts `human_invalid`. Report the same confusion metrics as B2.

The existing B3 score is an uncalibrated validity/quality score used with a static
0.7 acceptance threshold, not a documented probability of validity or invalidity.
For continuous discrimination, use `1 - b3_score` as the diagnostic predictor of
`human_invalid`. Emit ROC-AUC only when both human classes exist and PR-AUC for
human-invalid detection when defined. Do not emit a Brier score because direct
probability semantics are not established. Do not tune or recommend a threshold.

Score summaries include min, p10, p25, median, mean, p75, p90, and max split by human
validity, dataset, and requested class. Histogram-ready data consists of deterministic
fixed-width bins spanning `[0, 1]`, with bin edges and counts for each split.

## Comparative analyses

The B2/B3 disagreement CSV contains the four decision cells and, within each cell,
human-valid and human-invalid counts. B2 rejects are additionally split into
redundancy-only, structural/domain, and ambiguous classifications.

Copying analysis reports counts and `P(human invalid | flag)` independently for:

- `exact_synthetic_duplicate`
- `exact_reference_match`
- `exact_nonreference_train_match`

Reference-copy analysis reports valid and invalid counts, duplicate-category counts,
and additional non-duplicate human defect counts. Reports describe copying as a
diversity or dataset-quality diagnostic, never as privacy leakage.

Support-distance analysis covers `nearest_train_distance`,
`nearest_same_class_train_distance`, and `nearest_other_class_train_distance` when
present. For human-valid and human-invalid groups it reports count, median, IQR, p10,
and p90. It also reports the rank-biserial effect derived from the Mann-Whitney U
statistic and optional ROC-AUC for human-invalid discrimination when both classes and
sufficient non-missing values exist. These remain diagnostics; no thresholds or
validators are produced.

Dataset/class analysis reports labelled counts, invalid counts, and invalid rates by
dataset and requested class. Failure-taxonomy reports separate global and per-dataset
record-level, dataset-level, legacy, and unknown-label counts. A row may contribute to
multiple categories.

## Outputs and traceability

Completed analysis writes beneath `artifacts/reports/human_audit/`:

- `human_summary.json`
- `b2_human_confusion.json`
- `b3_human_confusion.json`
- `b3_score_distribution.json`
- `b2_b3_human_disagreement.csv`
- `copying_vs_human.json`
- `support_distance_vs_human.json`
- `failure_taxonomy.json`
- `dataset_class_human_rates.json`
- `human_audit_summary.md`

Every JSON report and the Markdown summary include the schema version, source path,
SHA-256 of each annotation source, and SHA-256 values for joined B2 evidence files.
The disagreement CSV includes source-hash columns so it remains independently
traceable. Output ordering and serialization are deterministic.

The writer refuses to overwrite an incompatible output directory by default. A
repeat analysis from identical source hashes may replace its own generated files;
changed source hashes require an explicit `--overwrite` option.

## Error handling

Status treats incomplete labels as expected state and exits successfully after
reporting counts. It exits unsuccessfully for unreadable CSVs, missing required
columns, duplicate row identities, duplicate canonical hashes in the P1 review file,
invalid boolean labels, and malformed annotator specifications.

Analyze exits without evaluation artifacts when primary annotations are incomplete,
taxonomy labels are unknown, required numeric fields are malformed, or B2 evidence
needed to classify a rejection is unavailable or ambiguous. Diagnostics absent from
the source schema are reported as unavailable rather than treated as zero.

## Testing and verification

Network-free tests use small temporary CSV and JSONL fixtures. Tests cover multi-label
parsing and unknown retention, annotation completeness, blank labels, duplicate-only
B2 treatment, B2 and B3 confusion metrics, score distributions, support-distance
summaries and effects, partial-overlap annotator agreement, explicit adjudication,
traceable output generation, and CLI status/analyze behavior.

Implementation follows red-green-refactor cycles. Final verification runs:

- `pytest -q`
- `ruff check .`
- `pyright`
- `pytest --cov=rcqasyn`
- `git diff --check`

No P1 generation command or model provider is invoked during development or tests.
