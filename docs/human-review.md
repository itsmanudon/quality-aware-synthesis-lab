# Human review and ground-truth audit (M1.5-M1.6)

The human-review CSVs (`human_review.csv` per run; `p1_human_review.csv` cross-dataset)
are the audit input that will determine M2 design. Automated B1/B2/B3 decisions and human
adjudication are kept in separate columns. The coding agent never fills a human column and
never infers a human validity label from a B2/B3 decision.

## Columns the annotator fills

| column | meaning |
| --- | --- |
| `human_valid` | `true` / `false` — does the record conform to known schema/domain semantics and represent a plausible member of the requested target class |
| `human_failure_type` | one or more taxonomy labels (below); multi-label allowed, separate with `\|`, `;` or `,` |
| `human_severity` | free scale, e.g. `low` / `medium` / `high` / `critical` |
| `human_affected_fields` | comma-separated field names |
| `human_notes` | free text |

## Failure taxonomy

`NONE`, `PARSE`, `SCHEMA`, `MISSING_FIELD`, `INVALID_CATEGORY`, `TARGET_MISMATCH`,
`NUMERIC_OUTLIER`, `LOGICAL_INCONSISTENCY`, `STATISTICAL_IMPLAUSIBILITY`, `DUPLICATE`,
`SEMANTIC_IMPLAUSIBILITY`, `OTHER`.

Multi-label is expected. Use semicolon (`;`) as the canonical delimiter, for example
`NUMERIC_OUTLIER;LOGICAL_INCONSISTENCY`. The audit reader also accepts existing `|`
and `,` delimiters without rewriting the source. Unknown taxonomy labels are reported
verbatim and are never silently dropped.

## Record validity vs dataset-level redundancy

`DUPLICATE` is primarily a **dataset-level redundancy** signal, not by itself a statement
that the record is invalid. An exact duplicate of an otherwise well-formed, in-domain,
correctly-conditioned record is still a structurally valid record; its problem is that it
adds no information to the synthetic dataset. Annotators should therefore:

- set `human_valid=true` for a structurally sound exact duplicate and add `DUPLICATE`
  to `human_failure_type` to record the redundancy, and
- reserve `human_valid=false` for records with an actual structural, domain, target,
  logical, or plausibility defect.

Reports separate **record structural validity** from **duplicate / redundancy** for the
same reason. `exact_reference_match` and `exact_nonreference_train_match` are copying
diagnostics, not privacy claims. TRAIN-support nearest-neighbour distances in the review
sample are exploratory context only — they carry no threshold and are not validity
probabilities.

## Blinded annotation protocol

Human record-validity annotation must use the blinded exports, not the master review
CSV. The master contains automated evaluator and diagnostic data that could influence
judgment.

For blinded review, **human-valid** means:

> The record conforms to known schema/domain semantics and represents a plausible
> member of the requested target class, independently of its redundancy within the
> synthetic dataset.

Reviewers must not classify dataset redundancy, duplication, reference copying, or
TRAIN copying during blinded record-validity annotation. Those automated diagnostics
are joined only after labels are imported. In particular, do not use `DUPLICATE` in a
blinded reviewer file even though it remains part of the master taxonomy for backward
compatibility.

Blinded `human_failure_type` values are limited to these record-level labels:

`NONE`, `SCHEMA`, `MISSING_FIELD`, `INVALID_CATEGORY`, `TARGET_MISMATCH`,
`NUMERIC_OUTLIER`, `LOGICAL_INCONSISTENCY`, `STATISTICAL_IMPLAUSIBILITY`,
`SEMANTIC_IMPLAUSIBILITY`, `OTHER`.

Use `NONE` for a human-valid record without a record-level defect. Semicolon remains
the canonical delimiter for multiple record-level defects. A row with all five human
fields blank is unlabelled. Once any human field is entered, both `human_valid` and
`human_failure_type` are required; severity, affected fields, and notes remain
optional.

Create the reviewer files from the unchanged master:

```text
rcqasyn human-review export-blind artifacts/reports/p1/p1_human_review.csv
```

The default output directory is `artifacts/reports/human_audit/blinded/`:

