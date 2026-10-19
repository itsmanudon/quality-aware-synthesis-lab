# Phase 5: M7 coverage-aware provisional dataset construction

Engineering prototype, with scientific acceptance and personal human review pending.
Exact parent: `0a7005e3b36438ba52fa25dd99d9a2b54a1bf1b3`.

## Architecture and scope

Authoritative crosswalk + frozen Phase-4 decisions -> complete labeled-record
eligibility -> frozen TRAIN-only mixed-distance geometry -> deterministic
budgeted set selection -> original selected payloads + complete selection ledger
-> full replay audit -> sealed versioned datasets -> geometric comparison report.
No human labels, providers, utility fitting, additional validators, calibration,
repair or TEST-driven selection are introduced. No earlier phase is scientifically
frozen. All output datasets are EXPLORATORY_PROVISIONAL_NOT_HUMAN_VALIDATED.

The main eligible pool is precisely the frozen combined-review q=.90 provisional
population, restricted to complete source-contract records. Structural rejects,
review-required and abstained records remain deferred with explicit reasons.
Class must occur in the original payload, with its original literal token;
requested_class never supplies a missing class. Every source field must be present,
non-null and compatible with authoritative primitive/category declarations.
Integer-compatible floats are allowed; observed numerical ranges do not become
validity rules. No imputation, relabeling, repair or altered payload is allowed.

Pool sizes are Abalone19 170, Ecoli4 162 and page-blocks0 119. These are provisional
eligibility counts, not verified-valid populations. The 120 agent proposals remain
0 VALID, 27 INVALID and 93 INDETERMINATE with no human approvals. Those proposals
do not enter M7 objectives, budgets, selection or geometric metrics.

## TRAIN-only identity and distance

Check the recorded TRAIN indices, disjoint TRAIN/TEST identities, TRAIN frame
fingerprint and canonical M2 TRAIN-reference fingerprint. Read TRAIN values only
for geometry. Reading source bytes and split membership for integrity is distinct
from consulting TEST values. No TEST statistic, label or score enters any M7
calculation. Preserve the documented historical exact-value TRAIN/TEST overlap
limitation; source provenance cannot erase that limitation.

The frozen M2 numerical spans are reused and checked against the same TRAIN
reference. Call the existing Phase-3 `TrainEvidenceModel.distances` function on a
small frozen-data view; no validator, covariance or neighborhood model is refitted.
For p features, the exact mixed distance is

$$d(x,z)=p^{-1}\sum_{j=1}^{p}\delta_j(x_j,z_j).$$

For numerical feature j with frozen TRAIN range R_j>0,
$$\delta_j=\min(|x_j-z_j|/R_j,1).$$
For R_j=0 use 0 for equality and 1 for inequality. For nominal features use
$$\delta_j=1[x_j\ne z_j].$$
The class field is excluded from distance. Distances are descriptive geometry,
not physical validity or calibrated risk. Unsupported TRAIN feature rows are
excluded with recorded IDs; remaining rows retain their source IDs. No supported
reference causes explicit failure, not imputation. Single-row references and
constant features are supported. Sparse minority support is reported explicitly.

## Reference regions, coverage and density

Let T be supported frozen TRAIN rows. Regions R are distinct canonical
(feature-payload, literal-class) pairs, retaining first-source representatives.
This prevents repeated identical TRAIN rows from multiplying the selection
objective. Different literal classes at the same geometry remain separate regions;
this does not resolve target truth. Numerical JSON type distinctions are preserved
by canonical payload identity even if distance is zero. Report row-weighted,
distinct-feature and region coverage separately.

For predeclared radius r=.05 and selected set S,
$$h_t(S)=1[\min_{s\in S}d(s,t)\le r],\quad h_t(\varnothing)=0.$$
Coverage of reference population A is
$$C_A(S)=|A|^{-1}\sum_{t\in A}h_t(S).$$
Report A=T, distinct TRAIN feature representatives, and R. For class-balanced
region coverage, w_t=1/(K n_y) for region class y, K represented literal classes
and n_y their region count:
$$C_{bal}(S)=\sum_{t\in R}w_t h_t(S).$$
Geometric class-balanced coverage can be supplied by a candidate with another
literal class because the distance itself is label-free. Therefore also report
per-TRAIN-class coverage by ANY selected candidate and by SAME-literal-class
selected candidates. Minority is the least frequent supported TRAIN literal class,
with lexicographic token tie-break. It does not assert an unknown original target
mapping. Minority-label selection quotas and same-label metrics preserve the
available minority support without inventing it.

