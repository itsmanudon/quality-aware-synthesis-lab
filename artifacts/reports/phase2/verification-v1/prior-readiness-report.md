# RC-QASyn Phase-2 Readiness Audit

Audit date: 18 October 2026, Asia/Calcutta. Repository: D:\Github Repos\quality-aware-synthesis-lab.

Strictly read-only: no source/data changes, branch/worktree, installation, download, experiment, annotation, provider call, scientific parameter change, commit, merge, push, or Phase-2 execution. Audit scripts, evidence and this report are outside the repository in a new Windows TEMP directory.

## 1. Executive Summary

**NO-GO — CRITICAL DATA / INFRASTRUCTURE BLOCKER**

The frozen implementation and all three core source datasets are usable. The branch is main, HEAD matches the requested freeze, the worktree is clean, source/archive hashes reconcile, all core registered loaders work, and recorded seed-42 splits and TRAIN profiles reproduce in memory.

A confirmed historical provenance contradiction prevents accepting the existing annotation cohort as source-bound ground-truth input. The page-blocks0 P1 run has 200 candidate occurrences but only 185 unique record IDs. Three external generation call IDs are reused. Review master row 94 combines one occurrence's candidate data with another occurrence's canonical hash. Both blinded exports preserve the inconsistent master. Current legacy readers and review-status checks accept these resources, so a successful read/status check does not establish end-to-end integrity.

This invokes the request's rule that a confirmed provenance contradiction is a critical blocker. It does not make read-only inventory impossible: P2.0 and provisional structural specification drafting can proceed safely after separate authorization. The affected cohort must not be frozen, labeled for evaluation, or joined to approved ground truth until its source-occurrence mapping is reconciled and approved.

Other gaps are classified independently: no explicit INDETERMINATE support, no structured agent-proposal/human-approval history, zero completed labels, absent expanded datasets, incomplete original-task semantic evidence, and absent local PDFs. Missing completed human labels and the optional ML repository do not cause this verdict.

## 2. Git / Environment State

| Check | Observed | Assessment |
| --- | --- | --- |
| Branch | main | PASS |
| HEAD / Phase-1 freeze | 341fc2ce647c180b0f4a34fdbdeb49a0acfdcbcc | Exact match |
| Verified implementation | a677dd6864162cbf0f0c52810a0d761a92e2e266 | No tree diff against HEAD |
| origin/main local ref | Same freeze SHA | No network fetch; server state not rechecked |
| Worktree | Empty porcelain output before/after | Clean |
| Python | CPython 3.12.11 | Matches >=3.12,<3.13 |
| Virtual environment | [.venv](<D:/Github Repos/quality-aware-synthesis-lab/.venv>) | Present; imports and all core loading work |
| Disk free | C: approximately 157.5 GiB; D: approximately 261.5 GiB | Enough for inventory/review derivatives |
| Secrets | OLLAMA_API_KEY absent in audit process; repository .env absent | No values printed; offline work needs neither |
| GPU | Not probed | Not required |

Installed dependency versions: rcqasyn 0.1.0, pydantic 2.13.5, PyYAML 6.0.3, typer 0.27.2, rich 15.0.0, numpy 2.5.2, scipy 1.18.1, pandas 2.3.3, scikit-learn 1.9.0, pytest 9.1.1, pytest-cov 7.1.0, ruff 0.16.5, pyright 1.1.411.

Expected modules are present under src/rcqasyn: datasets, baselines, generation, metrics, contracts, storage, experiments, cli and literature. Source functionality includes registry/loading/profiles, B1/B2/B3, replay, TRTR/TSTR, scientific/execution identity, guarded writers/seals, and human-audit tooling. Tests, configurations, data/manifests/raw files, canonical runs/reports, experiments, methodology docs, research workbook, manuscript and literature index/notes are present. The registered IDs are Abalone19, Ecoli4, page-blocks0 and the non-scientific dev-small fixture.

No full regression suite was run, as requested. Runtime checks used Python -B, pure readers and in-memory split/profile reconstruction. No experiment runner or output-writing CLI command was invoked. Existing validation commands are: .venv\Scripts\python.exe -B -m pytest -q -ra --tb=short -p no:cacheprovider --basetemp <fresh-TEMP>; ruff check .; pyright. These are available commands, not checks freshly passed by this audit.

docs/phase1-stabilization.md attests historical verification up to 1,222 full-suite and 1,124 focused cases. That is documentation evidence, not a newly executed freeze-SHA log. test-results/history.jsonl has two old 67/67 pass records at 482a304 and a later 97-pass/1-failure, exit-code-1 record at 3179c03 that nevertheless says status=ok. Do not use this stale record to claim a current freeze pass or failure. The supplied independent freeze verification is accepted as context; its full final handoff transcript was not located in these test-history files.

Documentation does not uniformly describe the current freeze: generation-protocol.md says array-only parsing while prompt/config/source v2 support a records object; research-plan.md describes B1–B3 as future M0.1 work; the workbook says core datasets are not downloaded. Current code/config/data take precedence over historical planning prose. No documentation was repaired.

## 3. Core DS Dataset Inventory

