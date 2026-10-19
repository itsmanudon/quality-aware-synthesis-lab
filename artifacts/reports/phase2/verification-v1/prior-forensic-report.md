# RC-QASyn Historical Provenance Forensic Audit

Date: 18 October 2026 (Asia/Calcutta).
Repository: D:\Github Repos\quality-aware-synthesis-lab.
Scope: forensic inspection and an implementation-ready proposal only. No historical file, ID, hash, cohort, split, scientific behavior or annotation was changed. No candidate generation, resampling, installation, model/provider request, commit, merge, push or Phase-2 implementation occurred.

## 1. Executive Summary

**READY FOR SUPERVISOR RECONCILIATION DECISION**

Recommend **Option A — versioned occurrence-aware provenance crosswalk**, preserving the existing 120 payloads and their order, plus the saved 40-record overlap. A new source-bound cohort version is required after approval, but replacing/resampling the cohort is not required by the recovered evidence.

All 200 historical page-blocks0 P1 candidate occurrences can be traced uniquely to saved generation response occurrences. They contain 185 distinct legacy IDs and 181 distinct canonical payload hashes. Fifteen legacy IDs each name two different payloads; no source occurrence is unresolved. This is an ID collision problem separate from ordinary content duplication.

The row-94 contradiction is recoverable. The saved review payload/raw response identifies source candidate occurrence 1, while its hash, batch, seed and distances were borrowed from occurrence 41 by last-write-wins ID dictionaries. Historical code shows this exact mixing mechanism, and all 120 selected rows' saved lookup-derived metadata are explained by it. The payload-preserving resolution is supported by the recorded row and the original ordered export path, not by guessing which generated record looks better.

Full cohort binding audit: 119 VERIFIED, 1 RECOVERABLE, 0 AMBIGUOUS, 0 UNRECOVERABLE. Both reviewer packets include the recoverable row; their payloads/annotation IDs remain stable, but the machine-evidence join needs the approved crosswalk.

No TEST-to-upstream leakage was confirmed. All 144 saved generation and 721 saved judge contexts match reconstructed TRAIN-only contexts. Raw page-blocks0 duplicate values explain the reported overlap across disjoint row-index partitions. Utility independence remains a research interpretation issue.

This verdict authorizes no repair or automatic labeling. The original readiness NO-GO is not silently lifted: the supervisor must approve reconciliation and independently verify the new derivative before annotation work uses it.

## 2. Source Artifact Inventory

Prior report read in full: [readiness report](<C:/Users/manan/AppData/Local/Temp/rcqasyn-readiness-audit-db13465ccaef4767992dec7f9c0121a4/readiness-report.md>). All available supporting JSON evidence was parsed and inventoried in [prior evidence manifest](<C:/Users/manan/AppData/Local/Temp/rcqasyn-provenance-forensics-20261018-7c5f082a/prior-evidence-read.json>). Scripts were read as needed and were not treated as authoritative data. Early first/last-ID dictionary views were superseded by occurrence-preserving reconstruction.

| Source | Role / scope | Concrete reference |
| --- | --- | --- |
| Frozen baseline | main; HEAD=341fc2ce647c180b0f4a34fdbdeb49a0acfdcbcc; clean before/after | No tree diff implied or created |
| Legacy run identity | m1-run-v1, completed, root seed 42; manifest git_commit ab492bf294b563e4b165755692ac8edb8f3dd2be, git_dirty=true | [artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/manifest.json](<D:/Github Repos/quality-aware-synthesis-lab/artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/manifest.json>) |
| Candidate population | 200 ordered JSONL occurrences | [artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/candidates_raw.jsonl](<D:/Github Repos/quality-aware-synthesis-lab/artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/candidates_raw.jsonl>) |
| Generation response evidence | 41 traces: one smoke and 40 generation; full prompts/raw response strings retained | [artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/provider_calls.jsonl](<D:/Github Repos/quality-aware-synthesis-lab/artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/provider_calls.jsonl>) |
| Original recorded payload hashes | 200 ordered records; all agree with occurrence payload under historical canonical rules | [artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/copying_diagnostics.json](<D:/Github Repos/quality-aware-synthesis-lab/artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/copying_diagnostics.json>) |
| Support context | 200 occurrence-ordered distance entries | [artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/support_diagnostics.jsonl](<D:/Github Repos/quality-aware-synthesis-lab/artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/support_diagnostics.jsonl>) |
| B1 evidence | 200 decisions and exact accepted candidate sequence | [artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/baselines/b1](<D:/Github Repos/quality-aware-synthesis-lab/artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/baselines/b1>) |
| B2 evidence | 200 decisions; complete ordered evidence blocks; accepted candidate sequence | [artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/baselines/b2](<D:/Github Repos/quality-aware-synthesis-lab/artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/baselines/b2>) |
| B3 evidence | 200 decisions/results/prompt-response traces; every judge prompt payload matches its candidate occurrence | [artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/baselines/b3](<D:/Github Repos/quality-aware-synthesis-lab/artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/baselines/b3>) |
| Review source | 120 saved rows plus saved selection-count manifest | [artifacts/reports/p1/p1_human_review.csv](<D:/Github Repos/quality-aware-synthesis-lab/artifacts/reports/p1/p1_human_review.csv>) |
| Reviewer packets | A=120, B=40 and their integrity manifests | [artifacts/reports/human_audit/blinded](<D:/Github Repos/quality-aware-synthesis-lab/artifacts/reports/human_audit/blinded>) |
| Historical code | 063ca963... and artifact-commit 136b9eb5... contain the relevant parser/export mechanics | [committed source excerpts](<C:/Users/manan/AppData/Local/Temp/rcqasyn-provenance-forensics-20261018-7c5f082a/historical-code-evidence.json>) |
| Core sources | page-blocks0/Ecoli4/Abalone19 load and source/split hashes still match prior audit | [dataset integrity / overlap evidence](<C:/Users/manan/AppData/Local/Temp/rcqasyn-provenance-forensics-20261018-7c5f082a/train-test-overlap.json>) |

