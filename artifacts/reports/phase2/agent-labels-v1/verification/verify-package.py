"""Targeted verification of the actual pending proposal package; no human labels."""
from pathlib import Path
import hashlib,json,runpy
from rcqasyn.phase2.common import read_bundle,verify_envelope,digest,csv_rows,write_bundle,envelope
from rcqasyn.phase2.annotations import packets,pending_batches,validate_proposals
from rcqasyn.phase2.research import load_research_proposals,export_research_review,read_review_rows
from rcqasyn.phase2.workflow import load_preparation,historical_inventory
from rcqasyn.storage.ownership import file_hash
repo=Path(r'D:\Github Repos\quality-aware-synthesis-lab-phase2')
source=Path(r'D:\Github Repos\quality-aware-synthesis-lab')
tmp=Path(r'C:\Users\manan\AppData\Local\Temp\rcqasyn-label-prep-20261018')
base=repo/'artifacts/reports/phase2/agent-labels-v1'
cohort,cws,protocol,specs=load_preparation(repo/'artifacts/reports/phase2/gate-a-v3')
scope=json.loads((base/'technical-checkpoint/scope-approval.json').read_text(encoding='utf-8'))
proposals=load_research_proposals(base/'proposals',cohort,protocol,scope)
inputs=read_bundle(base/'labeling-input')
answers=read_bundle(base/'blinded-answers')
ledger=read_bundle(base/'supervisor-review')
rich=json.loads((base/'supervisor-review/review.json').read_text(encoding='utf-8'))
summary=json.loads((base/'supervisor-review/summary.json').read_text(encoding='utf-8'))
checks=[]
def check(name,condition):
    assert condition,name
    checks.append({'check':name,'result':'PASS'})
check('exactly_120_unique_proposals',len(proposals)==len({r['review_row_id'] for r in proposals})==120)
check('complete_cohort_membership_and_original_order',[r['review_row_id'] for r in rich]==[r['review_row_id'] for r in cohort['records']])
validate_proposals(proposals,cohort,protocol)
check('existing_source_bound_proposal_validator',True)
source_byrow={r['review_row_id']:r for r in cohort['records']}
proposed_byrow={r['review_row_id']:r for r in proposals}
check('payload_occurrence_and_proposal_fingerprints',all(r['payload']==source_byrow[r['review_row_id']]['payload'] and digest(r['payload'])==r['payload_sha256']==source_byrow[r['review_row_id']]['payload_sha256'] and r['occurrence_id']==source_byrow[r['review_row_id']]['occurrence_id'] and r['proposal_fingerprint']==digest(proposed_byrow[r['review_row_id']]) for r in rich))
hashes={r['source_occurrence_locator']['artifact']:r['source_occurrence_locator']['sha256'] for r in rich}
check('raw_source_artifact_hashes',all(file_hash(source/k)==v for k,v in hashes.items()))
check('canonical_cohort_crosswalk_and_rubric_identities',cohort['fingerprint']=='b754ccee1f58ccfc0d89dfde176cb84d58993b93bc5e87a7059ce5e8885877a5' and digest(cohort['crosswalk_fingerprints'])=='a030da9a974f1e305ce7acdf257752f4f39bb8285afdf353f086e61ae6931acd' and inputs['rubric']['fingerprint']=='1770f1503e8b7cbb0768b596e443fb0753a920d264247a52120be7c242b90d15')
_,private=packets(cohort,protocol)
blind_byrow={r['review_row_id']:r['blinded_review_id'] for r in private['mapping']}
check('unique_correct_blinded_mapping',len({r['blinded_review_id'] for r in rich})==120 and all(r['blinded_review_id']==blind_byrow[r['review_row_id']] for r in rich))
check('source_backed_authoritative_evidence_only',all(e['authority']=='AUTHORITATIVE' and e['source_sha256']==protocol['source_files'][e['source']] and e['rule_id'].startswith(r['dataset_id']+':') for r in rich for e in r['supporting_source_evidence']))
check('no_populated_human_decisions',all(p['annotator_type']=='AGENT' and p['review_status']=='PENDING_HUMAN_APPROVAL' and all(p[k] is None for k in ('human_final_label','human_correction_note','human_reviewer_reference','human_approval_provenance')) for p in proposals) and all(r['human_review_status']=='PENDING' and r['human_final_label'] is None and r['human_correction_note']==r['human_reviewer_reference']=='' for r in rich))
check('pending_ledger_matches_existing_export',export_research_review(source,cohort,cws,protocol,scope,proposals)==ledger)
check('canonical_import_template_matches_pending_ledger',read_review_rows(base/'supervisor-review/review-import-template.json')==ledger['rows'])
check('no_missing_resume_work',pending_batches(cohort,protocol,base/'proposals')==[] and len(list((base/'proposals').glob('batch-*')))==1)
# Replay the source-only annotator without invoking its main/output writer.
procedure=runpy.run_path(str(base/'blinded-answers/annotation-procedure.py'),run_name='reproduction_without_output')
replayed=[procedure['annotate'](p) for p in inputs['primary']]
check('deterministic_blinded_proposal_reproduction',[x[0] for x in replayed]==answers['answers'] and [x[1] for x in replayed]==answers['observations'])
allowed={'blinded_review_id','dataset_id','payload','payload_sha256','field_definitions','allowed_evidence','known_ambiguity'}
check('label_input_is_exact_annotation_only_projection',all(set(p)==allowed for p in inputs['primary']) and inputs['primary']==read_bundle(repo/'artifacts/reports/phase2/gate-a-v3/public-packets')['primary'] and inputs['machine_critic_information_included'] is False and answers['machine_critic_information_used'] is False and answers['external_provider_calls']==0)
# Explicit expected violations were inspected in the blinded original-order packet.
missing=set(range(26,31))|set(range(71,76))|{76}|set(range(116,121))
fractional={83,85,90,93,97,98,104,105,106,107,113,116,117,118,119,120}
invalid=missing|fractional
check('specific_observed_schema_cases_and_no_forced_valids',{r['review_order'] for r in rich if r['proposed_label']=='INVALID'}==invalid and all(r['proposed_label']=='INDETERMINATE' for r in rich if r['review_order'] not in invalid) and rich[40]['proposed_label']=='INDETERMINATE')
check('exact_counts_and_uncertainty_definitions',summary['proposal_counts']=={'VALID':0,'INVALID':27,'INDETERMINATE':93} and summary['ambiguous_records']==summary['records_lacking_sufficient_authoritative_evidence']==93 and summary['unresolved_domain_semantics_records']==120)
csv=csv_rows(base/'supervisor-review/review.csv')
match=len(csv)==len(rich)
for observed,expected in zip(csv,rich,strict=True):
    match=match and set(observed)==set(expected)
    for key,value in expected.items():
        parsed=json.loads(observed[key]) if isinstance(value,(dict,list)) else None if value is None and observed[key]=='' else int(observed[key]) if type(value) is int else observed[key]
        match=match and parsed==value
