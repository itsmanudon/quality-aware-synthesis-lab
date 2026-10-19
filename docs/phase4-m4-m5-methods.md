# Phase 4: M4/M5 descriptive evidence fusion and shadow admission

Status: engineering prototype; scientific acceptance and human label review pending.
Parent: `c47cccb54c2c1cc4f2eff4cb2f83489a0e02b855`. Phase-1 freeze:
`341fc2ce647c180b0f4a34fdbdeb49a0acfdcbcc`. All work is local.

## Architecture and boundaries

Frozen source-bound candidate -> frozen M2 structural/local/global evidence ->
M4 descriptive transformation -> dependent evidence vector/diagnostics ->
calibration eligibility gate (inactive on actual data) -> M5 deterministic shadow
policy -> sealed decision explanations -> offline behavior comparison.

Raw evidence, descriptive normalized scores, future calibrated probabilities,
policy actions, and dataset contribution are separate quantities. No accepted
synthetic dataset is built. Dataset contribution is deferred to Phase 5. M2
validators and all B1/B2/B3 algorithms, thresholds and historical decisions are
unchanged. No provider calls or new datasets are used.

Source population: exactly 601 ordered historical occurrences: page-blocks0 200,
Ecoli4 201, Abalone19 200. The corrected 120-row cohort, 40-row overlap, row-94
reconciliation and three dataset specifications remain frozen as source artifacts.
All latest proposals remain AGENT/PENDING_HUMAN_APPROVAL: 0 VALID, 27 INVALID,
93 INDETERMINATE. These proposals are not calibration or evaluation ground truth.

## Frozen M2 input

Read `artifacts/reports/phase3/experiments-v2/baseline-k5-a10` using the sealed M2
reader. It contains 1,803 records, three families per occurrence, with exact
payload, dataset specification, configuration and TRAIN-reference fingerprints.
Local mixed-type k-neighbor distance uses k=5; cross-feature robust/one-hot
shrinkage covariance uses alpha=0.1 and ridge=1e-8. Their mathematical definitions
and source-rule authority are in `docs/phase3-m2-methods.md`; Phase 4 never refits
these models. Raw statistical scores increase with weaker support. Structural
violation flags remain separate from these continuous scores.

## M4.1 transformation (candidate-mid-ecdf-v1)

For dataset d and statistical family f, reference R_df is the complete available,
finite raw-score population among these frozen generated candidates. It is
**not** REAL TEST and is **not** a TRAIN distribution or a human-label population.
Each reference records ordered occurrence IDs, raw scores, evidence fingerprints,
size, definition and its own canonical content fingerprint. The focal candidate
is included. This retrospective descriptive choice avoids refitting M2 and makes
comparisons conditional on this particular candidate population.

For score s and reference size n,

$$u_{df}(s)=\frac{\sum_{r\in R_{df}}1[r<s]+\frac12\sum_{r\in R_{df}}1[r=s]}{n}.$$

This empirical mid-distribution statistic gives equal scores equal ranks; all
constant values receive 0.5. Larger u means weaker statistical support. An n=200
unique minimum receives 0.0025 and maximum 0.9975. It is not P(INVALID), a tail
p-value, a conformal score guarantee, a validity threshold or calibrated risk.
Changing the candidate population can change u. References are dataset- and
family-specific; they are not pooled across datasets. Minimum reference size is
predeclared as 10. Missing/non-AVAILABLE scores or sparse references yield null u
with MISSING_SCORE or SPARSE_REFERENCE. They never become zero risk. Nonfinite
inputs are rejected. No target label, agent judgment or recorded B2/B3 outcome
enters the transformation. Candidate distributional membership is not proof of
physical validity. Historical exact-value TRAIN/TEST overlap remains a limitation;
no TEST values or TEST-derived statistics are used to fit this transformation.

## M4.2 dependence and descriptive fusion