Candidate density is
$$D(s)=|T|^{-1}\sum_{t\in T}1[d(s,t)\le r].$$
Report mean D over selected records and the share with D at or above the eligible
pool's 75th percentile. That percentile is a descriptive concentration reference,
not a validity boundary. Assign selected candidates to the nearest distinct TRAIN
feature representative, with first-reference tie-breaking. If assignment bin
fractions are p_b, report HHI=sum_b p_b^2. Larger HHI describes concentration in
fewer nearest-reference bins; it is not a utility or validity measure.

## Budgets and predefined matrix

Plan: `configs/phase5/m7-study-v1.json`, committed before geometric outcomes.
For each dataset let U be the distinct feature-payload count in the complete
primary eligible pool. Budgets are max(1,floor(f U)), f=.25,.50,.75. This allows
the exact-feature-deduplicated strategy to participate at matched sample counts.
Availability is measured independently for each dataset, not assumed equal.

| Dataset | Eligible | Distinct feature payloads | Fixed budgets |
| --- | ---: | ---: | --- |
| Abalone19 | 170 | 113 | 28, 56, 84 |
| Ecoli4 | 162 | 141 | 35, 70, 105 |
| page-blocks0 | 119 | 99 | 24, 49, 74 |

Main comparison: four strategies x three budgets x three datasets = 36 datasets.
Control: B2-accepted INTERSECT main provisional pool, source order at those same
budgets = 9 datasets. This is explicitly an intersection, not unfiltered B2
acceptance. B1/B3 intersections equal the main pool here and are not redundantly
constructed. Sensitivity: quality-coverage on frozen q=.80 and q=.95 provisional
pools at the primary middle budget = 6 datasets. Total 51, with no policy changes.
No subset is described as a replacement for historical accepted populations.

## Four selection strategies and exact objectives

A. Source-order: take the earliest eligible source occurrences up to budget b.

B. Farthest-first: seed with earliest source occurrence. Thereafter choose
$$s^*=\arg\max_{s\in E\setminus S}\min_{z\in S}d(s,z).$$
This is deterministic diversity control, not a learned optimizer.

C. Coverage-greedy: choose the largest uniform region-coverage marginal gain
$$\Delta C_R(s\mid S)=\sum_{t\in R}|R|^{-1}(h_t(S\cup\{s\})-h_t(S)).$$

D. Quality-constrained coverage: retain provisional eligibility, prohibit repeated
canonical feature payloads, and satisfy a declared minority quota first. Requested
quota q_b=floor(.5 b), capped by the number of available distinct minority feature
payloads. Record requested, feasible, unavailable and achieved counts. A capped
quota records unavailable support; it is never fulfilled by invented records.
While quota is unmet, consider only minority-literal-class candidates. Thereafter
consider all unused-feature candidates. Select lexicographically by:

1. Largest class-balanced region-coverage gain Delta C_bal(s|S).
2. Fewest already selected neighbors with distance <= tau=.01.
3. Largest minimum distance to previously selected candidates.
4. Smallest frozen Phase-4 uncalibrated max percentile U_s.
5. Stable source order and occurrence ID.

The Phase-4 concern tie-break is a descriptive quality proxy, not P(INVALID).
All four methods use the same primary eligibility and budgets. D adds explicit
redundancy/quota constraints and a different coverage weighting; it does not
establish that coverage, diversity and minority support can all be maximized
simultaneously. No universal superiority claim is appropriate.

Numerical ordering keys are rounded to 12 decimal places for reproducible ties.
Marginal gains and cumulative objectives retain full precision in trace output.
For A/B the trace's marginal coverage is a diagnostic, not the optimized objective;
for C/D it is the respective selection objective. Stop at exact budget or explicit
candidate/distinct-feature exhaustion. Do not stop merely because coverage gain
is zero: sample-count matching still matters. Record shortfall and stopping reason.
A seed is retained for identity but no randomized procedure uses it.

