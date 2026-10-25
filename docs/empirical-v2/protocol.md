# RC-QASyn empirical protocol v1 - frozen before scoring

Base: 244a9bfd490a03a35c4be5cb3b83354e425795fc. Date: 25 October 2026.
Machine configuration: configs/empirical/protocol-v1.json. No tuning after scores.

## Audit and questions

RQ1 structural violation frequency; RQ2 local/global complementarity;
RQ3 coverage and redundancy at matched budgets; RQ4 bounded repair;
RQ5 downstream classification; RQ6 uncertainty and fresh-split stability.
The full Phase-6 report and manuscript were inspected. Their 601 occurrences,
75 rejects, 54 successful repairs and 21 ineligible rejects are consistent.
Existing M2 five configurations, M4 six admission policies, M7 four strategies
and three budgets, and M6 original/repair comparisons will be reused and cited.
Historical utility stores aggregates, not paired example predictions. Refit the
unchanged model specifications and verify reproduced metrics before inference.
The historical unfiltered scorer can turn missing targets into 'nan'; exclude
missing/unsupported labels explicitly rather than using requested_class.

## Track A: fixed historical split

Use the exact three source datasets, manifests and 601 historical occurrences.
Source raw files are read from the frozen original checkout, with recorded hashes.
No original split/candidate/control/archive is changed. TEST was used historically;
value-level TRAIN/TEST overlap is disclosed. This is descriptive, not confirmation.

At fixed budgets Abalone19=56, Ecoli4=70, page-blocks0=49, compare:
(1) unfiltered but feature-complete, labeled numerical/categorical-compatible
candidates (integer violations retained and counted), random seeds 13/29/43/61/79;
(2) schema-complete random at those five seeds;
(3) combined-admitted random at those five seeds;
(4) structure-only, local-only, global-only and combined admission followed by
identical quality-coverage selection (a nested eligibility ablation, not an
isolated causal effect of a score); (5) source-order, farthest-first,
coverage-greedy and quality-coverage on the same combined-admitted pool;
(6) existing original/repair-augmented four-selector comparisons.
Report pool sizes, achieved budgets, class counts and all shortfalls. Distinct
feature exhaustion is an unavailable matched-budget comparison, never silently
compensated. Reuse existing sensitivity rows rather than modify them.

Models: frozen logistic regression (liblinear, max_iter=300) and random forest
(50 trees), seed 42, existing median imputation/standard scaling/one-hot encoding,
fitted on actual training populations. Regimes: TRTR, pure TSTR, HYBRID_MINORITY.
Also replay all 138 Phase-6 utility rows, including 24 unavailable rows.

Separate external training comparisons: class_weight='balanced' logistic on real
TRAIN; RandomOverSampler and SMOTE (SMOTENC for Abalone19) adding exactly b minority
rows to real TRAIN. Standard SMOTE numeric interpolation is not rounded; report
integer schema failures. Plain SMOTE is unsupported on Abalone19 categorical input;
SMOTENC is unsupported as a distinct mixed-type comparison on numerical-only data.
Do not equate these generation/training baselines with candidate curation.

## Track B: fresh train-only offline curation study

Five deterministic stratified outer splits using the existing make_split algorithm
and declared test_size=.20. Fit every transformation, generator and evidence model
on that split's TRAIN only. Fresh pool size=4b, minority only. Generator: SMOTENC
for Abalone19, SMOTE for Ecoli4, RandomOverSampler for integer page-blocks0. The
last deliberately preserves source integers without unapproved coercion; its
lack of new support is a substantive limitation. Use established imbalanced-learn
implementations, pinned version recorded. Scale numerical inputs by TRAIN
StandardScaler before SMOTE/SMOTENC, inverse-transform numerical outputs; do not
round integer declarations. ROS copies source rows exactly. k=min(5,n_minority-1).
No historical candidate, frozen evidence parameter or original policy-score
reference is reused in Track B. Rebuild existing M2 evidence, descriptive
midrank local/global indices, q=.90 admission and M7 geometry from fresh TRAIN.

Compare same-pool schema random, admitted random, source-order, farthest-first,
coverage-greedy, quality-coverage at b. Selection randomness uses the split seed.
Compare TRTR, balanced-logistic, ROS+b and SMOTE/SMOTENC+b separately. Utility on
curated minority data is HYBRID_MINORITY. Pure TSTR is explicitly unavailable
because this declared offline generator emits one class; no majority is invented.
Save all 15 split populations, generated payloads and fit-source identities.
These are repeated random holdouts of the same datasets, with overlapping test
rows; they are not mutually independent experiments and do not replicate LLM
quality. Report five-split mean +/- sample SD and every row, including failures.
Value-level duplicate overlap is measured, not silently removed.

## Metrics and uncertainty

Separate source compliance, TRAIN distinct-feature coverage at .05, exact/near
redundancy (.01), F1, AP (existing pr_auc alias, not trapezoidal PR area), balanced
accuracy, MCC, AUROC and confusion counts/positive/negative denominators.
Preserve repository MCC=0 for degenerate predicted margins, recording that event;
bootstrap MCC is undefined in such replicates and valid/undefined counts are saved.
Missing true classes make AP/BA/AUROC undefined. No human-validity metrics.

Bootstrap Track A from saved aligned per-example predictions: 2,000 paired
stratified resamples, seed 20261025, percentile 95% intervals. Resample positive
and negative indices independently within their strata, identically across methods.
Intervals condition on fitted models, observed TEST and class counts. Primary
pairs, both classifiers and available regimes: quality-coverage original minus
REAL_TRAIN (hybrid); quality original minus schema-random seed13 (TSTR/hybrid);
quality original minus combined-random seed13 (TSTR/hybrid); repair quality minus
original quality (TSTR/hybrid). Individual intervals for primary endpoints plus
TRTR. Supplement recall with Wilson 95% bounds. No multiplicity-adjusted significance
claim, and four/six positives cannot be enlarged by resampling. Bootstrap variability
and between-split SD are distinct. No bootstrap of aggregate metrics.

## Unavailability, provenance and scope

Record failures with reason; never discard difficult splits or best-select seeds.
If library installation fails, mark affected external/replication methods unavailable
and continue historical evidence. No paid provider calls. No new validator or phase.
Bounded repair remains exact Decimal half-even, <=3 integer fields, <=.5 per edit;
no label invention, imputation, category substitution or partial over-limit repair.
Human labeling/calibration are removed from active scope; historical files remain.
No independent semantic validity is established. Author/institutional/funding and
venue declarations need human completion before submission.

Every output binds protocol hash, base/implementation SHA, input/file hashes,
source/split row identities, generated pool identity, selected IDs, model parameters,
predictions, metrics, dependency versions, runtime, failure reasons and result hashes.
Fresh output versions refuse overwrite; replay compares substantive hashes excluding
runtime. Frozen artifact byte integrity and full regression/static checks conclude
work. New manuscript paper/rcqasyn-empirical-v2; original draft unchanged.

## Reproduction (implementation will follow this protocol)

Set PYTHONPATH to this worktree/src; use Python 3.12 plus existing dependencies
and pinned imbalanced-learn. Run python scripts/run_empirical_study.py --output
artifacts/reports/empirical-v2/run-v1 --source-root <frozen checkout>. Replay in a
fresh output directory. Reporting and typesetting read saved evidence only.
