# Phase 6: bounded repair and consolidated final research evaluation

Parent: `7276fb150eda6248eaf64512eb9d197dfc5106b2`.
Engineering experimental-freeze preparation is distinct from scientific approval.
Phases 2--6 remain scientifically unapproved; all 120 human-final labels are pending.

## Approved repair operator

Policy `integer-half-even-max3-v1` applies only to source-declared integer features
with finite nonintegral numeric primitives and substantiated authoritative defects.
Represent the JSON numeric value by Decimal(str(value)), then round to the nearest
integer with ROUND_HALF_EVEN. This explicitly defines exact positive and negative
half-integer ties; it does not rely on Python's implicit binary-float rounding.
For feature x, r(x) is the nearest integer with even-integer tie-breaking:

$$|r(x)-x|\le 0.5,\quad |J|\le3,$$

where J is the set of edited integer-declared fields. Integral values, including
10.0 and signed floating zero, are unchanged. More than three required corrections
refuses the whole record rather than partially editing it. No class, missing
feature, null, category, extra field, rare value or statistical outlier is repaired.
Other unresolved authoritative defects make the record ineligible for complete
integer-only repair. Source-observed numerical ranges are not universal physical
bounds. An independently authoritative structured numeric bound is checked before
repair; an unsupported authoritative postcondition causes refusal rather than
invented compliance. This guard is not a new evidence family.

Original occurrence identity and payload remain immutable. Derived identity is
`m6:` followed by the canonical fingerprint of parent occurrence, repair policy,
specification fingerprint and repaired payload. Each edit preserves original value,
new value, Decimal change, field declaration, applicable rule and justification.
Applying the policy again to an already integral, compatible result performs no
new edit. Original proposals reproduce identically.

## Audit and frozen reevaluation

Audit all 601 authoritative occurrences. Count missing class, missing features,
nonintegral integer fields, primitive/category problems, simultaneous defects,
unsupported evidence and repair eligibility separately. Category counts can overlap;
field-level violations are not record counts. Preserve NOT_NEEDED records separately
from REPAIR_INELIGIBLE structural rejects. Record REPAIR_APPLIED/REPAIR_FAILED and
post-repair structural status, never human VALID.

Restore M2 from saved TRAIN rows, numerical scales/spans, category dictionary,
center and precision matrix. Do not invoke the model constructor or fit covariance.
Recompute TRAIN self-scores only for the existing resubstitution diagnostic using
the saved coefficients. The restored model replays original evidence, then scores
derived records. Structural validity, local neighbor evidence and global consistency
use the unchanged Phase-3 implementation and original TRAIN reference.

For each derived score, evaluate the Phase-4 mid-distribution function against the
original frozen candidate-score reference:

$$u(s)=(\#\{r<s\}+\tfrac12\#\{r=s\})/N.$$

Derived records never become reference members. No reranking/refitting occurs.
Use the frozen combined-review q=.90 policy and its existing precedence: supported
structural rejection, required-evidence abstention, partial-structure/statistical
review, otherwise provisional pass. This is descriptive shadow admission, not
calibrated risk or human validity. Preserve every original pre-repair decision.

## Controlled M7 interaction

Reuse all four Phase-5 selection functions and objectives unchanged, at middle
budgets Abalone19=56, Ecoli4=70, page-blocks0=49. Compare original and original-plus-
derived candidate versions. Derived versions enter only when post-repair provisional
and complete, with original class unchanged. Original rejected versions remain
ineligible. Assert unique source-parent IDs in each selected set, so an original
and its repaired version cannot count twice. Distinct physical parents with equal
payloads remain separate occurrences; exact/near redundancy is still reported.

There are 24 constructions (3 datasets x 4 strategies x 2 conditions). The original
condition must reproduce each corresponding frozen Phase-5 selection and all its
metrics exactly. New artifacts use an M6/M7 derivation-aware schema; they do not
pretend derived IDs occur in the original authoritative crosswalk. Bind the raw
crosswalk plus parent/derivation registry, frozen policy, TRAIN and configuration.

## Utility audit and predeclared comparison

The original M1 runner constructs a DataFrame directly from candidate.data, with
no requested_class injection (runner.py `_persist_baseline`). Consequently missing
class can become NaN and then the literal string 'nan' in the frozen `_fit_score`.
Historical unfiltered utility is preserved as historical evidence, not endorsed as
a complete-record comparison. New B1/B2/B3 controls are explicitly named
B1/B2/B3-structural-complete: recorded acceptance intersected with authoritative-
structure-compatible complete payloads. They are not the unchanged raw baselines.

Use the frozen `rcqasyn.metrics.utility._fit_score` implementation, its imputer,
StandardScaler/one-hot encoder and two estimators from `resolve_estimators(42)`:
logistic regression (liblinear, max_iter=300), random forest (50 trees). Fit every
preprocessor only on its corresponding training population. No classifier,
threshold, seed or metric definition is changed. Spec-defined positive literal is
used; this is task-class evaluation, unrelated to VALID/INVALID review labels.

The complete committed comparison set is fixed before TEST scoring: per dataset,
2 TRTR results; 3 filtered controls plus 8 fixed-budget M7 sources, each with 2
classifiers x 2 synthetic regimes. Total 138 result rows, including unavailable
cases. TRTR trains on REAL TRAIN. TSTR trains purely on synthetic selected records;
if fewer than two literal classes exist, report unavailable. HYBRID_MINORITY trains
on REAL TRAIN plus only synthetic minority-literal-class records; no synthetic
minority means unavailable, not a relabeled TRTR result. No invalid records are
added merely to make classification possible.

The historical generator and frozen M2/M7 design consume full TRAIN. Therefore a
new inner TRAIN holdout from this fixed pool would not be an independent validation
study. We do not claim such a validation result. Instead the committed fixed
comparison set is scored on the existing outer TEST only for descriptive utility.
TEST has already been used by Phase 1, so it is not called untouched or independent
confirmatory evidence. No TEST result changes candidates, repair, selection,
thresholds, budgets, models or hyperparameters. Existing TRAIN/TEST exact-value
overlap is a disclosed source limitation, not silently removed after inspection.
An exact replay is reproducibility, not another independent seed or uncertainty
replicate. No significance test or confidence interval is claimed.

## Frozen task metric definitions

For positive-literal confusion counts TP,FP,FN,TN:

$$F_1=2TP/(2TP+FP+FN),\quad BA=\tfrac12(TP/(TP+FN)+TN/(TN+FP)),$$
$$MCC=(TP\,TN-FP\,FN)/\sqrt{(TP+FP)(TP+FN)(TN+FP)(TN+FN)}.$$

Average precision is the sklearn step integral
$$AP=\sum_k(R_k-R_{k-1})P_k.$$
The existing pr_auc field is an alias of average_precision, not trapezoidal PR
area. AUROC is the probability that a positive gets a higher score than a negative,
with half credit for ties. Undefined cases and reasons retain frozen sklearn/
repository behavior, including finite/null metric handling. No official validity
precision/recall, false acceptance, false rejection or human agreement is computed.

## Reproducibility and outputs

Commands (fresh output versions, source root fixed at original main):

```powershell
$env:PYTHONPATH = "$PWD/src"
python -m rcqasyn phase6 core artifacts/reports/phase6/core-new-v1 --source-root 'D:/Github Repos/quality-aware-synthesis-lab'
python -m rcqasyn phase6 utility artifacts/reports/phase6/core-new-v1 artifacts/reports/phase6/utility-new-v1 --source-root 'D:/Github Repos/quality-aware-synthesis-lab'
python scripts/report_phase6.py --core artifacts/reports/phase6/core-new-v1 --utility artifacts/reports/phase6/utility-new-v1 --output artifacts/reports/phase6/report-new-v1
```

Core records bind all parents, original payloads, derived payloads, edits, original
and new evidence/actions, source/model/configuration/reference identities and
canonical substantive hashes. Guarded writers seal fresh versioned bundles.
Outer runtime-containing fingerprints can differ across replay, while repair
records, construction fingerprints and utility content must match. M9 registry
and final reproduction manifest retain source/split identities, generation runs,
methods/configurations, selected/evaluation populations, seed/repetition meaning,
metrics, unavailable reasons, dependency versions and artifact hashes.

All scholarly references in the final draft are verified against primary records;
old manuscript v0.1 remains preserved and is superseded only by the new draft.
Human-label review, unknown domain constraints, calibration eligibility, scientific
acceptance, generalization claims and author/institutional declarations remain
explicit pending decisions. No new generation, validator family, calibration
method, authentication system or Phase 7 is introduced.

Read-only source/derived audit: `python -m rcqasyn phase6 audit artifacts/reports/phase6/core-v1 --source-root "D:/Github Repos/quality-aware-synthesis-lab"`. It verifies every source parent, approved proposal, restored post-evidence, selected payload/class, admission, parent exclusivity, trace order, duplicate/budget accounting and substantive identity without fitting.