Version for each core dataset is the local content-identified, unpartitioned official KEEL imbalanced archive. No independent numbered release is recorded. Acquisition metadata records 29 August 2026. Checksums below identify extracted .dat bytes; the local archives were also checked.

| DATASET | VERSION | LOCAL PATH | ROWS | FEATURES | MINORITY LABEL | IMBALANCE RATIO | SOURCE CHECKSUM | REGISTERED | LOADABLE | SPEC READY | STATUS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| page-blocks0 | KEEL archive; SHA-pinned | [D:\Github Repos\quality-aware-synthesis-lab\data\raw\page-blocks0\page-blocks0.dat](<D:/Github Repos/quality-aware-synthesis-lab/data/raw/page-blocks0/page-blocks0.dat>) | 5472 | 10 | positive | 8.78890877 | c46bf830740d44bf8d4042b1679424857bcfd770568d2c250f92a91a12d425b2 | Yes | Yes | Partial; v1 absent | AVAILABLE |
| Ecoli4 | KEEL archive; SHA-pinned | [D:\Github Repos\quality-aware-synthesis-lab\data\raw\ecoli4\ecoli4.dat](<D:/Github Repos/quality-aware-synthesis-lab/data/raw/ecoli4/ecoli4.dat>) | 336 | 7 | positive | 15.80000000 | 1890c32ba2550cfe106d0524ebf6a42c2b50730f6521bd4f22eb58e7bda86bcb | Yes | Yes | Partial; v1 absent | AVAILABLE |
| Abalone19 | KEEL archive; SHA-pinned | [D:\Github Repos\quality-aware-synthesis-lab\data\raw\abalone19\abalone19.dat](<D:/Github Repos/quality-aware-synthesis-lab/data/raw/abalone19/abalone19.dat>) | 4174 | 8 | positive | 129.43750000 | 6aa5b1ffd05eb4c8c74bb07e6bab248cdb4fc327f5f62bb77339097e92bc76fa | Yes | Yes | Partial; v1 absent | AVAILABLE |
| Bank Marketing | bank-additional-full requested | No file found | N/A | N/A | Unverified | N/A | Unavailable | No | No | No | MISSING |
| DataCo Smart Supply Chain | v5 requested; unverified locally | No file found | N/A | N/A | Unverified | N/A | Unavailable | No | No | No | MISSING |
| Steel Plates Faults | Unspecified | No file found | N/A | N/A | Unverified | N/A | Unavailable | No | No | No | MISSING |
| Adult | Optional; unspecified | No file found | N/A | N/A | Unverified | N/A | Unavailable | No | No | No | MISSING |

All three core files are KEEL .dat. Registered target is class, literal minority label is positive, majority is negative. Missing values are 0 in every column. Registered missing policy is preserve_as_null and preprocessing is none_declared. Loader normalization aligns capitalization, converts declared numeric values and trims string labels without repairing records. page-blocks0 retains the source spelling Lenght.

The binary positive/negative tokens are authoritative from the source declarations. Local evidence inspected does not explicitly establish the original multiclass-to-binary derivation: do not infer an original page-block class grouping, Ecoli localization label, or Abalone ring predicate from its identifier alone. Recorded URLs do not substitute for locally available underlying semantic documentation.

Numeric/categorical feature lists:

- **page-blocks0:** numerical: height, Lenght, area, eccen, p_black, p_and, mean_tr, blackpix, blackand, wb_trans; categorical: none.

- **Ecoli4:** numerical: mcg, gvh, lip, chg, aac, alm1, alm2; categorical: none.

- **Abalone19:** numerical: length, diameter, height, whole_weight, shucked_weight, viscera_weight, shell_weight; categorical: sex.

Abalone19's raw sex declaration is F/I/M. All core targets declare negative/positive.

| Dataset | Full negative/positive | TRAIN negative/positive | TEST negative/positive | TRAIN / TEST rows | Duplicate excess / all-member rows | Feature-only duplicate excess |
| --- | --- | --- | --- | --- | --- | --- |
| page-blocks0 | 4913/559 | 3930/447 | 983/112 | 4377/1095 | 69/109 | 79 |
| Ecoli4 | 316/20 | 253/16 | 63/4 | 269/67 | 0/0 | 0 |
| Abalone19 | 4142/32 | 3314/26 | 828/6 | 3340/834 | 0/0 | 0 |

Duplicate excess uses all features plus target with keep=first; all-member rows uses keep=False. page-blocks0 also has 10 identical-feature groups with conflicting targets. Twelve distinct full-row values appear in both TRAIN and TEST, comprising 17 TEST and 26 TRAIN rows. Other core datasets have no such full-row value overlap. This is a holdout-independence concern, not permission to relabel/deduplicate, and equality alone does not establish common underlying entity identity.

Split policy is test_size=0.2, stratify=true, seed_offset=0, root_seed=42 with hash-ordered within-class allocation and per-class rounding. All split dictionaries reproduce exactly. TRAIN profiles reproduce exactly and all references lie in TRAIN. TEST descriptive counts in this report were used only for audit, never provided to generation or training.

