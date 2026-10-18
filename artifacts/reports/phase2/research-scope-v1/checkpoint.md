# Phase-2 cohort and exact rubric approval checkpoint

Status: awaiting personal supervisor approval. No real labels generated.

Implementation scope approval does not approve this cohort or rubric. The production-authenticated approval path remains disabled.

- cohort_fingerprint: `b754ccee1f58ccfc0d89dfde176cb84d58993b93bc5e87a7059ce5e8885877a5`
- crosswalk_set_fingerprint: `a030da9a974f1e305ce7acdf257752f4f39bb8285afdf353f086e61ae6931acd`
- protocol_fingerprint: `47fd0f0c929754c3bbe463f375b1dc996d159156a00d0428766f58e6f769a84f`
- specifications_fingerprint: `5e1c669d8fa3e41ffd41ef940089bb986171aafc1ba54159601122e3d53890b2`
- research_rubric_fingerprint: `1770f1503e8b7cbb0768b596e443fb0753a920d264247a52120be7c242b90d15`

The crosswalk-set fingerprint hashes the ordered list of the three individual crosswalk fingerprints; it does not replace them.

- page-blocks0: 200 occurrences; `3304be98d627bf5b9bb46f46e3f43f6ecbaae883ef0899aa2361dc0bdb6384f2`
- Ecoli4: 201 occurrences; `4df77104a1638c5948da314813b17f104490c2bfed4fd8f289e65bc65b4d8116`
- Abalone19: 200 occurrences; `61ae1ac58af59581317855d3aab30a338a1a4d9e5c066eaabfcbc7aaa689f588`

Preserved cohort: 120 records. Preserved review overlap: 40 records.
Logical CSV row 94 (data record 93) retains its payload and binds to page-blocks0 source occurrence 1. The original and five corrected metadata fields remain in gate-a-v3/cohort/row94.md and before-after.csv.

Recorded nonrepresentative cohort retained; historical ID-only diagnostic lookup biased strata. No resampling or population-wide inference.

## Exact annotation rubric

- **INDETERMINATE:** Evidence does not support a defensible conclusion.
- **INVALID:** A specific supported applicable authoritative violation exists.
- **VALID:** No substantiated authoritative violation, with sufficient evidence for a positive record-level judgment.

1. Assess the original payload against applicable AUTHORITATIVE rules only. Cite rule IDs and concrete payload observations in the rationale.
2. INVALID requires a specific substantiated authoritative violation. Declared primitive types and nominal categories are applicable; source numerical bounds and TRAIN support are not universal physical validity limits.
3. VALID requires sufficient positive record-level evidence. Absence of a detected violation alone is insufficient. Explain what the evidence establishes.
4. Use INDETERMINATE where a defensible conclusion depends on unresolved target mapping, physical meaning, units, or cross-field constraints. Do not invent them.
5. Preserved source missing token '?' / null is not automatically invalid. Document missingness and use INDETERMINATE when it prevents judgment.
6. Treat positive/negative as literal source tokens. Do not infer the original multiclass mapping from a dataset name or infer label truth from requested_class.
7. Keep validity, uncertainty, redundancy and contribution separate. Rare, unseen, outlier, duplicate and low probability are not validity violations.
8. Annotate blinded packets without B1/B2/B3 results or machine scores as evidence. Give every proposal a rationale, applicable evidence IDs and uncertainty statement.
9. The supervisor personally reviews every row, explicitly records a final label including INDETERMINATE where appropriate, and explains changed labels. No proposal becomes a human decision automatically.

## Exact applicable rules and source declarations

### Abalone19

Fields (source spelling retained):

- sex: {M, F, I}
- length: real [0.075, 0.815]
- diameter: real [0.055, 0.65]
- height: real [0.0, 1.13]
- whole_weight: real [0.0020, 2.8255]
- shucked_weight: real [0.0010, 1.488]
- viscera_weight: real [5.0E-4, 0.76]
- shell_weight: real [0.0015, 1.005]
- class: ['negative', 'positive']

- `Abalone19:declared-categories` [AUTHORITATIVE]: Nominal category declarations apply to this source version. Evidence: data/manifests/Abalone19/raw_schema.json; hard rejection allowed: True.
- `Abalone19:original-target-mapping` [UNVERIFIED]: Original multiclass-to-binary mapping is not independently established by the locally archived documentation. Evidence: none; hard rejection allowed: False.
- `Abalone19:schema` [AUTHORITATIVE]: Use the declared feature/target fields and primitive numerical/nominal types. Evidence: data/manifests/Abalone19/raw_schema.json; hard rejection allowed: True.
- `Abalone19:target-tokens` [AUTHORITATIVE]: The source target declaration permits positive and negative. Evidence: data/manifests/Abalone19/raw_schema.json; hard rejection allowed: True.
- `Abalone19:train-support` [INFERRED]: TRAIN ranges, frequencies and domains describe observed support only. Evidence: data/manifests/Abalone19/profile.json; hard rejection allowed: False.

