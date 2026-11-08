# How to label `review_blind.csv` (105 records, about 1-2 hours)

1. Copy `review_blind.csv` to `review_labelled.csv` in this folder and label the copy.
   Do not edit `review_id`, `dataset_id`, `requested_class` or `record_json`.
2. For each row, read `record_json` (one generated record) and judge it against that
   dataset's `schema_<dataset_id>.json` (declared field types, ranges, categories) and your
   domain sense. `requested_class` is the class the model was asked to generate.
3. Fill the five `human_*` columns. Leave a row fully blank if you skip it.

| Column | Fill with |
| --- | --- |
| `human_valid` | `true` if the record fits the schema/domain and is a plausible member of `requested_class`; otherwise `false` |
| `human_failure_type` | `NONE` for a valid record, or one or more of: `SCHEMA`, `MISSING_FIELD`, `INVALID_CATEGORY`, `TARGET_MISMATCH`, `NUMERIC_OUTLIER`, `LOGICAL_INCONSISTENCY`, `STATISTICAL_IMPLAUSIBILITY`, `SEMANTIC_IMPLAUSIBILITY`, `OTHER` (separate several with `;`) |
| `human_severity` | optional: `low` / `medium` / `high` / `critical` |
| `human_affected_fields` | optional: field names, comma-separated |
| `human_notes` | optional: free text |

Rules from `docs/human-review.md`: judge each record on its own. Do not mark duplicates or
copying (those are measured automatically afterwards), and do not use `DUPLICATE` here.
The file hides which model made each record on purpose; please do not look it up.

## Example (made up for illustration; not a row from the file)

Dataset `Abalone19`, `requested_class = positive`. Abalone are measured in mm/200, so
diameter should not exceed length and the shell weight cannot exceed the whole weight.

Record A:
`{"sex": "F", "length": 0.62, "diameter": 0.49, "height": 0.17, "whole_weight": 1.21, "shucked_weight": 0.48, "viscera_weight": 0.26, "shell_weight": 0.36, "class": "positive"}`

| human_valid | human_failure_type | human_severity | human_affected_fields | human_notes |
| --- | --- | --- | --- | --- |
| true | NONE | | | plausible adult female |

Record B:
`{"sex": "X", "length": 0.30, "diameter": 0.45, "height": 0.10, "whole_weight": 0.20, "shucked_weight": 0.09, "viscera_weight": 0.05, "shell_weight": 0.31, "class": "positive"}`

| human_valid | human_failure_type | human_severity | human_affected_fields | human_notes |
| --- | --- | --- | --- | --- |
| false | INVALID_CATEGORY;LOGICAL_INCONSISTENCY | high | sex, diameter, shell_weight | sex X not in {M,F,I}; diameter > length; shell weight > whole weight |

When you are done, tell me; the labels are joined to the hidden key
(`../key/review_key.csv`) and the automated diagnostics only after that.