All archives pass CRC, archive .dat members equal placed files byte-for-byte, both checksums match source.json, and normalized fingerprints match dataset_manifest.json. Actual dimensions/IR match the supplied approximate historical expectations. Historical macOS paths in manifests are lineage, not current loader paths. Per-dataset identity:

- **page-blocks0:** source https://sci2s.ugr.es/keel/dataset/data/imbalanced/page-blocks0.zip; source page https://sci2s.ugr.es/keel/dataset.php?cod=147. Archive SHA-256: 82b3c11b0bb0e84357033faecebf5fa91d93cb4c41eac48b815a949a4e59a86d. Normalized fingerprint: 57724e04c433bfeeac5cea3a6bdc66ff9e7d3a6e1ecce17402a78b5707dabf47. Split fingerprint: 1a608a3bd41e248b2befb98fec9bb5d490112d01707b4e4f7afabd864d6bd3fe. TRAIN fingerprint: be4f70ad3646d30b651c9a394a8d04f070cff75dd43718464e03fca1df3051a8. Provenance resources: [data/manifests/page-blocks0](<D:/Github Repos/quality-aware-synthesis-lab/data/manifests/page-blocks0>). TRTR report: [artifacts/reports/trtr-page-blocks0-42.json](<D:/Github Repos/quality-aware-synthesis-lab/artifacts/reports/trtr-page-blocks0-42.json>). P0-v3 and P1 baseline evaluation bundles are present.

- **Ecoli4:** source https://sci2s.ugr.es/keel/dataset/data/imbalanced/ecoli4.zip; source page https://sci2s.ugr.es/keel/dataset.php?cod=118. Archive SHA-256: 75f3a62a1d23b0081976131f6c18331219e29b07ea616620a650b68a27c831d7. Normalized fingerprint: 70f5e5185bd235972417b2e9e4b105abcf62e48056fca6f6e42b237a40901e36. Split fingerprint: e7d82d6f397d96c3b4e99c65b203b6092f51c5b179997f498d5619b2945c4b73. TRAIN fingerprint: e12e1be6917c00b466f90e80c09c70d67785ea30aa4dd274fb1458d984ba0970. Provenance resources: [data/manifests/Ecoli4](<D:/Github Repos/quality-aware-synthesis-lab/data/manifests/Ecoli4>). TRTR report: [artifacts/reports/trtr-Ecoli4-42.json](<D:/Github Repos/quality-aware-synthesis-lab/artifacts/reports/trtr-Ecoli4-42.json>). P0-v3 and P1 baseline evaluation bundles are present.

- **Abalone19:** source https://sci2s.ugr.es/keel/dataset/data/imbalanced/abalone19.zip; source page https://sci2s.ugr.es/keel/dataset.php?cod=115. Archive SHA-256: 595f3332d093368652a55dcef4c4fde60c432b2f7030965b2a661409bdc6f4b1. Normalized fingerprint: 6a55037afab1ec7b30eed4c680ea9ea10a638b722acf0edd9f0cd65ba9e6d9a1. Split fingerprint: 287933d773ae7b8dffc702f1680cb81edbe423a0d3e559c88c9d98f1dbc29d0e. TRAIN fingerprint: 0134894e154df592dabfcc3fbdcd694bdbb923edfd810ec99cd07dd969625d66. Provenance resources: [data/manifests/Abalone19](<D:/Github Repos/quality-aware-synthesis-lab/data/manifests/Abalone19>). TRTR report: [artifacts/reports/trtr-Abalone19-42.json](<D:/Github Repos/quality-aware-synthesis-lab/artifacts/reports/trtr-Abalone19-42.json>). P0-v3 and P1 baseline evaluation bundles are present.

## 4. Expanded DS Dataset Inventory

The extension shortlist is not an approved experimental cohort. No extension file was found in the repository data area or registered definitions.

| Candidate | Actual presence / registration / loading | Recorded source/version | Semantics and specification readiness |
| --- | --- | --- | --- |
| Bank Marketing: bank-additional-full | Absent / no / no | Workbook Dataset Plan A8:M8 says generic Bank Marketing, 45,211 rows, 16 features, UCI dataset/222, data/raw/bank_marketing/ | The workbook does not identify bank-additional-full. Its older dimensions cannot be substituted for the requested variant. No versioned checksum/schema/target mapping/license/preprocessing evidence for the requested variant. |
| DataCo Smart Supply Chain v5 | Absent / no / no | v5 comes from this request; no local version/source record found | Target, labels, numeric/category columns, missingness, imbalance, integrity, usage evidence and preprocessing unresolved. |
| Steel Plates Faults | Absent / no / no | Named in this request; exact local version absent | Task/binarization and all schema/statistics/license/preprocessing details unresolved. |
| Adult, optional | Absent / no / no | Named as optional in this request; exact local version absent | Version, source split composition, target mapping, categories, missing policy, imbalance, checksum/license and preprocessing unresolved. |

Only Bank has a recorded local source reference: https://archive.ics.uci.edu/dataset/222/bank+marketing. No URLs or dataset licenses are invented for missing entries. No byte-level integrity check is possible on absent files. Readiness requires human approval of exact dataset/version/target/scope, separate authorized acquisition, official source/usage evidence, then inspection and specification. No preprocessing recipe is approved for any absent candidate.

