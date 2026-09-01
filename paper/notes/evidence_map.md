# Evidence map

| Manuscript statement or table | Repository artifact, config, source, or literature record | Interpretation boundary |
| --- | --- | --- |
| Development dataset rows and split sizes | P1 `dataset/split_manifest.json` arrays; `dataset/profile.json`; `docs/datasets.md` | Full class counts are documented; split fingerprints and lengths are artifact-backed. |
| Development dataset feature types | P1 `dataset/profile.json`; `configs/datasets/*.yaml` | page-blocks0 preserves the source spelling `Lenght`. |
| P1 model, quotas, batch size, temperature, output limit, timeout, references | `configs/experiments/pilot_p1/*.yaml`; P1 `manifest.json`; `generation_plan.json` | Config is intended protocol; manifests/artifacts record execution. |
| Prompt v2 JSON-object transport | `prompts/generation/v2.txt`; P1 resolved configs and traces | `docs/generation-protocol.md` still describes an array-only prompt/parser and is stale. |
| TRAIN-only context and REAL TEST exclusion | P1 `manifest.json` (`no_test_leakage`); profiles; runner source | Does not independently prove absence of every possible software bug. |
| Deterministic provider-seed derivation | `src/rcqasyn/utils/seeds.py`; runner seed-plan guard; P1 `generation_seed_plan.json` | P0-v2 reused a seed and is excluded from diversity interpretation. |
| B1 definition | runner `_run_b1`; `docs/baselines.md` | Applies to parseable pool only. |
| B2 definition and severities | `src/rcqasyn/baselines/validators.py`; runner `_run_b2`; P1 configs | Duplicate rejection is an extra policy beyond emitted validator evidence. |
| B3 definition | `src/rcqasyn/baselines/judge.py`; P1 configs; judge prompt v1 | Score is uncalibrated and same-model. |
| Intrinsic metrics | `src/rcqasyn/metrics/intrinsic.py` | JSD is squared Jensen--Shannon distance with base 2; correlation error is mean absolute pairwise difference. |
| TRTR/TSTR implementation | `src/rcqasyn/metrics/utility.py` | `pr_auc` currently aliases average precision; undefined statuses must remain null. |
| Human-review sample and strata | `artifacts/reports/p1/p1_human_review_manifest.json` | Strata hits overlap and do not sum to 120. |
| Reviewer A/B sizes and overlap | `artifacts/reports/human_audit/blinded/*.manifest.json` | Reviewer B has 14/14/12 dataset allocation and balanced requested class. |
| Human-validity definition and blindness | `docs/human-review.md`; blinded CSV headers | Redundancy alone is not record invalidity. |
| P1 pool sizes and B1/B2/B3 acceptance | `artifacts/reports/p1/p1_b1_b2_b3.json` | Ecoli4 has 201 records against 200 requested. |
| P1 duplicate and reference-copy rates | `artifacts/reports/p1/p1_copying_diagnostics.json` | Exact equality only; no near-copy or privacy conclusion. |
| P0-v3 versus P1 duplicate rates | `artifacts/reports/p1/p0v3_vs_p1_diversity.json` | One run per scale; artifact explicitly disclaims significance. |
| B2/B3 disagreement counts and reason classes | `artifacts/reports/p1/p1_b2_b3_disagreements_summary.json` | A policy disagreement is not critic correctness without human labels. |
| Support representation and descriptive summaries | `artifacts/reports/p1/p1_support_distance_summary.json`; diagnostics source | No threshold; distances are representation-dependent and not cross-dataset comparable. |
| Pilot utility caution | `artifacts/reports/p1/p1_trtr_tstr.json`; `p1_cross_dataset_comparison.json` | Several logistic TSTR entries are undefined; one split only. |
| Current Evidence contract fields | `src/rcqasyn/contracts/evidence.py` | Dedicated evidence scope is not present despite the intended architecture in `docs/architecture.md`. |
| Framework pipeline status | Current source, `docs/architecture.md`, `docs/research-plan.md` | M2+ nodes are proposed, not implemented. |
| Core versus extension hierarchy | Manuscript Introduction/Method/status table; current source interfaces | Core is record/dataset evidence plus calibration/fusion and decision control; repair and richer optimization remain extensions. |
| Professor-pitch P1 table and key numbers | `p1_copying_diagnostics.json`; `p1_b1_b2_b3.json`; `p1_human_review_manifest.json` | Development observations only; Ecoli4 uses the persisted 201-record denominator. |
| Pitch engineering test statement | `tests/`; `.venv` run of `pytest --cov=rcqasyn` on 2026-09-01 | 98 passed and 86% line coverage are engineering evidence, not scientific evidence. |
| Literature-supported generator families | Official NeurIPS, PMLR, ICLR/OpenReview, and arXiv records in `references.bib` | Claims are limited to what each primary record evaluates. |
| LLM judge limitations | Zheng et al. official NeurIPS record | Assistant-response findings do not establish tabular critic behavior. |
| Calibration and risk-control motivation | Guo et al. PMLR; Angelopoulos et al. arXiv | No guarantee is transferred to RC-QASyn. |

## Discrepancy register

| Discrepancy | Manuscript treatment |
| --- | --- |
| Ecoli4 has 201 parseable P1 records against a requested 200; an aggregate artifact consequently records an impossible negative parse-failure count. | Use 201 as the persisted pool denominator, disclose over-generation, and do not quote the invalid negative count. |
| All three P1 manifests record `git_dirty=true` at commit `ab492bf294b563e4b165755692ac8edb8f3dd2be`. | Treat persisted run artifacts and resolved configs as primary evidence; do not claim a clean historical checkout. |
| `docs/generation-protocol.md` describes JSON-array transport, while prompt v2, current configs, and current source use a JSON object containing `records`. | Follow higher-priority artifacts/config/source and record the documentation as stale. |
| Current Evidence contracts omit a dedicated scope field, while architecture docs describe FIELD/RECORD/SUBGROUP/DATASET scope. | Present explicit scope as proposed M2+ architecture. |
| The working title says “Risk-Calibrated,” while calibration and risk control are not implemented. | Treat the phrase as the intended final method and research hypothesis; claim no current calibrated guarantee. |
| Several pilot logistic-regression TSTR entries are undefined. | Do not interpret pilot utility as final comparative evidence. |
| `RC_QASyn_Research_Implementation_Manifest.xlsx` could not be opened with the required read-only spreadsheet runtime. | Exclude the workbook from the manuscript evidence base for this pass. |

## P1 report artifacts used by the manuscript

- `artifacts/reports/p1/p0v3_vs_p1_diversity.json`
- `artifacts/reports/p1/p1_b1_b2_b3.json`
- `artifacts/reports/p1/p1_b2_b3_disagreements_summary.json`
- `artifacts/reports/p1/p1_copying_diagnostics.json`
- `artifacts/reports/p1/p1_human_review_manifest.json`
- `artifacts/reports/p1/p1_support_distance_summary.json`
- `artifacts/reports/p1/p1_trtr_tstr.json`
- `artifacts/reports/p1/p1_cross_dataset_comparison.json`