The [source artifact inventory](<C:/Users/manan/AppData/Local/Temp/rcqasyn-provenance-forensics-20261018-7c5f082a/source-artifact-inventory.csv>) lists 114 concrete run/review evidence files with absolute paths, byte sizes and SHA-256. The prior 496-file content inventory also matches at audit start. The source raw files, not the earlier audit's dictionary joins, are authoritative within the available local evidence.

Legacy limitations: no v2 scientific-specification file or bundle seal exists for these historical runs. The dirty run manifest prevents claiming a bit-exact committed executing source tree. Committed source plus artifact consistency demonstrate the mixing mechanism; they do not reconstruct unrecorded dirty changes or the provider's internal ID-generation implementation. No signed original HTTP response envelope/durable attempt ID is available. 'Source-recoverable' here means uniquely bound to the saved trace/response/candidate/control evidence.

## 3. Candidate Identity Collision Analysis

| Metric, page-blocks0 P1 | Count |
| --- | --- |
| Candidate occurrences accounted for / missing | 200 / 0 |
| Unique legacy candidate IDs | 185 |
| Unique canonical payload hashes | 181 |
| Repeated-ID groups / involved occurrences | 15 / 30 |
| A: same ID, same content groups | 0 |
| B: same ID, different content groups | 15 |
| C: ambiguous or missing source groups | 0 |
| D: repeated content with different IDs | 7 groups; 26 member occurrences; 19 excess copies |
| E: other verified legacy behavior | One smoke trace excluded; batch_index resets per requested class |
| Source-recoverable / unresolved occurrences | 200 / 0 |
| Generation traces / unique generation call IDs | 40 / 37 |
| All traces including smoke / unique call IDs | 41 / 38 |

The complete occurrence evidence is [200-occurrence JSON ledger](<C:/Users/manan/AppData/Local/Temp/rcqasyn-provenance-forensics-20261018-7c5f082a/page-blocks0-200-occurrences.json>) and [compact occurrence CSV](<C:/Users/manan/AppData/Local/Temp/rcqasyn-provenance-forensics-20261018-7c5f082a/page-blocks0-occurrence-evidence.csv>). The JSON includes original payload, original candidate/version, source run/manifest/file hashes, source trace address, response ordinal, item index, raw-response digest, computed/original recorded hashes, generator metadata, and B1/B2/B3 decision/evidence/judge addresses. It is forensic evidence, not an approved identity migration.

| Reused call ID | Trace line | Generation response ordinal | Class | Class-local batch_index | Seed | Candidate positions | Raw response SHA-256 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| chatcmpl-726 | 2 | 1 | negative | 0 | 1165294667 | 1–5 | 535b613d23b2ca368adae22c9e04b9897ea3a997bf5494c41fb7f2405e6e98d6 |
| chatcmpl-726 | 10 | 9 | negative | 8 | 1300151513 | 41–45 | 5c6ab6bb8422839abf03141c0e0a7f6dcb028956facb69c98336e655e338d831 |
| chatcmpl-144 | 21 | 20 | negative | 19 | 1167978639 | 96–100 | 640e34b970b7812a204ea16b421a902c6095ee0d7086d50a65c7f2ff6c41abac |
| chatcmpl-144 | 22 | 21 | positive | 0 | 759734032 | 101–105 | 3a64788980815f672406e03e81473d11246152cbe28c2b8c8b2dc9e706d5d668 |
| chatcmpl-459 | 25 | 24 | positive | 3 | 1717941234 | 116–120 | fc2bbf081454d103bc876211a0fe3f29f72dccf6b4de41ba06c663c546dabecb |
| chatcmpl-459 | 30 | 29 | positive | 8 | 3568088186 | 141–145 | 058313029e68adb05925c077dde323bb2d9494fcf11b0c0d02bbf67a78b0c137 |

Each of these call-ID pairs repeats item-0 through item-4. chatcmpl-144 crosses negative and positive requests, demonstrating that neither legacy call ID nor batch_index alone is a valid identity. Batch indices are class-local; a proposed scheme must use pinned source coordinates and response/item ordinals.

Record duplication and identity collision are different: the 19 excess same-content occurrences were retained under different IDs, whereas all 15 repeated-ID pairs have different content. Do not deduplicate the population to 185 or 181, or use payload hashes alone as occurrence identities.

Historical mechanism:
1. The old provider adapter copied the recorded response body's id into response.call_id.
2. The runner preferred response.call_id over its local fallback.
3. The parser formed record_id = call_id + '-item-' + item_index, with version=1, omitting independent response occurrence identity.
4. The diagnostic streams retained all occurrences, but the review exporter built copying/support/B2/B3/judge dictionaries keyed only by candidate ID and generation traces keyed only by call ID. Later entries replaced earlier ones.
5. It then iterated raw candidates in source order, taking each current candidate's payload/raw output and metadata from those lossy maps. Eligibility also used the mapped hash, affecting first-occurrence/stratum interpretation.

The saved traces prove reused recorded call IDs, distinct responses/seeds and resulting collisions. They do not prove why the upstream provider reused IDs, nor that such IDs were globally promised unique. Run identity is also required across historical contexts.

Other canonical runs were inspected to bound extent:

| Run | Occurrences | Unique IDs | Unique payload hashes | Source recovered | Judge payload/response links |
| --- | --- | --- | --- | --- | --- |
| m1-p0-real-v3-Abalone19-gemma4-e4b-20260829 | 40 | 40 | 33 | 40/40 | 40/40 |
| m1-p0-real-v3-Ecoli4-gemma4-e4b-20260829 | 40 | 40 | 38 | 40/40 | 40/40 |
| m1-p0-real-v3-page-blocks0-gemma4-e4b-20260829 | 40 | 40 | 37 | 40/40 | 40/40 |
| m1-p1-real-Abalone19-gemma4-e4b-20260829 | 200 | 200 | 143 | 200/200 | 200/200 |
| m1-p1-real-Ecoli4-gemma4-e4b-20260829 | 201 | 201 | 180 | 201/201 | 201/201 |
| m1-p1-real-page-blocks0-gemma4-e4b-20260829 | 200 | 185 | 181 | 200/200 | 200/200 |

All 721 occurrences across six runs are recoverable from saved evidence. Candidate-ID collisions were found only in the page-blocks0 P1 population. Repeated content in the other runs is not an ID collision. All runs' B1/B2/B3 decision sequences and accepted-candidate sequences align with raw occurrence order. All B2 evidence blocks cover the evidence stream exactly, and all judge prompt payloads/parsed responses agree with the corresponding result occurrence. These checks use ordered contents, counts, evidence references and prompt payloads together, not an unsupported positional zip alone.

## 4. Row-94 Forensic Reconstruction

'Row 94' means logical CSV row 94 counting the header, i.e. data record 93. Because raw_output is multiline, this record spans physical text lines 278–283. The prior readiness report's master :94 link was a logical-row locator, not a correct physical text-line locator; use the physical :278 link below.

Master source: [review row 94 (physical start)](<D:/Github Repos/quality-aware-synthesis-lab/artifacts/reports/p1/p1_human_review.csv:278>). Candidate ID: chatcmpl-726-item-0; source run: m1-p1-real-page-blocks0-gemma4-e4b-20260829.

| Evidence | Payload-matching occurrence | Other occurrence that supplied mapped metadata |
| --- | --- | --- |
| Candidate source line / occurrence | [candidate occurrence 1](<D:/Github Repos/quality-aware-synthesis-lab/artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/candidates_raw.jsonl:1>) | [candidate occurrence 41](<D:/Github Repos/quality-aware-synthesis-lab/artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/candidates_raw.jsonl:41>) |
| Generation trace | [trace line 2](<D:/Github Repos/quality-aware-synthesis-lab/artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/provider_calls.jsonl:2>) | [trace line 10](<D:/Github Repos/quality-aware-synthesis-lab/artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/provider_calls.jsonl:10>) |
| Generation response ordinal / class-local batch | 1 / 0 | 9 / 8 |
| Provider seed | 1165294667 | 1300151513 |
| Recorded source timestamp | 2026-08-29T16:30:31.622450Z | 2026-08-29T16:32:21.640987Z |
| Canonical hash | ee55fc63ebc55d8bf9fce08cada9e27236ee86eba9a16dde568d168fdf71652a | 4e15b1f85b0440d530edb3ccd1aff4af815305d67fc2751f593f21bfb5b9e42a |
| eccen / height / Lenght | 5.1 / 8.5 / 51.2 | 45.0 / 9.5 / 45.2 |
| Nearest TRAIN / same-class distance | 0.3501177783211569 / 0.3501177783211569 | 1.875127452816152 / 1.875127452816152 |
| B1/B2/B3 decision lines | 1 / 1 / 1 | 41 / 41 / 41 |
| B2 evidence lines | 1–5 | 201–205 |
| Judge trace/result line / call ID | 1 / 1 / chatcmpl-424 | 41 / 41 / chatcmpl-832 |
| B2/B3 decision and B3 score | accepted / accepted / 0.98 | accepted / accepted / 0.98 |

The first payload is:
~~~json
{"Lenght":51.2,"area":1120.5,"blackand":750.1,"blackpix":150.2,"class":"negative","eccen":5.1,"height":8.5,"mean_tr":2.5,"p_and":0.75,"p_black":0.25,"wb_trans":150.0}
~~~

The master candidate_json and raw_output match only occurrence 1 among this ID's source occurrences. Its original copying-diagnostics record[0] has the ee55... hash. Record[40] has the 4e15... hash for occurrence 41. The master stores 4e15..., seed 1300151513, batch_index 8 and distance 1.875127..., while retaining occurrence 1's payload and raw response. Both source hashes are correct for their own original payloads; their binding in the review row is wrong.

The original CandidateRecord does not have a dedicated canonical-hash field. 'Original recorded hash' refers to its occurrence-aligned copying_diagnostics.json record, not a field invented on the candidate.

Historically applicable hashing is the diagnostic _canonical function: project exactly the registered feature columns and target; represent missing/null/NaN as '<NULL>'; json.dumps with sort_keys=True, compact separators and default ASCII escaping/default=str; UTF-8 SHA-256. Its function AST is identical at 063ca963..., artifact commit 136b9eb5..., and frozen HEAD. No numeric coercion or replacement hash rule was introduced. Blind manifests use a separately documented full candidate_json hash with ensure_ascii=False; for this complete ASCII numeric payload it equals ee55....

The historical exporter creates a last-entry copying map, so cp[chatcmpl-726-item-0] refers to occurrence 41 even while its raw loop is on occurrence 1. The trace and support dictionaries behave the same way. Eligibility sees the mapped later hash first at the earlier occurrence; that explains how the earlier payload can be retained with later metadata. All 120 saved rows' relevant last-write lookup fields match this mechanism. No sampling was rerun to establish that result.

**Supported answer: A — the recorded review payload is source-proven, and the stored review hash belongs to another occurrence.** Here 'correct' means preserve what the saved review row actually selected/exported. An error-free alternative sampling policy's intended selection cannot be inferred. Choosing occurrence 41 to follow the hash would replace the recorded payload and requires an explicit scientific/cohort decision.