## Dataset-level metrics

For n selected occurrences: unique occurrences, unique canonical full payloads u,
unique feature payloads and exact duplicate rate 1-u/n (0 for empty selections).
With a_i=min_{j!=i} d(s_i,s_j), near-duplicate rate is
$$n^{-1}\sum_i1[a_i\le\tau],\quad \tau=.01.$$
It includes exact feature duplicates. Report null for n<2, rather than interpreting
absence of a neighbor as infinite diversity. Report min/q25/median/q75/max and
mean for nearest TRAIN distances, nearest selected distances and all unordered
selected pair distances. Singleton/empty summaries have zero finite observations.
No distance threshold is interpreted as physical invalidity. Radii/tolerances are
predeclared descriptive design parameters and are not TEST-tuned.

## Artifacts, audit and reproducibility

Each constructed bundle contains artifact.json, dataset.csv, dataset.json,
selection-ledger.csv, audit.json and FINALIZED.json. Selected records preserve
original payloads, labels, occurrence IDs, hashes, order and source locators.
The full per-source-occurrence ledger records eligibility, selected rank or defer
reason, and Phase-4 decision fingerprint. Trace records objective keys, marginal
and cumulative coverage, distance, quota phase and selection reason.

Provenance binds the exact crosswalk, specification, Phase-4 bundle/policy,
M2 input, TRAIN reference, candidate pool, configuration, source code and selected
content. Each study includes sealed TRAIN-only reference bundles. Runtime is
recorded in the study manifest, outside deterministic dataset identities.
Canonical fingerprints use the repository sorted compact JSON algorithm.
Guarded writers refuse differing overwrites; identical writes are resumable.
Study resume rechecks source-bound datasets rather than accepting cached claims.

Audit reloads source bindings/geometry and reconstructs the entire deterministic
recipe. Require exact equality of payloads, labels, identities, selected order,
budget/quota accounting, metrics, defer reasons and provenance. Duplicate occurrence
IDs, missing fields/classes, structural rejects, source substitutions, stale
references and changed artifacts fail explicitly. Export bytes are covered by the
storage seal. Nothing is silently repaired. Exact-value overlap with historical
TEST is disclosed as a pre-existing source limitation, not erased or newly used.

A fresh full replay must reproduce all 51 dataset fingerprints and selected lists;
outer manifest fingerprints may differ because runtimes differ. Cross-budget
prefix/set stability is reported, with quota-dependent changes allowed for D.
Policy sensitivities report Jaccard selected-set overlap with the main middle-budget
D selection; the denominator is union size (null if empty). Overlap is not accuracy.

Reproduction from a Phase-5 checkout, using existing optional research dependencies:

```powershell
$env:PYTHONPATH = "$PWD/src"
python -m rcqasyn phase5 study artifacts/reports/phase5/study-reproduction-v1 --source-root 'D:/Github Repos/quality-aware-synthesis-lab'
python -m rcqasyn phase5 audit artifacts/reports/phase5/study-reproduction-v1/datasets/Abalone19-quality-coverage-b56 --source-root 'D:/Github Repos/quality-aware-synthesis-lab'
python scripts/report_phase5.py --study artifacts/reports/phase5/study-reproduction-v1 --output artifacts/reports/phase5/report-reproduction-v1
```

## Limits and deferred decisions

Geometric coverage does not establish record validity, classifier utility,
calibrated risk, novelty or dataset superiority. No utility study is conducted;
TRAIN-only validation and untouched TEST evaluation require a separately approved
protocol. All human approvals remain pending. Target mappings, physical meanings
and cross-field semantics remain unresolved. Selected-cohort bias, literal-label
uncertainty and historical TRAIN/TEST exact-value overlap remain limitations.
The report decision ledger records personal label review, scientific acceptance,
future utility protocol, radius/quota justification and eventual claims. Phase 6
would require a separately authorized bounded-repair protocol with explicit budgets,
source-backed permitted edits, provenance, reevaluation and independent scientific
assessment. No repair or Phase-6 method is implemented here.