check('csv_json_round_trip_and_blank_human_cells',match)
priority=csv_rows(base/'supervisor-review/review-priority.csv')
check('priority_contains_all_rows_high_uncertainty_first',len(priority)==len({r['review_row_id'] for r in priority})==120 and all(r['proposed_label']=='INDETERMINATE' for r in priority[:93]) and all(r['proposed_label']=='INVALID' for r in priority[93:]))
check('preserved_40_overlap_and_row94_binding',len(cohort['overlap_review_row_ids'])==40 and next(r for r in rich if r['original_review_row']==94)['source_occurrence_locator']['ordinal']==1)
check('research_only_no_human_ground_truth_claim',ledger['production_approval'] is ledger['cryptographically_authenticated'] is False and summary['human_final_labels_populated']==0 and ledger['validation_status']=='PENDING_PERSONAL_SUPERVISOR_REVIEW')
before=json.loads((tmp/'implementation-artifacts-before.json').read_text(encoding='utf-8'))
check('all_335_preexisting_implementation_artifacts_byte_identical',all((repo/k).is_file() and hashlib.sha256((repo/k).read_bytes()).hexdigest()==v for k,v in before.items()))
historical=json.loads((tmp/'historical-source-before.json').read_text(encoding='utf-8'))
check('historical_source_file_set_and_bytes_unchanged',historical_inventory(source)==historical)
value=envelope('pending-agent-proposal-verification-v1',{'checks':checks,'checks_passed':len(checks),'proposal_count':120,'counts':summary['proposal_counts'],'historical_source_files':len(historical),'preserved_existing_implementation_artifact_files':len(before),'cohort_fingerprint':cohort['fingerprint'],'research_rubric_fingerprint':inputs['research_rubric_fingerprint'],'proposal_set_fingerprint':ledger['proposal_set_fingerprint'],'official_human_analysis_executed':False,'all_human_decisions_pending':True})
write_bundle(base/'verification',value,{'verify-package.py':Path(__file__).read_text(encoding='utf-8-sig'),'checks.md':'# Targeted pending-proposal package checks\n\n'+'\n'.join('- PASS: '+c['check'] for c in checks)+'\n\nNo full suite, adversarial Gate-A campaign, human-label analysis or Phase-3 work was performed.\n'})
print(json.dumps({'checks_passed':len(checks),'records':120,'counts':summary['proposal_counts'],'historical_source_files_unchanged':len(historical),'preexisting_implementation_artifact_files_unchanged':len(before)},indent=2))