Versioned contracts: `m4-evidence-vector-v1`,
`dependent-max-min-descriptive-v1`, `shadow-policy-v1` and `m5-shadow-decision-v1`.
Vectors retain both raw scores, both percentiles, all input evidence fingerprints,
reference/configuration/specification identities, family reasons and structural
findings. With both percentiles available, descriptive indices are

$$U=\max(u_L,u_G),\qquad I=\min(u_L,u_G).$$

If either is unavailable, both combined indices are null and the vector is
incomplete. U and I are uncalibrated concern indices. No independent-likelihood
product, evidence multiplication or learned ensemble is used. This avoids
counting correlated families as independent observations; it does not eliminate
all dependence or establish optimal fusion. M5 uses the individual family vector
and a union predicate, not a probability derived from U.

Dependence diagnostic is Spearman correlation, computed as Pearson correlation
of average ranks on the paired-available population:

$$\rho=\frac{\sum_i(a_i-\bar a)(b_i-\bar b)}
{\sqrt{\sum_i(a_i-\bar a)^2\sum_i(b_i-\bar b)^2}}.$$

Sparse (<2) or constant ranks produce null rho with an explicit undefined status.
At cutoff q, A={i:u_L>=q}, B={i:u_G>=q}, reported only on paired-available cases.
Report |A union B|, |A intersection B|, |A symmetric-difference B|,
J=|A intersection B|/|A union B| (null if denominator zero), and number with equal
concern state. These are redundancy/agreement statistics, never correctness.

## M4.3 future calibration interface

Actual current status: **NOT_ELIGIBLE_UNAPPROVED_LABELS**. No real calibrator is
fitted or persisted, and no policy consumes calibrated risk. The offline runner
only accepts the sealed, unapproved agent review package and emits this explicit
refusal. No official human performance analysis is performed.

Future `fit_confirmed_research` first calls the existing research-ledger
confirmation validator, verifying the whole source-bound cohort, rubric/scope,
proposal set, every reviewed row, reviewer provenance and the explicit reviewed
ledger fingerprint confirmation. It then validates the exact frozen M2 population
and replays its normalized predictor. This workflow checks content/provenance;
it does not cryptographically authenticate people or resist a malicious agent
with the same permissions. Production-authenticated approval stays disabled.

Calibration is dataset-specific. Caller-declared, unique calibration and evaluation
occurrence IDs must be nonempty, disjoint and drawn from reviewed generated
candidates. REAL TEST is forbidden. INDETERMINATE and unavailable predictors are
excluded with separate counts, never mapped to a binary class. Both partitions
must contain at least 5 VALID and 5 INVALID scored records. Constant calibration
predictors also refuse. This is a conservative engineering eligibility floor,
not an adequacy or generalization guarantee. Partition choice and sample adequacy
still need independent scientific review before any official use.

Predeclared method: `isotonic-increasing-v1`. Given confirmed binary outcomes
y_i=1 for INVALID, y_i=0 for VALID and predictor x_i=U_i, fit monotone g:

$$\hat g=\arg\min_{g\text{ nondecreasing},0\le g\le1}\sum_{i\in C}(y_i-g(x_i))^2.$$

The implementation uses scikit-learn IsotonicRegression with increasing=True and
out_of_bounds='clip', recording fitted x/y thresholds and method identity.
Evaluation-only diagnostics are Brier score
$$\mathrm{BS}=|E|^{-1}\sum_{i\in E}(\hat g(x_i)-y_i)^2$$
and five fixed reliability bins [j/5,(j+1)/5), j=0..4, last bin includes 1.
Report bin count, mean prediction and observed INVALID fraction. These future
selected-cohort diagnostics do not imply validity performance on the full source
population. No actual current-human-cohort metrics are computed. A separate
`fit_synthetic_fixture` entry point accepts fixture-prefixed IDs and the synthetic
population only; it cannot establish real-cohort eligibility. Synthetic tests
exercise fitting, refusal, partitioning and deterministic output.

## M5 policy and precedence

