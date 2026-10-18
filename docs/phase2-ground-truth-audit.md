# Phase 2: source reconciliation and annotation preparation

Status: PENDING_INDEPENDENT_VERIFICATION. These derivatives are not approved
ground truth. No real cohort agent proposals, human labels or official B2/B3
comparison have been produced.

## Frozen inputs and identity

Phase-1 freeze: 341fc2ce647c180b0f4a34fdbdeb49a0acfdcbcc.
Historical generation, admission, metrics, splits, seeds, prompts and reports
remain immutable. New outputs live under artifacts/reports/phase2/VERSION/.
The default is gate-a-v3. Completed derivatives are sealed and refuse overwrite.
Changed inputs require a new version. Raw datasets remain ignored local inputs.

legacy-occurrence-id-v1 fingerprints a canonical descriptor containing execution
ID, manifest checksum, repository-relative raw artifact, artifact checksum and
one-based physical occurrence ordinal. The SHA-256 identifier starts with occ-.
Source trace line, response ordinal and item index are witnesses. Reused provider
call IDs are not durable attempt identities.

The crosswalk separates occurrence ID, legacy candidate ID, full payload hash,
original projected canonical hash and duplicate content. Identical content in
different occurrences is retained. The projected hash uses the existing historical
canonicalizer; the full hash covers the entire parsed object. Reconstruction
never reads the corrected review CSV.

Generation traces must uniquely match recorded alias, response, seed, requested
class, item and payload. Ordered B1/B2/B3 decisions, accepted candidate streams,
B2 evidence blocks and B3 prompt/result witnesses must agree. Ambiguous or missing
evidence fails closed. Validation reconstructs every field from original sources.

## Cohort and row 94

review-cohort-v2 preserves 120 payloads, selection order and the fixed 40-row
overlap without resampling. Logical CSV row 94 is data record 93. Its payload
belongs to page-blocks0 occurrence 1; its historical hash, seed, batch and two
nearest-TRAIN distances belonged to occurrence 41.

The corrected row takes source-backed metadata from occurrence 1. Complete
conflicting original values, field changes and locators remain in the audit.
Original CSV and blind packets remain byte-identical. The overlap preserves
membership/order, including this corrected binding.

Historical CSV exports changed response LF line endings to CRLF. Matching
normalizes CRLF to LF only for witness comparison; original bytes and response
checksums remain protected. A diagnostic target_class nan sentinel exported as
blank is documented separately from foreign-occurrence corrections.

Selection roles remain historical selection evidence; corrected requested class
comes from the source trace. Selection was nonrepresentative and historical
ID-only diagnostic lookup affected strata. Results cannot estimate population
accuracy.

## DatasetSpecification v1 drafts

All three core specifications validate exact raw SHA-256 against acquisition
evidence, reconcile archived declarations with the raw header, check the unchanged
recorded split, and construct bounded TRAIN-only profiles. TEST/full-population
statistics and example rows are not fitted inputs. Whole-source checksums document
source identity only.

Rules are AUTHORITATIVE, INFERRED or UNVERIFIED. Only authoritative rules with
cited evidence may support hard rejection. Primitive declarations, field names and
binary tokens are source-backed. Observed numeric support, rarity and probability
are not universal laws. Duplicates, unseen TRAIN categories and outliers are not
automatically invalid.

Original multiclass-to-binary membership, physical meanings/units and cross-field
hard constraints are not fully established by archived documentation. The gap
report marks these RESEARCH_DECISION_REQUIRED. Dataset names do not prove target
mapping. New constraints require evidence and protocol approval. The source
spelling Lenght is preserved.

The prior forensic audit found page-blocks0 exact-value TRAIN/TEST overlap:
12 full-row groups, 26 TRAIN and 17 TEST rows. This is a documented limitation,
not automatic proof of upstream leakage. Membership remains unchanged.
Optional extension datasets remain missing and inactive.

## Annotation protocol and blindness

annotation-protocol-v1 permits VALID, INVALID and INDETERMINATE. VALID requires
sufficient evidence for a positive judgment without a substantiated applicable
authoritative violation. INVALID requires a specific supported violation.
INDETERMINATE is abstention and is never converted into INVALID.

Validity, uncertainty, redundancy and future contribution remain separate.
No Phase-3 validators or provider backend are added. Tools ingest evidence-backed
agent answers and never derive independent labels from B2/B3.

Public packets explicitly project blinded ID, payload, field definitions, allowed
authoritative evidence and known ambiguity. They exclude admission outcomes,
scores, thresholds, providers and prior judgments. The overlap is an intended
independent-review subset, not proof of a second review. Distribute only
public-packets. Keep private-map, cohort, crosswalk and evaluation artifacts
internal. Separate mapping storage is not encryption or an access-control system.

## Commands

Use Python 3.12 and confirm imports resolve to this worktree:

~~~powershell
$env:PYTHONPATH = "$PWD\src"
$env:PYTHONDONTWRITEBYTECODE = "1"
$python = "D:\Github Repos\quality-aware-synthesis-lab\.venv\Scripts\python.exe"
& $python -B -c "import rcqasyn; print(rcqasyn.__file__)"
$source = "D:\Github Repos\quality-aware-synthesis-lab"
& $python -B -m rcqasyn phase2 prepare --source-root $source --dry-run
& $python -B -m rcqasyn phase2 prepare --source-root $source
& $python -B -m rcqasyn phase2 validate --source-root $source
~~~