- Rare/unseen/outlier/duplicate/low-probability is not automatically invalid.
- Cross-field physical constraints and original target mapping need evidence.
- Missing token '?' is preserved as null; no new imputation is introduced.
- No exact-value overlap found in audit.

### Ecoli4

Fields (source spelling retained):

- mcg: real [0.0, 0.89]
- gvh: real [0.16, 1.0]
- lip: real [0.48, 1.0]
- chg: real [0.5, 1.0]
- aac: real [0.0, 0.88]
- alm1: real [0.03, 1.0]
- alm2: real [0.0, 0.99]
- class: ['negative', 'positive']

- `Ecoli4:original-target-mapping` [UNVERIFIED]: Original multiclass-to-binary mapping is not independently established by the locally archived documentation. Evidence: none; hard rejection allowed: False.
- `Ecoli4:schema` [AUTHORITATIVE]: Use the declared feature/target fields and primitive numerical/nominal types. Evidence: data/manifests/Ecoli4/raw_schema.json; hard rejection allowed: True.
- `Ecoli4:target-tokens` [AUTHORITATIVE]: The source target declaration permits positive and negative. Evidence: data/manifests/Ecoli4/raw_schema.json; hard rejection allowed: True.
- `Ecoli4:train-support` [INFERRED]: TRAIN ranges, frequencies and domains describe observed support only. Evidence: data/manifests/Ecoli4/profile.json; hard rejection allowed: False.

- Rare/unseen/outlier/duplicate/low-probability is not automatically invalid.
- Cross-field physical constraints and original target mapping need evidence.
- Missing token '?' is preserved as null; no new imputation is introduced.
- No exact-value overlap found in audit.

### page-blocks0

Fields (source spelling retained):

- height: integer [1, 804]
- Lenght: integer [1, 553]
- area: integer [7, 143993]
- eccen: real [0.0070, 537.0]
- p_black: real [0.052, 1.0]
- p_and: real [0.062, 1.0]
- mean_tr: real [1.0, 4955.0]
- blackpix: integer [1, 33017]
- blackand: integer [7, 46133]
- wb_trans: integer [1, 3212]
- class: ['negative', 'positive']

- `page-blocks0:original-target-mapping` [UNVERIFIED]: Original multiclass-to-binary mapping is not independently established by the locally archived documentation. Evidence: none; hard rejection allowed: False.
- `page-blocks0:schema` [AUTHORITATIVE]: Use the declared feature/target fields and primitive numerical/nominal types. Evidence: data/manifests/page-blocks0/raw_schema.json; hard rejection allowed: True.
- `page-blocks0:target-tokens` [AUTHORITATIVE]: The source target declaration permits positive and negative. Evidence: data/manifests/page-blocks0/raw_schema.json; hard rejection allowed: True.
- `page-blocks0:train-support` [INFERRED]: TRAIN ranges, frequencies and domains describe observed support only. Evidence: data/manifests/page-blocks0/profile.json; hard rejection allowed: False.

- Rare/unseen/outlier/duplicate/low-probability is not automatically invalid.
- Cross-field physical constraints and original target mapping need evidence.
- Missing token '?' is preserved as null; no new imputation is introduced.
- page-blocks0 exact-value TRAIN/TEST overlap is a historical limitation.

## Unresolved scientific decisions for explicit supervisor disposition

For each dataset, original multiclass-to-binary mapping, physical field meanings/units and cross-field hard constraints remain unverified. Proposed disposition: retain these unknowns, use literal source labels, add no physical rules, and use INDETERMINATE where they prevent a defensible record-level judgment. Source numerical ranges and TRAIN statistics remain descriptive; neither supplies a universal hard bound.

Accept the preserved nonrepresentative cohort and the documented page-blocks0 TRAIN/TEST exact-value overlap as limitations. The fixed 40-row overlap is retained, but one supervisor's review cannot establish inter-rater agreement.

Confirm that VALID requires positive sufficient evidence and that absence of a detected schema violation alone is insufficient. This may yield many INDETERMINATE proposals; no target class correctness is inferred.

## Requested approval

Explicitly approve the cohort and exact rubric fingerprints above and state whether you accept the proposed conservative disposition of these unresolved decisions. Corrections require a new source-backed version before proposals. Only after approval will the agent prepare 120 proposals for personal review. That later review and exact reviewed-ledger confirmation are separate gates.

Fingerprints bind file content; this workflow does not cryptographically authenticate people or resist a malicious agent with the same permissions.