Plan `configs/phase4/m4-m5-shadow-v1.json` was committed before Phase-4 outcome
inspection. It fixes q=0.9 for structure-only, local, global, combined, and q=0.8
and q=0.95 combined sensitivities. These are exploratory review-budget heuristics,
not tuned official thresholds or calibrated risk controls. No best policy is
selected from agent proposals or shadow outcomes.

For required families F, concern C_F(q) = OR over f in F of [u_f>=q]. Empty F
means no statistical review condition. Decisions in order:

1. Substantiated M2 authoritative structural INVALID -> REJECT_STRUCTURAL.
2. Structural evidence UNAVAILABLE or a required percentile missing -> ABSTAIN.
3. Structural evidence PARTIAL -> REVIEW_REQUIRED.
4. Any required statistical concern -> REVIEW_REQUIRED.
5. Otherwise -> PROVISIONAL_PASS.

The combined union policy reviews local/global concern disagreement too. Family
unavailability cannot silently pass under a policy requiring that family.
Structure-only does not require statistical evidence, but all missing-family
states are still recorded. Hard rejection dominates statistical unavailability
when an authoritative violation already exists. Unsupported physical rules cannot
cause hard rejection. A statistical-only outlier cannot become INVALID.
PROVISIONAL_PASS explicitly does **not** mean human-validated VALID.

Every decision records occurrence/payload/source identity, evidence and vector
fingerprints, policy/configuration, structural judgment, concern families,
missing-family state, explanations/reason codes, calibration status, and deferred
contribution. No raw candidates, M2 evidence, accepted populations or B1/B2/B3
outcomes are overwritten. Control comparison is a post-decision join only.

## Offline evaluation and reproducibility

Six policies x 601 occurrences = 3,606 shadow decisions. Report per-dataset
four-action counts, evidence availability, dependence, literal payload class
breakdown including absent class, and joint action/recorded-acceptance tables for
B1/B2/B3. Requested class is never substituted for absent payload class.
Provisional-pass/recorded-acceptance symmetric difference is a behavior comparison,
not disagreement with human truth. Sensitivity reports action transitions and
changed counts against q=0.9; no threshold optimization follows.

Canonical fingerprints use the repository sorted compact JSON algorithm, not raw
file SHA conventions. Guarded writers create new versioned bundles, seal exact
bytes and refuse differing overwrites. Readers validate seals, fingerprints,
unique complete policy/occurrence coverage and deterministic decision replay;
with the M2 path they also replay the exact descriptive transformation. Repeat
experiments must match vector and decision content hashes. Outer fingerprints
include measured runtime and may differ. Reporting is derived solely from sealed
results. Fixed SVG metadata/hash salt makes report content deterministic.

Reproduce from a checkout with the optional `research` dependencies installed:

```powershell
$env:PYTHONPATH = "$PWD/src"
python -m rcqasyn phase4 shadow artifacts/reports/phase4/shadow-reproduction-v1 --source-root 'D:/Github Repos/quality-aware-synthesis-lab'
python -m rcqasyn phase4 inspect artifacts/reports/phase4/shadow-reproduction-v1
python scripts/report_phase4.py --experiment artifacts/reports/phase4/shadow-reproduction-v1 --output artifacts/reports/phase4/report-reproduction-v1
```

Source-root must be the untouched Phase-1 checkout; fresh output versions are
required. No seed is used by this deterministic layer. Input identities, versions,
configurations, content fingerprints and runtime are stored in each run.

## Deferred scientific decisions and limits

Use the report's single decision-ledger.csv for personal review of all 120 labels,
unknown original target mappings/physical meanings/cross-field constraints,
calibration eligibility/partitioning, official thresholds, Phase-3/4 scientific
acceptance and final claims. The cohort is selected and nonrepresentative;
TRAIN/TEST exact-value overlap and one-supervisor review limitations persist.
Descriptive ranks, statistical support and duplicates do not determine validity,
novelty, contribution or downstream utility. No novelty, superiority, calibrated
risk-control guarantee or validated correctness is claimed. Phase 2 and Phase 3
remain scientifically unfrozen. Phase 5 and Phase 6 are outside this work.
