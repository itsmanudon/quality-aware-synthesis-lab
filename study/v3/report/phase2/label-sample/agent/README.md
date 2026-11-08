# Agent labels (not human labels)

`review_agent_labelled.csv` labels the 105 records of `../blind/review_blind.csv` with
`agent_*` columns, written by `study/v3/agent_labels.py` (rule-based, deterministic; rerun
with `python -m study.v3.agent_labels`). The human file `../blind/review_blind.csv` was
read, not changed, and no `human_*` column was filled. Report these as one more automated
judge, never as human validation. Do not copy them into `review_labelled.csv`. If you later
label by hand, do it before reading this file.

Inputs: the record, `requested_class`, and `schema_<dataset>.json`. Not used: the hidden
key, B2/B3/gate outputs, TRAIN or TEST data.

| Rule | Check | Failure type | Severity |
| --- | --- | --- | --- |
| S1 / S2 | all declared fields present / no undeclared field | MISSING_FIELD / SCHEMA | high |
| S3 | `class` equals `requested_class` | TARGET_MISMATCH | critical |
| S4 | categorical value in documented categories | INVALID_CATEGORY | high |
| S5 / S6 | numeric / integer where declared | SCHEMA | high / medium |
| S7 | value inside declared range | NUMERIC_OUTLIER | medium |
| D1 | ecoli `lip`, `chg` and yeast `erl` take only their two source values | STATISTICAL_IMPLAUSIBILITY | low |
| A1 | abalone diameter <= length | LOGICAL_INCONSISTENCY | high |
| A2 | abalone height <= diameter | LOGICAL_INCONSISTENCY | medium |
| A3 | each part weight < whole weight | LOGICAL_INCONSISTENCY | high |
| A4 | shucked + viscera + shell <= whole weight | LOGICAL_INCONSISTENCY | medium |
| A5 | diameter / length within 0.70-0.90 | STATISTICAL_IMPLAUSIBILITY | low |
| A6 | height <= 0.30 | STATISTICAL_IMPLAUSIBILITY | medium |

Any failed rule gives `agent_valid = false`. `agent_confidence` is high when a hard rule
failed (S1-S5, S7, A1, A3), low when only low-severity rules failed, and medium otherwise.
Passing records get medium confidence for abalone and low for the other five datasets,
where only schema/range checks are possible.

Limits: no rule judges class membership (the schemas mark it UNVERIFIED), and there are no
cross-feature checks for vehicle, ecoli or yeast. So `true` there means only "no checkable
rule failed". The thresholds in A4-A6 were set from domain knowledge after one read of the
records and were not tuned to change any count. A4 has no tolerance, so one record that
exceeds by 0.001 (`v3r-0397ef4f912c6eb3`) is flagged; that is inside plausible measurement
noise. Duplicates are not marked, per `docs/human-review.md`.