The workbook also proposes HTRU2, Musk, Mammography, Default Credit Card, APS and Satimage-2. These historical proposals do not freeze the current DS shortlist.

Workbook evidence: [RC_QASyn_Research_Implementation_Manifest.xlsx](<D:/Github Repos/quality-aware-synthesis-lab/RC_QASyn_Research_Implementation_Manifest.xlsx>); Dataset Plan A1:M11, especially A8:M8. Stored cells were extracted read-only through bundled Python ZIP/XML; no recalculation, edit, export or download.

## 5. ML Dataset Overlap

**OPTIONAL INFORMATION UNAVAILABLE.** D:\Github Repos\imbalance-synthesis-lab is absent at the supplied path. No ML project was imported, copied, executed or added as a dependency.

| DS ID | ML ID/version/checksum | Mapping |
| --- | --- | --- |
| page-blocks0 | Unavailable | Unresolved identity |
| Ecoli4 | Unavailable | Unresolved identity |
| Abalone19 | Unavailable | Unresolved identity |

Identical dataset/version, same dataset/different version, changed target mapping, ML-only and DS-only counts cannot be determined. The approximate 15-dataset suite is not fabricated and does not block DS inventory.

## 6. Dataset Specification Resources

DatasetDefinition in datasets/registry.py and DatasetSpec in contracts/dataset.py are useful existing models. A complete approved DatasetSpecification v1 with per-rule evidence, authority, uncertainty and approval was not found.

| Rule/resource | Classification | Evidence / interpretation |
| --- | --- | --- |
| Core columns, primitive types, target tokens | AUTHORITATIVE within source schema | YAML declarations reconcile with .dat metadata and raw_schema.json |
| Abalone sex F/I/M | AUTHORITATIVE within source schema | Raw nominal declaration agrees with TRAIN domains |
| Numeric intervals in KEEL declarations | AUTHORITATIVE as source-file declarations; universal-domain meaning UNVERIFIED | Record declaration provenance; do not turn whole-source ranges into new TRAIN-derived validity rules |
| TRAIN ranges, quartiles, class proportions, missing rates | INFERRED | Recomputed TRAIN profile; descriptive support, not proof of invalidity outside support |
| TRAIN category/target domains | INFERRED empirical support | B2 rejects out-of-TRAIN categories; its decision is an existing policy, not ground truth |
| Missing token '?' | AUTHORITATIVE file encoding | Raw parsing/schema evidence |
| preserve_as_null / none_declared | AUTHORITATIVE project policy; scientific appropriateness UNVERIFIED | Declared handling does not establish domain validity of missing values |
| Requested-class equality | AUTHORITATIVE execution condition | Request versus candidate target |
| Original-task mapping / units / semantic membership | UNVERIFIED | Original mapping documentation not locally found |
| Cross-field rules | UNVERIFIED / absent | No approved dataset-specific logical rule catalog |
| Rare/unseen exceptions | NOT YET CREATED | Absence in TRAIN must never imply impossible/invalid |
| Source/dataset/split fingerprints | AUTHORITATIVE local provenance | Bytes and recorded split/profile hashes reconcile |
| TRAIN examples / distributions | INFERRED | Profiles contain examples, class proportions and numeric summaries; richer distributions can later be derived from TRAIN |

Each core v1 draft needs exact source/version/checksums, schema, evidence-backed target semantics, declared versus empirical categories/bounds, units where justified, missing policy, cross-field/rare exceptions, TRAIN-only summaries, split lineage, stable rule/evidence IDs, authority tags, uncertainty, owner, review status and approval/version. Unknown fields should remain unknown. Structural drafts can proceed autonomously; unsupported semantic rules cannot be adopted automatically.

## 7. Annotation and Review Resources

| Resource | Status | Evidence |
| --- | --- | --- |
| 120-record cohort | PRESENT BUT INCOMPLETE | 120 distinct row IDs and actual payloads; one source/hash contradiction |
| Selection code | PRESENT AND VALIDATED as available policy code | diagnostics.p1_human_review_sample: unique-prioritized, per-dataset quotas, decision/role/copying/distance strata, hash ordering; recorded history consumed unchanged |
| Historical selection freeze metadata | PRESENT BUT INCOMPLETE | Master manifest gives counts/strata hits; no independently recorded historical seed/protocol hash; overlapping strata hits are not class totals |
| Reviewer A/B packets | PRESENT BUT INCOMPLETE | 120/40 rows; master-relative integrity passes, but source contradiction inherited |
| B overlap selection | PRESENT AND VALIDATED | Seed 42 reproduces exact 40 IDs; Abalone19=14, Ecoli4=14, page-blocks0=12 |
| Completed human labels/provenance | NOT YET CREATED | All human fields blank across nine annotation CSVs |
| Overlap judgments / adjudication | NOT YET CREATED | 40 overlapping packet IDs; zero completed paired judgments |
| Human-audit API/CLI | PRESENT BUT INCOMPLETE for intended workflow | Status/export-blind/import-blind/analyze exist; label interface is binary |
| B2/B3 disagreement reports | PRESENT AND VALIDATED as stored policy reports | P1 Abalone19=62, Ecoli4=26, page-blocks0=25; not human correctness evidence |
| Completed human summary/confusion outputs | REFERENCED BUT NOT FOUND | Listed in human-review.md; absence consistent with unfinished labels |

