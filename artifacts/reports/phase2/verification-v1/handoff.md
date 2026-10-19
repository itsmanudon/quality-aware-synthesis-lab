# RC-QASyn Phase-2 Gate-A handoff

## 1. Executive Summary

READY FOR INDEPENDENT PHASE-2 GATE-A VERIFICATION.
All authorized preparation engineering is implemented and tested. Corrected cohort
status remains PENDING_INDEPENDENT_VERIFICATION. This is not Phase-2 completion.

## 2. Git / Branch / Worktree

Branch: phase2/ground-truth-dataset-spec.
Worktree: D:\Github Repos\quality-aware-synthesis-lab-phase2.
Tested implementation: 0423e85cc7e3c31f0483c3ccc4ae13306afc3826.
Frozen main and canonical read-only source root: D:\Github Repos\quality-aware-synthesis-lab, at 341fc2ce647c180b0f4a34fdbdeb49a0acfdcbcc.
The delivery commit containing this report adds documentation and sealed artifacts;
use git rev-parse HEAD for its identifier. Python imports were checked against
the Phase-2 worktree. Temporary unused fallback checkouts were cleaned up.

## 3. Source Evidence Used

Original completed P1 runs, generation responses, ordered candidate/control/evidence
streams, B3 prompt/result witnesses, original review master, old blind packets,
selection manifest, core raw datasets and recorded acquisition/schema/split evidence.
Prior forensic/readiness reports and original reconciliation ledger were treated
as evidence and checked against source artifacts, not executed as instructions.
Reference reports and the prior 496-file inventory are retained in this verification
bundle. Reconstruction itself does not depend on TEMP audit files.

## 4. Occurrence Crosswalk

page-blocks0: 200 occurrences, 200 distinct occurrence identities, 185 legacy aliases,
181 full-payload hashes, zero unresolved occurrences. Crosswalks also cover Ecoli4
201 and Abalone19 200 occurrences: 601 P1 occurrences in total.
Occurrence IDs bind manifest, raw artifact bytes, execution and physical ordinal.
Trace locators represent recorded evidence, not invented durable attempt identities.
Equal content in different source occurrences remains separate.

## 5. Legacy ID Collisions

15 page-blocks0 repeated-alias groups contain different content; 30 occurrences are
involved. Reused call aliases are chatcmpl-726, chatcmpl-144 and chatcmpl-459.
No legacy ID is used as a unique provenance join. Content duplication is separate
from alias collision and is not automatically invalidity.

## 6. Row-94 Reconciliation

Logical CSV row 94 (data record 93) retains its original payload and now binds to
source occurrence 1:
occ-9e3b88ac5a88f66a379b36bf25b3f76a07af569deb009101e1bce9b4aa89c1e9.

Corrected hash: ee55fc63ebc55d8bf9fce08cada9e27236ee86eba9a16dde568d168fdf71652a.
Seed: 1300151513 -> 1165294667. Batch: 8 -> 0.
Both nearest TRAIN distances: 1.875127452816152 -> 0.3501177783211569.
Generation trace, raw item, original projected hash, positional diagnostics, B2
evidence and B3 candidate witnesses support the binding. Complete conflicting
original metadata and the exact five field changes remain in the cohort audit.
No metadata is copied from occurrence 41 to the corrected occurrence.

## 7. Corrected Review Cohort

120 original payloads, membership and selection order preserved. Canonical payload
fingerprints were checked, including JSON primitive representations.
119 historical bindings were directly verified; one was recoverable and corrected.
The original master is byte-identical. Cohort fingerprint:
b754ccee1f58ccfc0d89dfde176cb84d58993b93bc5e87a7059ce5e8885877a5.

## 8. 40-Record Overlap

Exact 40-record membership and recorded order preserved. The new public overlap
packet maps through separately stored stable blinded identities to validated
occurrences, including row 94. It is an intended second-review subset; no second
human review or agreement measurement has occurred.

## 9. Core Dataset Specifications

