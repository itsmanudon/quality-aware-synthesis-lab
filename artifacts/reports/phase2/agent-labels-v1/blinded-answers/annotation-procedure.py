"""One-off agent annotation procedure. Reads only the sealed blinded input.

This records proposed judgments under the approved rubric; it is not a new
production validator, independent rater, or authenticated human decision.
"""
from pathlib import Path
import json, math, re
from collections import Counter
from rcqasyn.phase2.common import read_bundle, write_bundle, envelope, digest

BASE=Path(r'D:\Github Repos\quality-aware-synthesis-lab-phase2\artifacts\reports\phase2\agent-labels-v1')
AGENT='OpenAI Codex / RC-QASyn research annotation procedure v1 (2026-10-18)'
EXECUTION='agent-labels-v1/2026-10-18/source-only-pass-1'

def annotate(packet):
    payload=packet['payload']
    fields=packet['field_definitions']
    dataset=packet['dataset_id']
    rules={r['rule_id']:r for r in packet['allowed_evidence']}
    assert all(r['authority']=='AUTHORITATIVE' for r in rules.values())
    expected={f['name'] for f in fields}
    missing=sorted(expected-set(payload))
    extra=sorted(set(payload)-expected)
    failures=[]
    if missing:
        failures.append((dataset+':schema','Absent declared field(s): '+', '.join(missing)+'.'))
    if extra:
        failures.append((dataset+':schema','Undeclared field(s): '+', '.join(extra)+'.'))
    fractional=[]
    unavailable=[]
    support_excursions=[]
    observations=[]
    for field in fields:
        name=field['name']
        if name not in payload:
            observations.append({'field':name,'observation':'ABSENT_KEY','rule_id':dataset+':schema'})
            continue
        value=payload[name]
        if value is None:
            unavailable.append(name)
            observations.append({'field':name,'value':value,'observation':'PRESERVED_MISSING_VALUE; not automatically invalid'})
            continue
        if field['type']=='categorical':
            rid=dataset+(':target-tokens' if name=='class' else ':declared-categories')
            if value not in field['documented_categories']:
                failures.append((rid,f"{name}={value!r} is outside the declared nominal categories {field['documented_categories']}."))
            observations.append({'field':name,'value':value,'observation':'DECLARED_CATEGORY' if value in field['documented_categories'] else 'UNDECLARED_CATEGORY','rule_id':rid})
        else:
            numeric=type(value) in (int,float) and math.isfinite(value)
            if not numeric:
                failures.append((dataset+':schema',f'{name}={value!r} is not a finite numerical value under its declaration.'))
            declaration=field.get('source_declaration','')
            if numeric and declaration.startswith('integer') and value != int(value):
                fractional.append(name)
                failures.append((dataset+':schema',f'{name}={value!r} is non-integral; the authoritative declaration is {declaration}.'))
            observations.append({'field':name,'value':value,'source_declaration':declaration,'observation':'NON_INTEGRAL_INTEGER_FIELD' if name in fractional else 'NUMERIC_TYPE_COMPATIBLE' if numeric else 'NUMERIC_TYPE_VIOLATION','rule_id':dataset+':schema'})
            # Bounds describe source support only. They never change the label.
            match=re.search(r'\[([^,]+),\s*([^\]]+)\]',declaration)
            if numeric and match and not float(match[1]) <= value <= float(match[2]):
                support_excursions.append({'field':name,'value':value,'source_declaration':declaration,'interpretation':'Descriptive source-support excursion only; not invalidity evidence.'})
    assert all(rid in rules and rules[rid]['hard_rejection_allowed'] for rid,_ in failures)
    if failures:
        label='INVALID'
        evidence=sorted({rid for rid,_ in failures})
        rationale=' '.join(text for _,text in failures)+' This is a declared-field/primitive-type violation; no physical relationship, rarity, TRAIN support, or machine judgment is used.'
        uncertainty='Specific schema evidence supports this proposed INVALID judgment. Original target mapping, physical meanings/units and cross-field constraints remain unresolved and are not asserted. Supervisor should inspect the cited declaration and original values.'
        severity='SPECIFIC_AUTHORITATIVE_VIOLATION'
    else:
        label='INDETERMINATE'
        evidence=sorted(rules)
        literals=', '.join(f"{f['name']}={payload.get(f['name'])!r}" for f in fields if f['type']=='categorical')
        rationale=f"Observed {len(payload)} of {len(expected)} declared fields; primitive types and available nominal tokens ({literals}) show no substantiated authoritative violation. This schema evidence does not positively establish record-level validity: original target mapping and physical/cross-field semantics remain unverified. Absence of a detected violation is insufficient for VALID."
        if unavailable:
            rationale+=' Preserved missing values in '+', '.join(unavailable)+' further limit judgment.'
        uncertainty='HIGH: insufficient authoritative evidence for a positive validity judgment; original target semantics, physical meanings/units and cross-field rules remain unresolved. INDETERMINATE is an explicit agent abstention, not an INVALID label or a contribution assessment.'
        severity='HIGH_UNCERTAINTY_INSUFFICIENT_EVIDENCE'
    if support_excursions:
        uncertainty+=' Descriptive source-support excursion(s): '+', '.join(f"{s['field']}={s['value']}" for s in support_excursions)+'. These do not establish invalidity.'
    answer={'blinded_review_id':packet['blinded_review_id'],'proposed_label':label,'proposed_rationale':rationale,'supporting_evidence_ids':evidence,'uncertainty_or_ambiguity':uncertainty}
    detail={'blinded_review_id':packet['blinded_review_id'],'dataset_id':dataset,'payload_sha256':packet['payload_sha256'],'uncertainty_category':severity,'missing_declared_fields':missing,'non_integral_integer_fields':fractional,'preserved_null_fields':unavailable,'field_observations':observations,'authoritative_violation_observations':[{'rule_id':r,'observation':v} for r,v in failures],'source_support_excursions':support_excursions,'unresolved_domain_semantics':True,'lacks_sufficient_authoritative_evidence_for_either_label':label=='INDETERMINATE'}
    return answer,detail

