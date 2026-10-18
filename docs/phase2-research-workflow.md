# Phase 2: streamlined supervisor-reviewed research workflow

Implementation scope approved by the supervisor on 2026-10-18, starting at
`e60f32efa8cca9a0037bf578347e4821558b0402` on
`phase2/ground-truth-dataset-spec`. Cohort/rubric approval and reviewed-label
confirmation remain separate mandatory checkpoints. No real labels are included
in this implementation checkpoint.

## Purpose and limits

This academic prototype uses explicit supervisor decisions and source-bound
CSV/JSON ledgers. Fingerprints detect changed or mismatched content; they do not
cryptographically authenticate a person, prove personal inspection, or resist a
malicious agent with the same permissions. The supervisor supplies the actual
approval and confirmation through the conversation or reviewed files. The agent
records that provenance verbatim and never invents a human approval.

Production `phase2 approval-import`, `phase2 analyze` and direct production
`authenticate_review` remain disabled. Research commands use distinct schemas and
always emit `production_approval=false` and `cryptographically_authenticated=false`.
No signing keys, enrollment provider or authentication infrastructure is added.
Synthetic diagnostic APIs retain their existing restrictions and behavior.

## Preserved preparation and dataset specifications

The immutable `artifacts/reports/phase2/gate-a-v3` bundle remains the preparation
source. All 601 source occurrences (200 page-blocks0, 201 Ecoli4, 200 Abalone19),
the corrected 120-row cohort, fixed 40-row overlap, row-94 reconciliation and
three dataset specifications are retained without edits or resampling. Logical
CSV row 94 (data record 93) binds to page-blocks0 occurrence 1; its original
payload and five corrected metadata fields remain documented in the cohort
bundle. Legacy identifiers remain aliases, not occurrence keys.

| Dataset | Raw records | Features | TRAIN / TEST | Source target tokens |
| --- | ---: | ---: | --- | --- |
| page-blocks0 | 5472 | 10 numeric | 4377 / 1095 | negative / positive |
| Ecoli4 | 336 | 7 numeric | 269 / 67 | negative / positive |
| Abalone19 | 4174 | 7 numeric, 1 nominal | 3340 / 834 | negative / positive |

These figures and exact source checksums are recorded in the preserved
specifications, acquisition records and frozen split manifests. Original feature
spelling, including `Lenght`, remains unchanged. Missing source `?` tokens remain
null; the specification's existing missing policy and split are unchanged. No
imputation, dataset acquisition, re-splitting or ML migration is performed.
Profiles used for annotation describe TRAIN only; TEST is not fitted or used as
annotation evidence. The documented page-blocks0 exact-value TRAIN/TEST overlap
remains a scientific limitation; this work does not repair historical membership.

Each source-bound specification documents source identity, binary task/tokens,
primitive types/categories, missing policy, evidence authority, TRAIN support,
frozen split provenance, applicability and ambiguities. The nine grouped gaps
(three per dataset) remain explicit: original multiclass-to-binary mapping,
physical field meanings/units, and cross-field hard constraints. The proposed
supervisor disposition is to retain those unknowns and avoid unsupported rules.
Dataset names cannot establish original target mappings. Numerical source bounds
and observed TRAIN ranges are descriptive support, not universal validity bounds.

`docs/datasets.md` and the sealed specification/protocol artifacts are fingerprinted
inputs and are not rewritten by this documentation update. New source evidence or
changed scientific policy requires a new preparation/rubric version and renewed
supervisor approval; do not patch the frozen bundle in place.

## Three mandatory human checkpoints

1. **Cohort and exact rubric approval, before real proposals.** Inspect the
   `research-scope-v1/checkpoint.md` and `rubric.json`, the corrected cohort and
   original evidence. Explicitly approve the exact cohort, ordered crosswalk,
   protocol, specifications and research-rubric fingerprints and state the
   disposition of unresolved scientific questions. Scope approval alone cannot
   pass this gate. The pending JSON template is deliberately invalid as approval.
2. **Personal inspection of all 120 proposals.** After the first approval, the
   agent generates blinded evidence-backed proposals. Review a working copy of
   `review.csv` or `review.json`; inspect and correct every row, set
   `human_review_status=REVIEWED`, explicitly set `human_final_label` to VALID,
   INVALID or INDETERMINATE, and supply your reviewer reference on every row.
   Explain changed labels in `human_correction_note`, citing supporting evidence
   where needed. Do not edit payload, identities, original proposal or fingerprints.
   Review all rows even where the final label matches the proposal.
3. **Exact reviewed-ledger confirmation, before analysis.** Return the reviewed
   file. Import validates complete unique membership, all source/proposal fields,
   explicit decisions and the named supervisor. It produces a new immutable ledger
   and presents its fingerprint. Personally confirm that exact fingerprint and
   explicitly authorize its use in research analysis. An import alone never runs
   analysis. The pending confirmation template is deliberately invalid.

The agent may transcribe an explicit human statement into the corresponding JSON
record, preserving its conversation/file reference as provenance. This is a
research record of authorization, not an identity authentication boundary. Known
proposing-agent identities and the implementation owner's scope self-approval are
rejected; arbitrary strings still cannot prove human identity.

## Ledger schemas, versions and corrections

`research-scope-approval-v1` binds population, cohort, ordered crosswalks, protocol,
specifications and exact research rubric, with supervisor/implementation-owner
references, actual approval provenance and scientific decisions. Its purpose is
COHORT_AND_RUBRIC_ONLY; it is not approval of labels. It replaces no production
contract and requires no fabricated personnel-independent Gate-A attestation.