The B3 prompts independently identify the two payloads, and result reasons mention their different Lenght values. Equal scores/acceptance do not make the occurrences interchangeable. Option A should attach the saved payload to judge call chatcmpl-424 and corresponding occurrence-specific B1/B2 evidence, retaining the original contradictory fields in an audit delta. These are proposed source-backed bindings, not edits performed now.

Detailed reconstruction:

[row-94 evidence](<C:/Users/manan/AppData/Local/Temp/rcqasyn-provenance-forensics-20261018-7c5f082a/row94-forensic-reconstruction.json>) and [source/control reconstruction](<C:/Users/manan/AppData/Local/Temp/rcqasyn-provenance-forensics-20261018-7c5f082a/root-cause-evidence.json>).

## 5. Full 120-Row Binding Audit

Deliverables: [120-row reconciliation ledger (CSV)](<C:/Users/manan/AppData/Local/Temp/rcqasyn-provenance-forensics-20261018-7c5f082a/review-reconciliation-ledger.csv>) and [JSON ledger](<C:/Users/manan/AppData/Local/Temp/rcqasyn-provenance-forensics-20261018-7c5f082a/review-reconciliation-ledger.json>). [Field-by-field evidence](<C:/Users/manan/AppData/Local/Temp/rcqasyn-provenance-forensics-20261018-7c5f082a/review-binding-details.json>) retains every original review row and comparison result.

Required ledger columns are present: review_row, original_candidate_id, source_run, source_attempt, source_ordinal, canonical_payload_hash, recorded_hash, binding_status, failure_reason and recommended_action. Additional columns disambiguate data-record index, physical CSV lines, generation response ordinal, class-local batch index and item index.

source_attempt is a byte-pinned saved trace address (absolute provider_calls.jsonl path plus line). It is not an invented durable/provider attempt ID. Candidate occurrence position is 1-based; recorded batch_index/item_index remain 0-based.

Every row was checked for unique source occurrence using run, legacy ID, exact payload and raw response; occurrence payload/hash consistency; original copying diagnostic; generation class/seed/batch; candidate version and target/role representation; B1/B2/B3 decisions; B2 reason/evidence blocks; B3 score and prompt/response/result payload link; copying flags and TRAIN distances. Missing source target is preserved as blank target_class, per the historical CSV encoding, rather than fabricated as a literal 'None' class.

| Binding status | Abalone19 | Ecoli4 | page-blocks0 | Total |
| --- | --- | --- | --- | --- |
| VERIFIED | 40 | 40 | 39 | 119 |
| RECOVERABLE | 0 | 0 | 1 | 1 |
| AMBIGUOUS | 0 | 0 | 0 | 0 |
| UNRECOVERABLE | 0 | 0 | 0 | 0 |

VERIFIED means all checked current bindings match occurrence evidence. RECOVERABLE means the observed payload has a unique supported source but one or more saved metadata bindings conflict; it does not mean repaired or approved. Row 94 fails five checked fields: canonical hash, generation batch, generation seed, nearest TRAIN distance and nearest same-class distance.

Selection provenance is bounded: the saved 120-row master is immutable evidence of actual chosen payloads/order, with 40 per dataset, 56 majority/64 minority. Its manifest records counts and overlapping stratum hits. Available historical code explains the selected row's eligibility and saved fields, but no signed historical sampling execution/protocol digest establishes the counterfactual clean sample. First-occurrence/stratum information may have been biased by the ID collapse, especially in the unselected affected population. Option A must preserve and disclose this retrospective selection limitation, not claim a newly representative random sample. No new sample or alternative 120-row cohort was produced.

## 6. Reviewer-Overlap Impact

A has 120 records, B has 40, all 40 B records are in A. B allocation is Abalone19=14, Ecoli4=14, page-blocks0=12. The saved seed-42 overlap policy reproduces the same recorded 40 IDs; this was a check of the existing packet, not creation of a new cohort.

All saved annotation IDs, candidate JSON hashes and source-master hashes validate internally. Both packets have zero labels. The affected record is A logical/physical row 94 and B logical/physical row 18, annotation_id ann-e6ae275d74cea47bb572, actual payload hash ee55fc63ebc55d8bf9fce08cada9e27236ee86eba9a16dde568d168fdf71652a.

The packets' content identities are stable; the master-to-machine-evidence join is not currently safe for that one overlap entry. Thirty-nine B rows verify directly and one is recoverable. Option A can keep exactly the same 40 payloads and reviewers' overlap assignment. A new occurrence-aware annotation ID scheme may change token strings; preserve old IDs as aliases and provide a 1:1 approved mapping. Do not promise token equality across a version change or treat current blind-manifest checks as a source-reconciliation approval.

Packet evidence: [overlap identity audit](<C:/Users/manan/AppData/Local/Temp/rcqasyn-provenance-forensics-20261018-7c5f082a/review-overlap-packets.json>).

## 7. TRAIN/TEST Overlap Investigation

| Dataset | Full-row overlap groups | TRAIN members | TEST members | Feature-only overlap groups | Feature-only TEST members | Partition row-ID intersection |
| --- | --- | --- | --- | --- | --- | --- |
| Abalone19 | 0 | 0 | 0 | 0 | 0 | 0 |
| Ecoli4 | 0 | 0 | 0 | 0 | 0 | 0 |
| page-blocks0 | 12 | 26 | 17 | 15 | 21 | 0 |