| Measure | Exact count | Meaning |
| --- | --- | --- |
| Distinct cohort IDs / actual payloads | 120 / 120 | 40 per dataset |
| Labeled / unlabeled cohort records | 0 / 120 | No explicit human_valid values |
| Completed VALID / INVALID / INDETERMINATE | 0 / 0 / 0 | Third state unsupported in existing field |
| Reviewer-A exported rows / judgments | 120 / 0 | Export is not a judgment |
| Reviewer-B exported rows / judgments | 40 / 0 | Export is not a judgment |
| Packet overlap / overlapping judgments | 40 / 0 | No agreement denominator yet |
| Human disagreements / adjudicated records | 0 / 0 | No paired labels; not evidence of perfect agreement |
| Run-specific review export rows | 81 | P0-v3 Abalone19/Ecoli4/page-blocks0=15/9/11; P1=15/16/15; all blank |
| Annotation CSV files inspected | 9 | Master, two blinded, six run-specific; exports are repeated representations |
| Master requested majority / minority | 56 / 64 | Do not assume 60/60 |
| Master B2 accepted / rejected | 103 / 17 | Stored values; source collision remains |
| Master B3 accepted / rejected | 119 / 1 | Stored values |
| Master B2/B3 machine disagreements | 16 | Not human disagreements |
| Full P1 machine disagreements | 113 | 97 redundancy and 16 structural/domain reason classes |
| Unambiguous observed cohort source joins | 119 / 120 | One selected ID has two distinct source occurrences and mismatched hash |

Provider call IDs/seeds are populated on 120/120 master rows. Overall TRAIN distance is populated on 120/120, same-class distance on 105/120. Those diagnostics are not labels or validity probabilities. Reviewer files contain annotation ID, record ID, dataset, requested class, candidate JSON and five human fields; no B1/B2/B3 scores/reasons/provider lineage.

## 8. Autonomous Labeling Readiness

**Partial; not ready as-is.** Annotation IDs, master hashes, blinded packets, protected candidate JSON and separate imports exist. Free-text human_notes can hold explanations. Structured agent evidence/rationale/uncertainty/model/protocol/review-status/correction history is absent. The strict importer rejects added columns and accepts only blank/true/false human_valid. Blank means unlabeled, not INDETERMINATE.

A separate proposal ledger is needed during a subsequently authorized preparation task: label VALID/INVALID/INDETERMINATE; explanation; cited rule/evidence; uncertainty; annotator_type=AGENT; model/version where applicable; prompt/protocol version; review_status=PENDING_HUMAN_APPROVAL. Bind each proposal to a reconciled occurrence ID and payload hash. Keep supervisor decisions, corrections, approval provenance and final signoff distinct from agent proposals. Do not fill human_* fields with agent decisions.

The supervisor must review EVERY proposal. Acceptance after seeing an agent suggestion is human-validated assisted review, not an independent human judgment. Reviewer-B independence, adjudication and the treatment of INDETERMINATE in binary confusion/agreement analysis require a protocol decision. Do not map it to false or silently exclude it. No labels or proposal records were created by this audit.

## 9. Experimental Infrastructure Readiness

Frozen source provides offline response replay, synthetic candidate contracts, B1 raw acceptance, deterministic B2 schema/category/missing/target/range checks plus duplicate filtering, B3 stored scores/decisions, accepted/rejected records, TRAIN profiles, intrinsic/utility/cost reports, scientific/execution identity, source readers and guarded/sealed outputs for new executions. See generation/provider.py, baselines/{validators,judge}.py, datasets/, metrics/, experiments/{runner,readers,specification,artifact_identity,diagnostics,human_audit}.py and storage/.

All six historical bundles pass current legacy source and recorded-context checks. They are completed m1-run-v1 bundles; none has FINALIZED.json or scientific_specification.json. This is explicit legacy compatibility, not new-format sealing. No history was retroactively changed or sealed.

Persisted candidate occurrences: P0-v3 40/40/40; P1 Abalone19=200, Ecoli4=201, page-blocks0=200; total 721. Existing Ecoli4 over-generation and negative parse-failure aggregate accounting are documented pilot discrepancies; impossible negative counts must not be quoted as meaningful results. Undefined utility entries and one-seed pilot scope prevent final scientific performance claims.

The audit helper joined the 17 master B2 rejections to structural/domain evidence using existing files. All selected IDs and B3 scores exist, but page-blocks0 occurrence binding is ambiguous. Existing B2/B3 decisions can be compared offline after reconciliation, approved ternary-analysis policy and human labels. The exact missing resource is an approved source-occurrence mapping connecting cohort payloads to candidate, B2 evidence/decision and B3 judgment occurrences. New provider calls would not repair a historical identity claim.