`agent-proposal-batch-v1` research batches retain AGENT provenance, pending human
status and null human fields. Batches also bind the research scope and rubric;
existing production-style proposal checkpoints cannot be silently promoted. Exact
retries are idempotent; changed answers must not overwrite existing proposals.
Blinded answers contain only the blinded ID, proposed label/rationale, applicable
authoritative evidence IDs and uncertainty. Machine controls are excluded.

`research-review-ledger-v1` binds the complete proposal set and source inputs. Its
editable CSV/JSON exports include the full payload, original row locator, stable
identities and proposal fingerprint alongside separate human columns. CSV stores
payload and evidence arrays as JSON cells. Import accepts those exported row lists,
not arbitrary approved claims or a pre-filled signed-ledger schema. Pending or
blank decisions, missing/duplicate/foreign rows, altered context, unsupported
labels and unexplained corrections fail. INDETERMINATE is an explicit reviewed
label, not an incomplete row.

Use a fresh output directory for every import. Corrections pass the previous
reviewed bundle with `--previous-ledger`; the next ledger records an incremented
version and previous fingerprint. Prior files remain immutable. Every correction
changes the current ledger fingerprint and needs fresh explicit confirmation.
These links record history; they do not enforce freshness against an actor able
to replace all files with the same permissions. Working review copies should live
outside sealed export bundles; do not edit `artifact.json` or `FINALIZED.json`.

`research-ledger-confirmation-v1` requires the exact reviewed ledger and scope
fingerprints, matching supervisor reference, explicit decision
CONFIRM_ALL_REVIEWED_LABELS_FOR_RESEARCH_ANALYSIS and actual confirmation provenance.
No command manufactures that decision for the supervisor.

## Commands and reproducibility

Use Python 3.12, the Phase-2 implementation worktree and its `src` on PYTHONPATH.
Here SOURCE_ROOT denotes the preserved audited evidence checkout when raw data are
not present in the implementation checkout. Required arguments are positional;
append `--source-root SOURCE_ROOT` to each command in that setup. Use `--help` for
options. All generated output/checkpoint paths stay under
`artifacts/reports/phase2/` in this worktree, with a new directory per version.

~~~text
python -B -m rcqasyn phase2 research checkpoint artifacts/reports/phase2/research-scope-v1
# STOP: explicit supervisor approval of cohort and exact rubric
python -B -m rcqasyn phase2 research batches SCOPE_JSON CHECKPOINT REQUEST_BUNDLE
python -B -m rcqasyn phase2 research submit SCOPE_JSON ANSWERS_JSON AGENT_VERSION EXECUTION_ID CHECKPOINT
python -B -m rcqasyn phase2 research review-export SCOPE_JSON CHECKPOINT REVIEW_BUNDLE
# STOP: supervisor personally inspects and corrects all rows in a working CSV/JSON copy
python -B -m rcqasyn phase2 research review-import SCOPE_JSON CHECKPOINT REVIEWED_ROWS PROVENANCE REVIEWED_BUNDLE
# STOP: supervisor explicitly confirms the imported reviewed-ledger fingerprint
python -B -m rcqasyn phase2 research analyze SCOPE_JSON CHECKPOINT REVIEWED_BUNDLE CONFIRMATION_JSON RESULT_BUNDLE
~~~

The result schema is `supervisor-reviewed-research-analysis-v1`. It records the
implementation commit, Python/dependency versions, source checksums, rubric,
approval/confirmation, proposal set and reviewed-ledger fingerprints. Commit the
implementation before analysis so HEAD describes the executed code. Result bundles
include the report, comparisons CSV, scope approval, proposals, reviewed ledger
and confirmation. Preserve the preparation bundle, proposal checkpoint and raw
source files too. Replay the recorded command inputs from the recorded commit and
dependency environment into a fresh output directory. Identical inputs/environment
produce identical result content; no timestamps are injected into analysis.

The shared comparison function retains historical B2/B3 admission booleans and
B3 verdicts, including abstentions. INVALID is the positive class; false acceptance
is accepting an INVALID row (FN), false rejection is rejecting a VALID row (FP).
INDETERMINATE rows are reported separately and excluded from binary denominators;
a zero denominator gives null rates. Outputs include label/verdict counts,
overall/dataset/requested-class breakdowns, disagreements, shared errors and
individual cases. B1/B2/B3 algorithms, thresholds, WARN handling, seeds, generation
and splits remain frozen. The nonrepresentative selected cohort supports an
exploratory audit, not population-wide accuracy. Retaining the 40-row overlap does
not establish a second independent rater or permit invented agreement statistics.

## Closeout

Use targeted tests during development. After actual reviewed-label confirmation,
run research analysis and reporting, complete the scientific decision record,
run the full suite once at final closeout and request one independent final
verification. Record that outcome and any limitations. Make local Conventional
Commits only. No push or merge until final supervisor approval. Phase-3 methods,
new datasets, authentication deployment and ML migration are outside this scope.

## Implementation checkpoint validation (2026-10-18)

- New synthetic workflow tests plus existing annotation/analysis tests: 38 passed.
- Source-bound real checkpoint content test: 1 passed; no labels generated.
- Existing CLI discovery regression check: 1 passed.
- Ruff on the changed Python files and Pyright on the four changed/new source
  modules passed. No full-suite run or broad security audit was performed.
- The actual checkpoint command validated the preserved source preparation,
  dataset specifications and historical inventory before writing its separate
  pending approval package. All 330 pre-existing implementation artifact files
  remained byte-identical; only the new five-file research checkpoint was added.
- The first sandboxed targeted run could not create the Windows hard links used
  by the existing immutable writer. The same targeted tests passed with the
  required filesystem permissions; no storage behavior was weakened.

These checks establish implementation readiness for cohort/rubric inspection.
They do not approve the real cohort, rubric, labels or final Phase-2 results.