def main():
    inputs=read_bundle(BASE/'labeling-input')
    assert inputs['machine_critic_information_included'] is False
    allowed={'blinded_review_id','dataset_id','payload','payload_sha256','field_definitions','allowed_evidence','known_ambiguity'}
    assert all(set(p)==allowed for p in inputs['primary'])
    assert len(inputs['primary'])==120
    answers=[]
    details=[]
    for packet in inputs['primary']:
        answer,detail=annotate(packet)
        answers.append(answer)
        details.append(detail)
    assert len({a['blinded_review_id'] for a in answers})==120
    value=envelope('agent-blinded-annotation-pass-v1',{
        'annotator_type':'AGENT','annotator_model_or_agent_version':AGENT,'proposal_timestamp_or_execution_identity':EXECUTION,
        'review_status':'PENDING_HUMAN_APPROVAL','human_final_label':None,
        'cohort_fingerprint':inputs['cohort_fingerprint'],'protocol_fingerprint':inputs['protocol_fingerprint'],
        'research_rubric_fingerprint':inputs['research_rubric_fingerprint'],'blinded_input_fingerprint':inputs['fingerprint'],
        'allowed_input_files':['labeling-input/artifact.json','labeling-input/FINALIZED.json'],
        'procedure':'Source-only agent review of declared field membership, mathematical integer compatibility, numeric/nominal types and literal target tokens. A JSON float such as 10.0 is integer-compatible; 10.1 is not. Absent keys are distinguished from preserved nulls. Schema conformance alone never produces VALID. No cross-field physical constraint or source-range rejection is introduced.',
        'external_provider_calls':0,'machine_critic_information_used':False,
        'answers':answers,'observations':details})
    write_bundle(BASE/'blinded-answers',value,{'answers.json':json.dumps(answers,indent=2,sort_keys=True)+'\n','annotation-procedure.py':Path(__file__).read_text(encoding='utf-8-sig')})
    print(json.dumps({'counts':dict(Counter(a['proposed_label'] for a in answers)), 'missing_field_records':sum(bool(d['missing_declared_fields']) for d in details),'fractional_integer_records':sum(bool(d['non_integral_integer_fields']) for d in details),'support_excursions':sum(bool(d['source_support_excursions']) for d in details),'answers_fingerprint':value['fingerprint']},indent=2))

if __name__=='__main__':
    main()