Facts:
- page-blocks0 has 69 excess full-row duplicates in the raw file. Twelve full-row groups crossing the split are also literal repeated physical .dat lines, so they predate scoring and preprocessing. The overlap ledger gives physical source lines and separate TRAIN/TEST row indices.
- Feature-only equality adds three cross-split groups: 15 feature groups total, 33 TRAIN and 21 TEST rows. Ten identical-feature groups in the full source have different targets; do not equate these with same full-row records.
- All partitions have disjoint row indices and reproduce recorded split fingerprints. No actual row identity crosses partitions.
- There is no source entity/observation ID in the registered schemas. Repeated source observations as duplicate file rows are proved; whether they are repeated measurements of the same real-world event is not established.
- Recomputed TRAIN profiles match every stored profile exactly. All 144 generation and 721 judge prompt contexts match reconstructed TRAIN-only projections, with no unexpected context keys. All example indices belong to TRAIN; none of the saved reference examples has an equal full-row TEST counterpart.
- Frozen runner source limits TEST access to final utility evaluation; classifier preprocessing fits its actual training population. No new classifier/experiment was run.

Interpretation: the overlap is a pre-existing source/partition property that can affect utility-scoring independence; it is not caused only at scoring time. TRAIN profile statistics legitimately reflect the selected TRAIN occurrences, even when some values also exist in TEST. Equality alone does not demonstrate TEST-derived information entered generation, admission or preprocessing. **TRAIN_TEST_LEAKAGE_CONFIRMED: NO in the inspected evidence.** This is a bounded finding about recorded inputs/code, not a proof against unrecorded activities or every possible software bug. Independent-holdout claims still need a supervisor decision; do not alter the frozen split or deduplicate now.

Full source-line/index evidence and parsed context checks: [TRAIN/TEST overlap investigation](<C:/Users/manan/AppData/Local/Temp/rcqasyn-provenance-forensics-20261018-7c5f082a/train-test-overlap.json>).

## 8. Recoverability Assessment

All 200 page-blocks0 P1 occurrences have exactly one matching saved generation trace when matched by recorded call ID, exact raw response, seed, requested class and decoded item index/payload together. All 200 original occurrence hashes agree. Raw responses retain the data; no source regeneration is needed.

B1–B3 loops and their persisted arrays retain order. Counts/IDs, accepted candidate payload sequences, B2 evidence-ID blocks, and B3 candidate prompts and response/result fields agree for every occurrence. Thus the two controls associated with a collided ID can be recovered using source coordinates rather than scalar ID lookup. This is stronger evidence than simply pairing two rows by ordinal.

All 120 actual reviewed payloads have unique occurrence bindings with the saved raw_output discriminator. Only one selected row has conflicting mapped metadata. Across all six runs the equivalent checks account for 721/721 saved candidate occurrences. No necessary local source evidence is missing for the proposed payload-preserving reconciliation.

Limits: original dirty source and provider-internal uniqueness guarantees are not reconstructed. Legacy hashes/sequences are local recorded evidence without historical cryptographic seals. A new derivative may bind those source bytes honestly; it must not retroactively claim they were sealed at execution.

## 9. Option A — Crosswalk

Retain every historical artifact and source ID/hash unchanged. After supervisor approval, create an additive versioned crosswalk from a byte-pinned run/file/occurrence address to a new occurrence ID, with generation trace/response/item and B1/B2/B3 evidence addresses. Rebind the same selected payloads/order through that map; produce a NEW cohort version and new source manifest, while keeping the original cohort accessible.

Proposed uniqueness basis: schema_version plus source_run, source manifest SHA-256, candidates_raw.jsonl SHA-256 and candidate JSONL line. Derive an occurrence token from the full canonical identity object; keep the complete descriptor and digest, not only a short display prefix. Two occurrences sharing content or a legacy ID remain distinct because their pinned source positions differ. Identical inputs produce identical IDs independent of output directory, machine path, clock time or execution UUID. A changed source byte/digest is an explicit new source version and must fail pinned validation rather than silently remap identities.

Generation call IDs, class-local batch_index, timestamps and payload hashes are supporting evidence, not sufficient unique keys. Include role and the exact trace source digest/line in attempt addresses; no provider attempt ID is invented.

For row 94, the proposal preserves the existing payload/raw response and binds occurrence 1. Its new occurrence-specific hash/seed/batch/distances come from the saved occurrence-1 evidence. Retain all old contradictory values with source addresses in a delta record. No majority/minority condition, generator/control decision or score is changed by this proposal. If an independent validator discovers a different scalar result in future checks, record it and stop; never substitute automatically.

A corrected version should retain the 120 payload sequence and 40 overlap payload sequence exactly, but describe the original selection policy as historical/biased by ID-only diagnostic lookup where applicable. No new sampling or claim of a clean regenerated sampling distribution is needed.

## 10. Option B — Cohort Rebuild

Preserve the original master/packets. If a supervisor rejects retaining the historical selection bias, propose a separately versioned deterministic sample over trusted occurrence identities and approved dataset/control/class strata. Record source cohort hash, sampling protocol/seed, selected occurrence IDs, changed membership and inclusion rationale.

No resampling was performed now. All necessary occurrences are recoverable, so missing provenance does not force this option. It changes review content/coverage, can change B2/B3 comparison denominators and requires more supervisor review. It is a legitimate research-design alternative if representativeness is prioritized, not an automatic technical repair.

## 11. Option C — Quarantine

If approval or independent verification fails, quarantine the affected page-blocks0 P1 ID-based machine joins/derived reports from final ground-truth comparisons while preserving all raw data and evidence. The 30 collision-associated occurrences can be explicitly flagged, but even apparently unaffected cohort entries must not justify silently excluding page-blocks0 or changing the approved cohort.

The raw page-blocks0 source and all its TRAIN-only structural specification resources remain usable. Ecoli4 and Abalone19 P1 each support 40 source-verified review payloads (80 total) and provisional dataset specification work. The page-blocks0 P0-v3 run also has recoverable 40/40 unique IDs, but substituting those candidates into the P1 cohort would change protocol/scale and needs approval.

