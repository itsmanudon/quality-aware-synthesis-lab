# Human review (M1.5)

The human-review CSVs (`human_review.csv` per run; `p1_human_review.csv` cross-dataset)
are the audit input that will determine M2 design. Automated B1/B2/B3 decisions and human
adjudication are kept in separate columns. The coding agent never fills a human column and
never infers a human validity label from a B2/B3 decision.

## Columns the annotator fills

| column | meaning |
| --- | --- |
| `human_valid` | `true` / `false` — is the record itself a valid draw for its stated class |
| `human_failure_type` | one or more taxonomy labels (below); multi-label allowed, separate with `\|`, `;` or `,` |
| `human_severity` | free scale, e.g. `low` / `medium` / `high` / `critical` |
| `human_affected_fields` | comma-separated field names |
| `human_notes` | free text |

## Failure taxonomy

`NONE`, `PARSE`, `SCHEMA`, `MISSING_FIELD`, `INVALID_CATEGORY`, `TARGET_MISMATCH`,
`NUMERIC_OUTLIER`, `LOGICAL_INCONSISTENCY`, `STATISTICAL_IMPLAUSIBILITY`, `DUPLICATE`,
`SEMANTIC_IMPLAUSIBILITY`, `OTHER`.

Multi-label is expected: a record can be, for example, `NUMERIC_OUTLIER;LOGICAL_INCONSISTENCY`.

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