configs/experiments/replay.yaml and tests/fixtures/replay_fixture.json provide an offline fixture path; no replay was run. Pilot configs point to local Ollama-compatible model/endpoint and OLLAMA_API_KEY. A generation replay flag alone does not establish that a configured live judge is disabled: both roles must be offline/recorded. Fresh providers are unnecessary for this phase and were not contacted.

## 10. Leakage / Provenance Status

Disjoint row indices, coverage, dataset/split hashes, reconstructed TRAIN profiles and TRAIN-only references pass. The current runner supplies bounded TrainingContext to generation/B2/B3, slices REAL TEST in final utility evaluation, and fits classifier preprocessing on its training population. This audit passed no TEST summaries into those paths. Recorded generation/judge traces contain neither test_indices nor test_fingerprint literals; that negative check is supporting evidence, not exhaustive proof of absence of all bugs.

page-blocks0 shares 12 exact full-row values across TRAIN/TEST, affecting 17 TEST rows. This is a confirmed value-overlap and holdout-independence concern requiring research review before independent-holdout claims. It does not itself demonstrate code routing TEST-derived summaries upstream. The frozen split was not changed.

**C1: CRITICAL historical provenance contradiction.**

Bundle: artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829. Generation has 41 trace rows and 38 unique call IDs: chatcmpl-726, chatcmpl-144 and chatcmpl-459 each repeat twice. Its 200 candidates contain 185 unique record IDs: item-0 through item-4 repeat under each of those three call-ID families. B2 decisions, B3 decisions and B3 judge results repeat all 15 candidate IDs. The other five bundles have unique candidate/decision/judge candidate IDs.

The selected chatcmpl-726-item-0 is directly inconsistent:

- [artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/candidates_raw.jsonl](<D:/Github Repos/quality-aware-synthesis-lab/artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/candidates_raw.jsonl:1>) has eccen=5.1, height=8.5 and canonical hash ee55fc63ebc55d8bf9fce08cada9e27236ee86eba9a16dde568d168fdf71652a.

- [artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/candidates_raw.jsonl](<D:/Github Repos/quality-aware-synthesis-lab/artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/candidates_raw.jsonl:41>) reuses the same ID/version for different data, including eccen=45.0, height=9.5 and canonical hash 4e15b1f85b0440d530edb3ccd1aff4af815305d67fc2751f593f21bfb5b9e42a.

- [artifacts/reports/p1/p1_human_review.csv](<D:/Github Repos/quality-aware-synthesis-lab/artifacts/reports/p1/p1_human_review.csv:94>) contains the first payload and second canonical hash. Both source B2/B3 decisions happen to accept, and both scores are 0.98; those scalar equalities do not disambiguate occurrence identity.

Both blinded packets contain that ID. Their manifests hash the actual first payload and source master, so their integrity checks pass while original candidate/hash binding fails. review_status checks nonblank/unique stored hashes but does not recompute every candidate_json hash and require unique source occurrences. Legacy source validation does not reject this collision. This is a confirmed provenance contradiction, not a claim of malicious tampering.

Do not silently replace, deduplicate, rename, re-export or rewrite historical resources to conceal it. The shortest safe next task is an external immutable reconciliation proposal using occurrence position, source-response hash, canonical payload hash and corresponding decision/judge occurrence. Flag all 15 colliding identities. The supervisor must approve the affected cohort entry and historical-claim handling before ground-truth use. No reconciliation/fix was performed here.

New-format execution uses durable internal role ordinals and separates external call IDs. Guards/seals exist for new outputs, but do not retroactively repair legacy provenance.

## 11. Research Materials

Available: README, methodology/contracts/baselines/dataset/human-review documents, Phase-1 stabilization report, manuscript/claim ledger/evidence map, research workbook, 34 literature-note files, 34-row paper inventory, 16 bibliography entries.

There are zero actual PDFs under literature/papers/; only .gitkeep. All 34 indexed PDF paths are absent. Workbook Downloaded flags do not prove local presence. Literature notes are not uniformly blank: qa13, for example, contains bibliography, concepts and page references, contrary to the stale literature README description. Notes provide context but do not replace checking primary evidence for new claims. Bibliographic links were not opened and no papers/licenses/domain rules were invented.

Locally supported: B1–B3 mechanics, deterministic split/TRAIN profile implementation, recorded pilot protocols/results, planned human-validity definition, export/import design and pilot limitations. Not established: calibrated guarantees, superiority, independent human ground truth, unrecorded original target semantics, complete dataset license evidence, frozen expanded cohort, final statistical significance. Missing optional ML papers and general PDFs do not block structural inventory; primary evidence is needed before new substantive domain-rule claims.

## 12. Missing Resources and Priorities

Paths below are relative to D:\Github Repos\quality-aware-synthesis-lab for compact comparison. No fixes were created.