Preparation reconstructs all three P1 runs (601 occurrences), including the required
page-blocks0 200-occurrence crosswalk. It exports the corrected cohort, ledger,
before/after evidence, draft specifications/protocol, public 120/40 packets,
private mapping and historical integrity inventory. All commands accept --source-root for audited read-only evidence, while derivative
writes remain in the Phase-2 worktree. Git core.autocrlf=true changes historical
checkout bytes. The final v3 bundle binds to original audited main bytes, without
rewriting either checkout. The preliminary local gate-a-v1 and gate-a-v2 bundles are superseded:
it used checkout CRLF bytes and exposed an ordering-dependent ledger serialization
bug. Both are retained locally, excluded from Git, and must not be approved or used.
The second draft exposed rule-list ordering after JSON serialization. Final
preparation validates canonical serialized cohort/protocol/packets before
reserving outputs.

Phase-2 artifacts use Git -text attributes so committed blob bytes retain seals
across platform line-ending settings. Future CLI outputs, checkpoints and review
history must stay under the Phase-2 worktree artifact namespace.

Each object has a fingerprint
and guarded storage seal. Identical preparation is a validated no-op.

## Gate A: external approval

A separate personnel-independent verifier and supervisor must approve exact
cohort, ordered crosswalk and protocol fingerprints before real proposals.
No command generates an approval. The external typed JSON requires:

- cohort_fingerprint, crosswalk_fingerprints, protocol_fingerprint;
- supervisor_reference, supervisor_approval_provenance;
- independent_verifier_reference, independent_verification_provenance;
- implementation_owner_reference, personnel_independent true;
- decision APPROVED.

Owner and verifier references must differ. These are explicit external trust
records, not authentication or proof of actual independence. Approval must
really come from responsible humans/verifier; strings alone cannot establish it.

After Gate A the following commands are available. Required arguments are
positional. Use phase2 COMMAND --help for the complete interface:

~~~text
phase2 batches APPROVAL_JSON CHECKPOINT OUTPUT_BUNDLE --batch-size 10
phase2 submit APPROVAL_JSON ANSWERS_JSON AGENT_VERSION EXECUTION_ID CHECKPOINT
phase2 review-export CHECKPOINT OUTPUT_BUNDLE
phase2 review APPROVAL_JSON DECISIONS_CSV_OR_JSON CHECKPOINT HISTORY
phase2 analyze APPROVAL_JSON CHECKPOINT HISTORY OUTPUT_BUNDLE
~~~

Answer rows contain blinded_review_id, proposed_label, proposed_rationale,
supporting_evidence_ids and uncertainty_or_ambiguity. Submission binds source
identities from the private mapping, validates evidence, records AGENT/model/
execution identity and leaves human columns blank. Stable batches resume by
validated completed identity. Exact retries are idempotent; changed answers for
existing proposals cannot overwrite the originals.

## Human review and Gate B

The export includes original proposals, payloads and proposal fingerprints.
Edit human fields only; original sealed proposals remain intact. Submitted
decisions require review_row_id, occurrence_id, payload_sha256,
proposal_fingerprint, review_status, human_final_label, human_correction_note,
human_reviewer_reference and human_approval_provenance.

Use APPROVED with an explicit allowed final label, or UNRESOLVED with a blank/null
label. Untouched PENDING_HUMAN_APPROVAL rows are not approvals. Submit a reviewed
subset or explicitly mark unresolved decisions. Changed labels require correction
notes. Empty reviewer fields and file export never count as approval.

Corrections append separately sealed events with previous-event fingerprints and
source/proposal bindings. Original proposals and prior events remain intact.
Interior deletion/reordering and altered sealed contents fail validation.
Detecting deletion of a complete trailing suffix requires an independently retained
tip. Analysis retains the exact ordered history fingerprints.

Official analysis requires complete identity sets and explicit approval of every
final label. Latest unresolved decisions block execution. INDETERMINATE counts
remain separate from binary confusion denominators. Synthetic fixture provenance
cannot enter official CLI analysis.

Original B2/B3 admission booleans and B3 verdicts remain unchanged. The tool does
not reinterpret WARN, tune thresholds or reuse older duplicate-related admission
remapping. Reports bind approvals, proposals, crosswalks, protocol and final human
ledger/history. They include explicit confusion axes, false acceptance/rejection,
disagreements, error overlap, dataset/requested-class breakdowns and source-linked
failure cases. All selected-cohort findings remain exploratory.

## Verification and integrity

Run focused Phase-2 tests, pytest -q, ruff check ., pyright and git diff --check.
Synthetic offline fixtures exercise approvals and analysis; fixture supervisor
references and labels are test data only. No real approval is generated.

Original test-results/history.jsonl is frozen. Do not append Phase-2 checks through
the old recording script. Use a new Phase-2 verification namespace. Historical
file-set/hash checks intentionally fail if original evidence changes.

Gate A is preparation for external verification and cohort/protocol approval.
Gate B requires human label approval. Gate C requires independent final
verification and supervisor acceptance. No push, merge or Phase-3 work is authorized.