Quarantine is a fallback, not required by the evidence recovered. Dataset-scope/exclusion decisions belong to the supervisor.

## 12. Recommended Resolution

**Choose Option A**, subject to explicit approval of the identity/retained-payload policy and independent verification. It recovers exact source bindings while preserving information and all historical artifacts.

| Criterion | Rank 1: A crosswalk | Rank 2: B rebuild | Rank 3: C quarantine |
| --- | --- | --- | --- |
| Exact traceability | Complete 200/200 source-occurrence evidence; all selected payloads retained | Complete if sampling only approved source occurrences; new selection | Safe exclusion flags, but loses disputed population in comparisons |
| Historical preservation | All bytes retained; additive derivative | All bytes retained plus replacement cohort | All bytes retained; restrict usage |
| Information loss | None in source population or saved payload cohort | Original remains, but new membership drops/replaces some review targets | Highest if page-blocks0/affected population excluded |
| Reproducibility | Pinned source descriptors and deterministic occurrence IDs | Also needs approved new seed/strata/selection protocol | Reproducible only after explicit exclusion policy |
| Implementation complexity | Moderate: occurrence scanner, adapters, integrity/version gates | Higher: A-style trusted identity plus sampler/coverage migration | Low immediate flagging; higher scope/comparison consequences |
| Cohort composition | Preserve 120 payloads/order and fixed 40 overlap | Changes possible; scientific approval mandatory | Reduces/changes scope if applied |
| Experimental comparisons | Original B1/B2/B3 evidence retained; fix linkage only | New annotation denominators/coverage; old results remain separate | Limits three-dataset comparability |
| Supervisor effort | Approve explicit mapping/delta; review labels later | Approve sampling redesign and replacements, then all labels | Approve exclusions and scientific claim reductions |

Ranking is evidence-based here, not a rule to preserve row count at any cost. If source recovery had failed, A would not qualify. Retaining the historical sample must explicitly accept its known selection limitation. No ML-project migration or runtime dependency is needed.

## 13. Proposed Data Contracts

These are design requirements only. No production schema, crosswalk or repaired cohort was implemented.

**Source snapshot contract (proposed legacy-source-snapshot-v1):**
- Run/dataset IDs, schema m1-run-v1, manifest hash and recorded dataset/split identities.
- Inventory of source-relative file paths, exact byte SHA-256 and lengths; raw candidates, generation traces, control decisions/candidates/evidence/judgments, copying/support and recorded review inputs included.
- Record the absence of historical seal/scientific specification, source run git_dirty state, audit protocol and parser/canonical-hash versions. New snapshot provenance must not be called the original run's scientific fingerprint.

**Occurrence crosswalk contract (proposed legacy-occurrence-crosswalk-v1):**
- New full-digest occurrence_id; source descriptor {schema_version, source_run, manifest_sha256, candidate_file_sha256, candidate_jsonl_line}; legacy_candidate_id and candidate_version as aliases.
- Original payload and historical payload hash with named hash protocol; copying-diagnostic source pointer and old recorded hash; raw source-line/file hashes as separate hash meanings.
- Source attempt address {role, trace_file_sha256, trace_line}, saved external call ID, response ordinal, requested class, class-local batch_index, seed, raw_response_sha256, item_index and exact matching evidence.
- B1/B2/B3 decision addresses with their source file digests/line positions; accepted-candidate witness; B2 evidence block addresses; judge trace/result addresses, candidate-prompt match, response/result match.
- Binding status, evidence references, ambiguity/recovery flags; no user-defined scalar ID dictionary may collapse multiple occurrences.

**Hash validation contract:**
1. Check source byte digests before parsing; distinguish byte digests, rendered/template prompt hashes, parsed JSON payload hashes and blind-record hashes.
2. Use the historically applicable diagnostic hash for original-record checks, including field projection, null sentinel and default escaping; do not silently normalize integers/floats, strings, omitted fields or unknown columns.
3. Use a separately versioned canonical serialization for the new identity descriptor. Do not call its digest a historical candidate hash.
4. Require a single generation occurrence match using all recorded discriminators. Same content under two traces must remain two occurrences; if available evidence cannot distinguish them, fail closed.
5. Validate controls using the independent witnesses above; never link solely by repeated candidate ID, result ID, score or timestamp.
6. Recompute review payload hash and require agreement with its occurrence. Preserve conflicting historical values separately.
7. Reject source tampering, truncation, duplication, reordered evidence without an approved new source version, mixed snapshot versions and unresolved joins before any review export or label import.

**Corrected cohort contract (proposed review-cohort-v2):**
- New cohort version, original master/packet SHA-256, approved snapshot/crosswalk version/digest and signed supervisor decision reference.
- Ordered 120 selected occurrence IDs plus original review positions and payloads; explicit unchanged payload/order assertion and a field-level delta for row 94.
- Retain original_candidate_id, original recorded hash and old annotation ID aliases. Keep historical strata/selection metadata as historical; any recomputed diagnostic field has its own provenance/version.
- Freeze the same approved 40 overlap occurrence IDs in a manifest rather than silently selecting again. A new annotation token should bind cohort version, occurrence ID and payload hash; old aliases map one-to-one to it.
- Keep original bundles untouched. Create outputs only in a fresh authorized derivative namespace, e.g. a new reconciliation directory under artifacts/reports/human_audit, with exclusive guarded writes and a new derivative seal. Output paths are execution details, not scientific/occurrence identities.

