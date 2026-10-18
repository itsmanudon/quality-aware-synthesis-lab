# Agent-proposed labels for personal supervisor review

READY FOR SUPERVISOR REVIEW — 120 AGENT LABEL PROPOSALS

VALID: 0; INVALID: 27; INDETERMINATE: 93.

These are agent proposals, not human-approved ground truth. All 120 remain AGENT / PENDING_HUMAN_APPROVAL with null human final labels. No personal supervisor file inspection or label approval is claimed.

Ambiguous/insufficient-evidence proposals: 93. The known domain-semantic gaps remain unresolved for all 120. Absence of a detected violation is not positive evidence of validity.

The 27 INVALID proposals cite absent declared fields and/or non-integral values in source-declared integer fields. There are 16 missing-field records and 16 fractional-integer records, with five records in both groups. Integral floats such as 10.0 are treated as integer-compatible; source-range excursions are not rejection evidence.

## Dataset and recorded control distribution

| Dataset | Records | VALID | INVALID | INDETERMINATE | B1 accepted/rejected | B2 accepted/rejected | B3 accepted/rejected |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Abalone19 | 40 | 0 | 5 | 35 | 40/0 | 35/5 | 40/0 |
| Ecoli4 | 40 | 0 | 6 | 34 | 40/0 | 34/6 | 39/1 |
| page-blocks0 | 40 | 0 | 16 | 24 | 40/0 | 34/6 | 40/0 |

Control counts were joined after the answers were sealed, solely to describe the retained cohort. They were not annotation evidence. No B2/B3-versus-human analysis was run.

## How to review

Use review.csv or review.json (same 120 records, original cohort order). Read feature_values / payload, proposed rationale and cited source evidence. Personally inspect every row. Edit only human_review_status (to REVIEWED), human_final_label (VALID / INVALID / INDETERMINATE), human_correction_note and human_reviewer_reference. Explain changed labels, preferably with source evidence. Do not edit or fill absent original feature values. Return one completed working copy.

The read-only context in these convenient sheets is richer than the strict import schema. After return, the agent must check every context column against this original export, project only the four human fields onto review-import-template.json, and use the existing research review importer. That import alone does not authorize analysis: you must explicitly confirm the resulting reviewed-ledger fingerprint.

review-priority.md / review-priority.csv list high-uncertainty records first without changing the main sheet order. All 93 INDETERMINATE proposals need positive-evidence scrutiny. Pay particular attention to descriptive support excursions (which were not treated as invalidity), declared-key absences, integer-declaration interpretations, and logical CSV row 94 / data record 93.

Work on a copy of review.csv or review.json outside this sealed bundle. Keep this original unchanged for context comparison. Neither this ledger nor its fingerprints cryptographically authenticate a human or resist a malicious actor with the same permissions.

## Scientific limitations

Recorded nonrepresentative cohort retained; historical ID-only diagnostic lookup biased strata. No resampling or population-wide inference.
Unknown target mappings, physical meanings/units and cross-field rules remain unresolved. Rarity, duplication and outside-TRAIN support are not automatic invalidity. Documented historical page-blocks0 TRAIN/TEST overlap is retained. The fixed 40-row review overlap does not prove a second independent review. Contribution remains separate from validity.

No new dataset, Phase-3 method, authentication feature, production approval or paid provider call was introduced. Stop here for personal supervisor review; full-suite testing and independent final verification remain at final closeout.