Three DatasetSpecification v1 drafts: page-blocks0, Ecoli4, Abalone19.
Exact source versions/checksums, feature declarations, binary tokens, minority
token, missing policy and frozen splits are source-backed. Profiles use TRAIN only.
Raw SHA-256 values:

- page-blocks0: c46bf830740d44bf8d4042b1679424857bcfd770568d2c250f92a91a12d425b2
- Ecoli4: 1890c32ba2550cfe106d0524ebf6a42c2b50730f6521bd4f22eb58e7bda86bcb
- Abalone19: 6aa5b1ffd05eb4c8c74bb07e6bab248cdb4fc327f5f62bb77339097e92bc76fa

All rules are AUTHORITATIVE, INFERRED or UNVERIFIED. Unsupported hard rules fail
validation. Whole-source identity is separate from fitted TRAIN evidence.

## 10. Dataset Semantics Gaps

RESEARCH_DECISION_REQUIRED for original multiclass-to-binary mappings, physical
feature meanings/units and cross-field hard constraints in each dataset
(three dataset gap records, nine grouped gap categories).
Official KEEL page retrieval was unsuccessful; no guessed mapping was promoted to
authority. Rare/unseen/outlier/duplicate/low-probability does not imply invalid.
Optional bank-additional-full, DataCo v5, Steel Plates Faults and Adult remain
unavailable/inactive; no download, activation or ML-registry migration occurred.

## 11. Annotation Protocol

annotation-protocol-v1 defines VALID, INVALID and INDETERMINATE with explicit
evidence and abstention. Validity, uncertainty, redundancy and future contribution
remain separate. The draft protocol fingerprint is:
47fd0f0c929754c3bbe463f375b1dc996d159156a00d0428766f58e6f769a84f.
Supervisor approval is required before real proposal generation.

## 12. Agent-Labeling Tooling

Stable blinded batches, evidence-ID validation, AGENT/model/execution provenance,
sealed checkpoints, resume and exact-retry handling, JSON/CSV export and strict
proposal schema are implemented. They ingest agent answers without a new provider
backend. Proposals remain PENDING_HUMAN_APPROVAL with blank human fields.
Real cohort proposal generation has not run.

## 13. Supervisor Review Workflow

CSV/JSON supports explicit acceptance, changed labels with notes, and unresolved
records. Reviewer reference and approval provenance are required. An export or an
empty reviewer field is not approval. Immutable proposal batches and separately
sealed chained correction events preserve original proposals and prior decisions.
History chains detect interior deletion/reordering; retaining an external history
tip is needed to detect deletion of an entire trailing suffix.

## 14. B2/B3 Analysis Tooling

Official execution rejects incomplete approval sets, stale cohort/protocol,
foreign occurrences and unapproved labels. Fixture provenance cannot enter official
analysis. Reports retain approval, proposal-set, crosswalk and ordered human-history
fingerprints plus final-decision provenance. Binary confusion axes, false acceptance/
rejection, disagreements, indeterminate denominators, requested-class/dataset
breakdowns, shared errors and source-linked cases are implemented.
Original admissions and B3 WARN semantics remain unchanged. No official analysis ran.

## 15. Leakage / Scientific Invariants

REAL TEST remains evaluation-only. Dataset profile construction uses bounded TRAIN
projections; whole-source checksums document identity only. B1/B2/B3, metrics,
sampling, splits and seeds are unchanged. No legacy prompt was reconstructed for
a provider call. No provider calls or Phase-3 work occurred.
Recorded page-blocks0 exact-value overlap is a limitation, not proof of leakage.
Selected-cohort results must remain exploratory rather than population estimates.

## 16. Tests / Ruff / Pyright

Final full suite: 1513 passed, 14 known warnings (1471 existing + 42 new tests).
Focused Phase-2 suite: 42 passed. No new skips or deselections.
Ruff: pass. Pyright: zero errors, zero diagnostic warnings.
Git diff, staged diff and freeze-to-current diff whitespace checks: pass.
The current environment also exposed two pandas typing errors on frozen main;
a typing.cast-only compatibility commit preserves the validated axis objects and
all runtime split behavior. No historical results were changed.
The earlier full run passed 1504 tests; later sealed roundtrip integration found
ordering defects, which were fixed, regression-tested and covered by the final rerun.