- `reviewer_a_blind.csv` contains all 120 records.
- `reviewer_b_blind.csv` contains the deterministic 40-record overlap.
- `reviewer_a_blind.manifest.json` and `reviewer_b_blind.manifest.json` contain
  internal identity and generated-record integrity hashes.

Give reviewers only their CSV. Keep the manifest internal: it exists for import and
tamper detection, not annotation. Reviewer CSVs contain only annotation identity,
record identity, dataset, requested class, serialized generated record, and human
fields. They contain no B1/B2/B3 decisions, scores, reasons, copying flags, distances,
provider lineage, or automatic verdicts.

After a reviewer returns a file, validate and import it to a new master-format file:

```text
rcqasyn human-review import-blind \
  artifacts/reports/p1/p1_human_review.csv \
  artifacts/reports/human_audit/blinded/reviewer_a_blind.csv \
  --manifest artifacts/reports/human_audit/blinded/reviewer_a_blind.manifest.json \
  --annotator-id reviewer_a \
  --output artifacts/reports/human_audit/reviewer_a_imported.csv
```

Import never modifies the master. It rejects missing, extra, or duplicate identities;
invalid booleans or taxonomy; partial annotations; modified dataset/class identity;
and any edited generated record. Unlabelled rows remain blank and are never inferred.
Import reviewer A and reviewer B separately. Existing agreement analysis calculates
raw agreement and Cohen's kappa only on their explicitly labelled overlap; it does not
resolve disagreements.

## Annotation status

Use the status command before analysis:

```text
rcqasyn human-review status artifacts/reports/p1/p1_human_review.csv
```

It reports row, labelled/unlabelled, valid/invalid, taxonomy, dataset, requested-class,
role, B2, and B3 counts. It also validates unique identities and canonical hashes,
copying flags, support-distance coverage, and provider lineage. Blank labels are an
expected state and are never inferred.

## M1.6 analysis

After every primary `human_valid` value has been supplied and all taxonomy labels are
known, run:

```text
rcqasyn human-review analyze artifacts/reports/p1/p1_human_review.csv
```

Incomplete annotations cause a clear error and no evaluation outputs. The command
reads existing per-run B2 evidence to distinguish structural/domain rejects from
redundancy-only rejects. Duplicate-only B2 rejection is treated as acceptance in the
record-validity view; it is not counted as successful detection of a human-invalid
record.

Optional annotation inputs use stable annotator IDs:

```text
rcqasyn human-review analyze artifacts/reports/p1/p1_human_review.csv \
  --annotator reviewer_b=path/to/reviewer_b.csv \
  --adjudicated path/to/adjudicated.csv
```

Pairwise raw agreement and Cohen's kappa use only overlapping rows with explicit
`human_valid` labels. Disagreements are never merged automatically. An adjudicated
file supplies only the human columns; machine decisions and diagnostics remain bound
to the primary review file.

Completed analysis writes these traceable files to
`artifacts/reports/human_audit/`:

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

Reports include SHA-256 hashes for annotation and joined B2 evidence sources. B3 score
analysis is uncalibrated and threshold-free; it does not calculate a Brier score.
Support distances remain diagnostic-only and do not become validators.

## Sharing completed annotations

Completed reviewer CSVs, adjudicated CSVs, agreement results, and human-audit summary
reports are collaboration-critical. Commit them when they are small and contain no
sensitive personal data. Keep reviewer identity limited to stable project identifiers
such as `reviewer_a`; do not add names, email addresses, or other personal metadata.

Reviewer comments belong only in the intended `human_notes` column. Private working
notes outside that column must not be committed. See
[`reproducibility-and-artifacts.md`](reproducibility-and-artifacts.md) for the repository
artifact policy.

## Phase 1 history protection

Annotate a separate copy of the exported review CSV. Machine run bundles are sealed
and immutable. Re-exporting historical reviews produces separate source-bound
derivatives. Choose a fresh output directory for each human-audit report; existing
reports/blinded exports/imports cannot be replaced even with `--overwrite`. Reports
are sealed with `FINALIZED.json` after all files are written. Analysis requires
completed source manifests; new sources additionally require valid seals/contracts.
New B2 duplicate evidence faithfully identifies the existing duplicate-only rejection
without changing admission or inferring evidence for legacy rows. See
[Phase 1](phase1-stabilization.md).