| Priority / class | Affected file/resource | Evidence and impact | Shortest corrective action | Safe autonomously? | Human approval? |
| --- | --- | --- | --- | --- | --- |
| C1 BLOCKING | P1 page-blocks0 candidates_raw/provider_calls; baselines b2/b3; p1_human_review.csv:94; both blinded packets | 15 source-ID collisions and mixed selected payload/hash break source-to-label binding | Prepare separate occurrence-bound reconciliation proposal; preserve frozen bytes | Evidence collection yes; authoritative rebinding/exclusion no | YES before cohort acceptance |
| N1 NON-BLOCKING | contracts/dataset.py; configs/datasets/*.yaml; v1 specification absent | Structural resources exist; no approved rule/evidence/uncertainty v1 | Draft schema/provenance with explicit unknowns | YES for draft | YES to freeze scientific rules |
| N2 NON-BLOCKING | experiments/human_audit.py; proposal ledger absent | No structured agent evidence/uncertainty/model/protocol/status/correction history | Draft separate immutable proposal/review ledger and export | YES structurally in a later authorized task | Protocol approval |
| R1 RESEARCH DECISION | docs/human-review.md; binary importer/analyzer | INDETERMINATE, assistance/independence and adjudication denominators unresolved | Approve three-way review/analysis protocol | Draft alternatives only | YES |
| R2 RESEARCH DECISION | core YAML/raw_schema; original-task documents absent | Binary tokens known; original task mapping/units/semantic rules insufficiently evidenced | Gather exact source evidence; approve unsupported interpretation | May record unknowns | YES for substantive interpretation |
| R3 RESEARCH DECISION | Dataset-specific cross-field/rare-exception catalog absent; validators.py | Empirical support is not universal validity | Tag authoritative/inferred/unverified and rare/unseen cases | Draft/evidence inventory yes | YES for new rules |
| R4 RESEARCH DECISION | Workbook Dataset Plan A8:M8; no expanded YAML/raw files | Bank version unresolved; other requested candidates lack local identity | Approve exact dataset/version/target/scope; separately authorize acquisition | Inventory yes; substitutions no | YES |
| R5 RESEARCH DECISION | page-blocks0.dat and recorded split_manifest.json | Duplicates, 10 conflicting-feature groups, 17 TEST rows matching TRAIN | Document limitation; approve future holdout interpretation without changing frozen split | Measurement yes | YES before methodological change/independence claim |
| N3 NON-BLOCKING | Nine human-review CSVs | 0 labels; approved ground-truth analysis unavailable | After C1/protocol gate, propose labels and obtain review of EVERY proposal | Agent proposals only after gates | YES for every final label |
| N4 NON-BLOCKING | human_audit adjudicated/summary outputs absent | No completed paired judgments or adjudication | Create only after actual reviews | Analyze explicit labels yes | YES for adjudication/signoff |
| R6 RESEARCH DECISION | p1_human_review_manifest.json / recorded cohort | 120 IDs but historical seed/protocol freeze incomplete; 56/64 class balance | Approve retained/reconciled cohort; never silently resample | Document exact IDs/hash yes | YES to freeze cohort |
| N5 NON-BLOCKING | Six m1-run-v1 bundles | No v2 seal/specification; compatibility accepts C1 | Keep legacy status, hash sources, later use separate sealed derivatives | Inventory yes; retroactive claims no | YES for changed evidence claims |
| N6 NON-BLOCKING | generation-protocol/research-plan/literature README/workbook/test history | Stale/inconsistent transport/status/PDF/test claims | Record discrepancies; prefer current code/config/bytes; obtain final handoff if needed | YES for factual inventory | NO for documenting facts |
| O1 OPTIONAL | D:/Github Repos/imbalance-synthesis-lab | Supplied optional repository absent | Reconcile if later available; no dependency | YES read-only later | NO for DS start |
| O2 OPTIONAL | literature/papers; paper_inventory.csv | 34 PDFs indexed, zero present | Record absence; acquire only with separate authorization when needed for claims | Inventory yes | No inventory gate; evidence needed for rules |

## 13. Phase-2 Task-by-Task Readiness

| Stage | Classification | Scope / prerequisite |
| --- | --- | --- |
| P2.0 Dataset/resource inventory | READY NOW | Read-only inventory, checksums, explicit unknowns/discrepancies; no completed-label/ML prerequisite |
| P2.1 Protocol / review-contract preparation | READY AFTER AUTONOMOUS PREPARATION | Draft proposal ledger, ternary policy, source reconciliation plan; human gate before freeze |
| P2.2 Agent annotation followed by human review | BLOCKED | C1 reconciliation first; then approved protocol and review of every proposal |
| P2.3 DatasetSpecification v1 generation | READY AFTER AUTONOMOUS PREPARATION | Draft core structure/authority/unknowns; final semantics/scope require approval |
| P2.4 B2/B3 versus approved-label analysis | BLOCKED | C1 mapping, approved labels and INDETERMINATE/independence policy; recorded decisions then suffice |
| P2.5 Independent verification / freeze | REQUIRES HUMAN APPROVAL | Complete signed specs/annotations and independent verification; later gate |

Safe P2.0 inventory remains possible even though the critical-provenance rule prevents a GO for the full autonomous phase.

## 14. Human Approval Gates

First stop: after permitted autonomous inventory/drafting, before freezing or using the annotation cohort. The supervisor must approve C1 source-occurrence reconciliation and the review/uncertainty protocol. The existing packet cannot be described as fully source-validated.

Later gates: expanded dataset/version/target; original-task/domain rules; holdout-independence interpretation; EVERY agent-proposed label and correction; independent overlap/adjudication when required by the protocol; DatasetSpecification/annotation version freeze; independent verification and supervisor Phase-2 freeze.

The audit itself made no scientific decisions. Unfinished labels are not a blocker for P2.0.

## 15. Recommended Autonomous Execution Scope

After separate authorization to begin Phase 2: inventory the three core sources, record their hashes/existing splits, draft structural specifications with unknown semantic fields, distinguish declared rules from empirical support, and draft proposal/review contracts. Prepare a source-collision reconciliation proposal from saved occurrences/responses without altering history. Document expanded dataset/version gaps without acquisition or registration.

Stop before choosing the authoritative occurrence/cohort treatment, starting labels on the affected cohort, adopting unverified rules, adding extensions, promoting proposals to human ground truth, or freezing the phase. No new generator/validator, provider calls, parameter/split changes or experiment reruns are proposed for this readiness task.

**No Phase 2 work was started.**

## 16. Final Verdict

**NO-GO — CRITICAL DATA / INFRASTRUCTURE BLOCKER**

C1 is a confirmed unsafe historical candidate-to-review/B2/B3 binding. Frozen code, source availability/loading and offline environment pass. Read-only P2.0 inventory and provisional structural drafting are feasible, but the complete autonomous phase cannot receive a GO under the supplied critical-provenance rule until reconciliation is approved.

The 496-file SHA-256 inventory covers source/tests/configs, raw/manifest data, six canonical runs/reports, docs/manuscript/literature, experiments/prompts/test history and top-level research files. .git, virtual environment, pre-existing caches/scratch and artifacts/test-tmp are outside this content inventory and were not targeted for modification. A broad filename scan encountered access denied in pre-existing artifacts/test-tmp; it was not opened or used as scientific evidence.

All audit outputs are in this TEMP directory. evidence.json is initial inventory. identity-collisions.json and review-provenance-summary.json preserve occurrences and are authoritative for C1. Early targeted-probes.json uses a last-occurrence dictionary view, while deep-integrity-evidence.json uses a first-occurrence view; these are diagnostic views of the collision, not changing source data, and are superseded for joins by identity-collisions.json. No early dictionary-based join should be treated as a resolved mapping. Final content-preservation evidence is final-integrity.json.

~~~text
PHASE1_FREEZE_SHA: 341fc2ce647c180b0f4a34fdbdeb49a0acfdcbcc
CURRENT_MAIN_SHA: 341fc2ce647c180b0f4a34fdbdeb49a0acfdcbcc
WORKTREE_CLEAN: YES
CORE_DATASETS_AVAILABLE: 3/3
CORE_DATASETS_LOADABLE: 3/3
CORE_DATASET_PROVENANCE: SOURCE/ARCHIVE/DATASET/SPLIT HASHES VERIFIED; ORIGINAL-TASK SEMANTICS INCOMPLETE
EXPANDED_DATASETS_AVAILABLE: 0/4
ML_DATASET_OVERLAP_CHECKED: NO; OPTIONAL REPOSITORY ABSENT
DATASET_SPECS_READY: NO; STRUCTURAL RESOURCES READY, V1 DRAFT/APPROVAL PENDING
REVIEW_COHORT_FOUND: YES; 120 RECORDS, ONE CRITICAL SOURCE-BINDING CONTRADICTION
EXISTING_LABELS_FOUND: NO; 0
AGENT_LABELING_TOOLING_READY: PARTIAL; PROPOSAL/TERNARY/APPROVAL CONTRACT MISSING
HUMAN_REVIEW_EXPORT_READY: PARTIAL; 120/40 PACKETS PRESENT, SOURCE RECONCILIATION REQUIRED
B2_B3_AUDIT_READY: NO; C1 RECONCILIATION AND APPROVED LABELS REQUIRED
REAL_TEST_BOUNDARY_INTACT: TRAIN-ONLY GUARDS/PROFILES VERIFIED; PAGE-BLOCKS0 VALUE OVERLAP REQUIRES REVIEW
HISTORICAL_ARTIFACTS_UNCHANGED: YES
OFFLINE_EXECUTION_READY: YES FOR INVENTORY/READERS; LABEL ANALYSIS GATED
CRITICAL_BLOCKERS: C1 LEGACY CANDIDATE-ID COLLISIONS AND MIXED COHORT PAYLOAD/HASH
NON_BLOCKING_GAPS: V1 SPECS, PROPOSAL/APPROVAL LEDGER, LABELS/ADJUDICATION, LEGACY-SEAL LIMITS, STALE DOCS; OPTIONAL ML/PDFS ABSENT
HUMAN_APPROVAL_REQUIRED: COHORT/PROTOCOL, SEMANTIC RULES/SCOPE, EVERY FINAL LABEL, FINAL FREEZE
READY_TO_START_P2_0: YES; READ-ONLY INVENTORY
READY_TO_START_AUTONOMOUS_PHASE2: NO; FULL-PHASE NO-GO UNTIL C1 RESOLVED
FINAL_VERDICT: NO-GO — CRITICAL DATA / INFRASTRUCTURE BLOCKER
~~~