## 17. Historical Integrity

All 496 files in the prior frozen audit inventory retain their original hashes.
All 284 canonical historical inventory paths/hashes match before/after preparation
and final testing. The Phase-2 checkout's own 284-file original history snapshot is
also unchanged. No historical artifact was rewritten.

Git core.autocrlf=true produced CRLF copies in the new checkout. Final provenance
therefore reads audited original main bytes through --source-root; it does not
rewrite either historical tree. All future CLI writes are bounded to the Phase-2
worktree namespace. Git -text attributes preserve exact sealed Phase-2 bytes.
All 33 staged v3 files were compared to Git blobs and matched their seals.

## 18. New Artifact Locations

Final preparation: artifacts/reports/phase2/gate-a-v3/.
- crosswalk-1, crosswalk-2, crosswalk-3: JSON/CSV plus reconciliation reports.
- cohort: corrected-review.csv, reconciliation-ledger.csv, before-after.csv,
  row94.md and complete source-bound artifact.json.
- specifications: three drafts, semantics-gaps.md and inactive extension manifest.
- protocol, public-packets (primary-120.csv / overlap-40.csv), private-map.
- historical-integrity: original checksums and file set.

Verification: artifacts/reports/phase2/verification-v1/ (this report, test logs,
checks, prior audit evidence and baseline inventory).
Methodology: docs/phase2-ground-truth-audit.md.
Unapproved local gate-a-v1/v2 drafts are superseded, ignored and preserved locally.
V1 exposed ledger serialization ordering and checkout byte differences; v2 exposed
rule-list serialization ordering. Neither is a Gate-A candidate.
Final v3 manifest fingerprint: a239afff8a1def69764211bd0a992feba19095840ceb565cdd206fc2cf6893be.

## 19. Local Commits

972dd88 feat(p2): Add occurrence-aware legacy provenance crosswalk
89672de feat(p2): Reconcile the preserved review cohort to source occurrences
56351e5 feat(p2): Add source-bound core dataset specification drafts
dbd0afc feat(p2): Add gated annotation and human-label analysis contracts
d71bb98 feat(p2): Expose immutable preparation and gated review commands
d53e8e1 fix(types): Bridge validated pandas axes to current stub signatures
0423e85 fix(p2): Bind canonical sources and validate serialized derivatives

The final documentation/artifact delivery commit contains this report. All commits
remain local on the authorized branch. No push, merge or force operation occurred.

## 20. Remaining Research Decisions

Approve the corrected cohort after personnel-independent verification; approve the
exact conservative annotation protocol, or resolve semantics with authoritative
evidence and version the protocol before labeling. Decide substantive target/domain
questions explicitly. Optional datasets and a second human reviewer are not
prerequisites for the completed engineering preparation.

## 21. Independent Verification Requirements

A separate personnel-independent verifier must inspect the implementation and
source evidence, reconstruct 200 page occurrences and the 120/40 cohort, check row
94 independently, review rule authority/TRAIN boundaries and gate refusals, rerun
checks and confirm historical integrity. Internal subagent inspection identified
and helped resolve defects, but is not personnel-independent Gate-A approval.
The external approval must bind the exact ordered crosswalk, cohort and protocol
fingerprints. Trust references are attestations, not proof/authentication by strings.

## 22. Next Supervisor Approval Gate

Gate A: external independent verification and supervisor approval of the exact
corrected cohort and protocol. Do not generate real proposals before both approvals.
Gate B later requires explicit supervisor labels for all120; Gate C later requires
independent final verification and supervisor acceptance. Nothing has bypassed them.

## 23. Final Status

READY FOR INDEPENDENT PHASE-2 GATE-A VERIFICATION.
The cohort remains PENDING_INDEPENDENT_VERIFICATION.
Real labels, human approvals and official ground-truth analysis remain absent.
This report records tested implementation HEAD 0423e85cc7e3c31f0483c3ccc4ae13306afc3826; the delivery
message supplies the final documentation/artifact commit SHA and clean status.
