# Academic-draft methods and results

We constructed provisional synthetic datasets from frozen M4/M5 admissions using four deterministic strategies: source order, farthest-first diversity, marginal TRAIN-region coverage and eligibility/uniqueness/quota-constrained class-balanced coverage. Geometry reused the TRAIN-fitted mixed-type distance; numerical spans and source identities were checked without refitting validators. Fixed per-dataset budgets matched sample counts across strategies. Coverage, redundancy, literal minority support and concentration were reported separately from validity and utility.

The bounded study produced 51 provisional datasets across three existing datasets, with all source-bound audits passing and exact deterministic replay. Radius .05 and near-duplicate tolerance .01 were declared before outcomes. No human labels or REAL TEST values informed construction. Main middle-budget results follow; these geometric comparisons do not establish classifier performance, genuine record validity, novelty or superiority.

| Dataset | Strategy | Budget | Distinct TRAIN feature coverage | Exact duplicate rate |
| --- | --- | --- | --- | --- |
| Abalone19 | source-order | 56 | 0.6225 | 0.3571 |
| Abalone19 | farthest-first | 56 | 0.9401 | 0.0000 |
| Abalone19 | coverage-greedy | 56 | 0.9479 | 0.1071 |
| Abalone19 | quality-coverage | 56 | 0.9479 | 0.0000 |
| Ecoli4 | source-order | 70 | 0.4164 | 0.2000 |
| Ecoli4 | farthest-first | 70 | 0.4684 | 0.0000 |
| Ecoli4 | coverage-greedy | 70 | 0.5056 | 0.1143 |
| Ecoli4 | quality-coverage | 70 | 0.5056 | 0.0000 |
| page-blocks0 | source-order | 49 | 0.9139 | 0.2653 |
| page-blocks0 | farthest-first | 49 | 0.9324 | 0.0000 |
| page-blocks0 | coverage-greedy | 49 | 0.9324 | 0.1633 |
| page-blocks0 | quality-coverage | 49 | 0.9324 | 0.0000 |

Human-label review and scientific acceptance remain pending. Unknown semantics, selected-cohort bias, candidate-pool limitations and historical exact-value TRAIN/TEST overlap constrain interpretation. Phase-6 repair is outside the current study.