**Annotation linkage contract:**
- Agent proposal key includes cohort version, occurrence_id, canonical_payload_hash, crosswalk digest and annotation/protocol version.
- Store label VALID/INVALID/INDETERMINATE, explanation, cited rule/evidence, uncertainty, annotator_type=AGENT, model/version, prompt/protocol version, status=PENDING_HUMAN_APPROVAL.
- Supervisor reviews EVERY proposal; decisions/corrections are separate append-only events with approval provenance. No proposal fills a human ground-truth field automatically.
- Import validates approved cohort/snapshot, exact packet membership, content and occurrence identity before accepting a decision. Preserve Reviewer-B independence rules and adjudication protocol. Pending, indeterminate and signed-approved states remain distinct.
- The existing strict boolean importer/analyzer lacks these fields; add a version-aware path rather than silently feeding v2 records into a legacy ID-based join.

## 14. Required Regression Tests

Tests for a later implementation, not tests added or run now:
1. Two distinct responses reuse one external call ID and item index: keep both occurrences with different stable IDs and exact response links.
2. Same legacy ID and same payload in two distinct attempts: retain both source occurrences; fail a review join without sufficient attempt evidence rather than deduplicating.
3. Same content under different IDs: preserve source multiplicity; identity is not a payload digest.
4. Class-local batch_index resets and a reused ID crosses requested classes (the chatcmpl-144 pattern): no class/attempt conflation.
5. Repeated IDs across runs: preserve separate run/source scope.
6. Actual row-94 pattern: first payload/raw output plus later hash/seed/batch/distances is detected and reported RECOVERABLE; no silent repair.
7. Full fixture cardinalities: 200 occurrences, 185 IDs, 181 hashes, 15 different-content groups; correct 119/1/0/0 review ledger and 40 fixed overlap identities.
8. Hash edge cases: omitted/null/NaN sentinel behavior, numeric types, categorical Unicode escaping, extra-field projection and separate blind/full-object hashing. Never alias distinct protocols.
9. Control order/content checks: decision/evidence/judge truncation, reordering, duplicate insertion, modified accepted candidates, wrong judge prompt payload and mismatched response/result must fail. Matching scalar scores alone cannot pass.
10. Metadata-only mismatch with unchanged payload and same decision: do not overlook corrupted seed, batch, distance or source pointer.
11. Missing/ambiguous raw response, two identical candidate occurrences under insufficient saved metadata: mark AMBIGUOUS/UNRECOVERABLE and prevent final export.
12. Source byte tampering or snapshot/cohort/crosswalk version mixing: fail before export/import. Changing machine/output paths leaves identity unchanged; changing source bytes changes/rejects the snapshot.
13. Preserve exact saved 120 payload sequence and fixed 40 overlap under A. No automatic resampling or payload substitution. Old annotation aliases map uniquely.
14. Label import rejects modified payload, wrong occurrence/cohort/protocol, duplicate identity or missing required source approval. Agent status cannot become human-approved without a real supervisor event.
15. Guarded outputs reject existing paths, protected historical destinations, aliases and unauthorized overwrite; only newly created derivative is sealed.
16. A separate before/after hash inventory verifies all historical bundles, sources, masters and packets unchanged. No provider can be constructed or called in this workflow.
17. New version-aware review analysis consumes occurrence-bound B2/B3 evidence; legacy m1-run-v1 compatibility and frozen B1/B2/B3 scientific admission remain unchanged.
18. TRAIN/TEST checks retain existing split indices, exact overlap measurements and TRAIN-only context equality; no deduplication or preprocessing alteration is hidden in reconciliation.

Use isolated TEMP fixtures and copies. Relevant existing regression organization is tests/m1 and tests/contracts; a new focused legacy-reconciliation test file is preferable to changing experiment behavior.

## 15. Historical Integrity

At audit start, all 496 files in the prior readiness snapshot matched exactly, including source data, canonical run evidence, source/tests/configs/docs and review packets. Worktree was clean and HEAD matched the freeze. All three original core sources loaded and raw/split fingerprints agreed.

The final check rehashes the same scope and detects added/removed files within it. No old run, candidate ID/hash, master, blind manifest, packet or prior readiness evidence was modified. No repository test, diagnostic writer, experiment, sampler, annotation export/import or provider command was run. Python -B suppressed bytecode writes; generated scripts/JSON/CSV/report remain in the new TEMP audit directory. Existing .git/.venv/caches/scratch are not included in the 496-file content inventory, and no mutation was directed there.

See [final integrity verification](<C:/Users/manan/AppData/Local/Temp/rcqasyn-provenance-forensics-20261018-7c5f082a/final-integrity.json>) and [baseline hash inventory](<C:/Users/manan/AppData/Local/Temp/rcqasyn-provenance-forensics-20261018-7c5f082a/repository-content-before.json>). The prior evidence directory itself was read-only; hashes of all its files were recorded and rechecked.

## 16. Human Approval Decisions

The supervisor must explicitly approve:
- The occurrence identity descriptor, canonical identity protocol and role-aware source-attempt addressing.
- Option A's retention of all 120 actual payloads/order and the same 40 overlap, accepting and disclosing historical selection limitations.
- Row 94's payload-preserving occurrence-1 binding and source-backed metadata delta. The record is RECOVERABLE, not unresolved; choosing its stored hash's other payload is a different cohort decision.
- Any exclusion/replacement/quarantine of records or page-blocks0; none is applied now.
- Any revised sampling policy if B is chosen; no new sampling is implied by A.
- New cohort/crosswalk/packet versions, migration of old annotation aliases, review protocol and uncertainty/independence policy.
- Treatment of exact-value TRAIN/TEST overlap in claims; no split/preprocessing change is authorized by reconciliation.
- Independent verification acceptance before annotation preparation uses the new derivative. Every eventual annotation proposal still requires supervisor review.

## 17. Implementation Readiness

No missing authoritative local occurrence evidence blocks Option A. The remaining gate is supervisor choice and approval, followed by additive implementation and independent verification.

Proposed later module/file touchpoints, each clearly a proposal:

| Existing structure / proposed addition | Responsibility |
| --- | --- |
| NEW src/rcqasyn/experiments/provenance_reconciliation.py (proposed) | Pure occurrence scanner, source snapshot/attempt/control witnesses, validation and delta generation |
| NEW contract alongside src/rcqasyn/contracts/m1.py or in contracts/ (proposed) | Typed versioned snapshot/crosswalk/cohort/approval contracts |
| src/rcqasyn/experiments/diagnostics.py | Reuse documented canonical hashing only; new reader must not use _run_candidate_table's lossy maps or resample existing cohort |
| src/rcqasyn/generation/parser.py | Reuse/version the recorded-response decoder; do not generate candidates, contact providers or rewrite parser scientific behavior |
| src/rcqasyn/experiments/human_audit.py | Add explicit version-aware occurrence join/export/import/analysis gateway; preserve legacy historical inputs |
| src/rcqasyn/experiments/readers.py and artifact_identity.py | Bind/validate legacy source bytes honestly; do not upgrade old runs to pretend v2 seals |
| src/rcqasyn/storage/{artifacts,ownership}.py | Reuse guarded reservations, immutable writes and derivative sealing |
| src/rcqasyn/cli/app.py | Optional additive human-review reconciliation/validation interface; names/flags below are proposals |
| NEW tests/m1/test_legacy_provenance_reconciliation.py (proposed) | Focused collision/row94/control/cohort/immutability regressions using TEMP |
| NEW docs/provenance-reconciliation.md (proposed) | Approved decision, schemas, historical limitations, steps and verification record |

Later workflow:
1. Pin the frozen source snapshot and supervisor-approved policy; verify all input digests. Work on new derivative outputs, never a historical destination.
2. Scan every raw/response/control occurrence; produce deterministic complete mappings with proofs and fail closed on unresolved cases.
3. Validate the original saved 120 and fixed 40 against those source occurrences. Present the row-94 field delta and unchanged-payload assertion before any cohort version is finalized.
4. After approval, create/seal a NEW source-bound cohort/packet version, retaining originals and aliases. Identity versioning is additive, not an ID rewrite inside historical runs.
5. An independent verifier reproduces the source matching, hash rules, 200/185/181 collision counts, 119/1 review findings, exact membership/order and fixed overlap, control prompt/evidence bindings, no source mutations and no network operation. Resolve discrepancies before supervisor acceptance.
6. Only then begin separately authorized agent proposals, all pending human approval, followed by supervisor review of every decision.

An additive CLI such as human-review reconcile-legacy and validate-reconciliation would be a proposed interface, not an existing runnable command. Existing status/export-blind/import-blind/analyze alone are insufficient because they do not enforce the full occurrence crosswalk. No command was added here.

Independent verification must not reuse the same lossy ID dictionaries or accept only the probe's summary; it should read the pinned original files, reconstruct all occurrence matches and judge prompt payload witnesses, and verify source inventory/delta independently. Do not rerun generation or change metrics to make the audit pass.

## 18. Final Verdict

**READY FOR SUPERVISOR RECONCILIATION DECISION**

Evidence supports A without source regeneration, cohort resampling, population exclusion or ML-project migration. All required page-blocks0 occurrences are recoverable; all 120 saved review payloads can be preserved. One row needs explicit metadata rebinding in a new approved version. No critical TEST-to-upstream leakage was confirmed.

This is a completed read-only forensic recommendation. It is not an approved crosswalk, repaired cohort, label dataset, Phase-2 start or permission to change the frozen implementation. The original cohort remains unchanged and must not be used for final ground-truth joins until the approved derivative passes independent verification.

~~~text
PHASE1_SHA: 341fc2ce647c180b0f4a34fdbdeb49a0acfdcbcc
WORKTREE_CLEAN: YES
CANDIDATE_OCCURRENCES: 200/200 PAGE-BLOCKS0 P1 ACCOUNTED FOR
UNIQUE_LEGACY_IDS: 185
REPEATED_ID_GROUPS: 15
DIFFERENT_CONTENT_COLLISIONS: 15 GROUPS / 30 OCCURRENCES
SOURCE_RECOVERABLE_OCCURRENCES: 200
UNRESOLVED_OCCURRENCES: 0
REVIEW_ROWS_VERIFIED: 119
REVIEW_ROWS_RECOVERABLE: 1
REVIEW_ROWS_AMBIGUOUS: 0
REVIEW_ROWS_UNRECOVERABLE: 0
ROW94_ROOT_CAUSE: EXPORTED OCCURRENCE-1 PAYLOAD MIXED WITH OCCURRENCE-41 HASH/SEED/BATCH/DISTANCES BY ID-ONLY LAST-WRITE MAPS
REVIEW_OVERLAP_SAFE: PAYLOAD/IDS STABLE; ONE OF 40 REQUIRES APPROVED SOURCE REBIND
TRAIN_TEST_LEAKAGE_CONFIRMED: NO IN INSPECTED RECORDED INPUTS; RAW VALUE-OVERLAP LIMITATION REMAINS
RECOMMENDED_OPTION: A — VERSIONED PROVENANCE CROSSWALK
COHORT_REPLACEMENT_NEEDED: NO PAYLOAD RESAMPLING; NEW APPROVED COHORT VERSION REQUIRED
HUMAN_APPROVAL_REQUIRED: YES; IDENTITY SCHEME, COHORT/ROW94 TREATMENT, PROTOCOL, VERIFICATION AND EVENTUAL LABELS
HISTORICAL_FILES_MODIFIED: NO
READY_FOR_RECONCILIATION_IMPLEMENTATION: YES AFTER SUPERVISOR APPROVAL
FINAL_VERDICT: READY FOR SUPERVISOR RECONCILIATION DECISION
~~~
