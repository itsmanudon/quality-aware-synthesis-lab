from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest

from rcqasyn.datasets.split import _subset_fingerprint
from rcqasyn.phase2.common import digest, envelope, read_bundle
from rcqasyn.phase3.contracts import M2Config
from rcqasyn.phase3.validators import TrainEvidenceModel
from rcqasyn.phase5.contracts import STRATEGIES, SelectionConfig
from rcqasyn.phase5.geometry import Geometry, complete_record, metrics, reference_from_frame
from rcqasyn.phase5.selection import select
from rcqasyn.phase5.workflow import Context, audit, construct, pool, write_constructed


@pytest.fixture
def fixture():
    fields = [{"name": "x", "type": "numerical", "source_declaration": "real [0, 10]"},
              {"name": "cat", "type": "categorical", "documented_categories": ["a", "b"]}]
    spec = envelope("dataset-specification-v1", {"specification": {"dataset_id": "fixture", "features": fields,
        "target_semantics": {"target_column": "class", "literal_labels": ["major", "minor"]}}, "source_files": {}})
    records = [{"x": 0., "cat": "a", "class": "major"}, {"x": 0., "cat": "a", "class": "major"},
               {"x": 5., "cat": "a", "class": "major"}, {"x": 10., "cat": "b", "class": "minor"}]
    frame = pd.DataFrame([*records, {"x": 999., "cat": "other", "class": "TEST_ONLY"}])
    split = {"dataset_id": "fixture", "train_indices": [0,1,2,3], "test_indices": [4], "train_fingerprint": _subset_fingerprint(frame,[0,1,2,3])}
    params = {"numeric_fields": ["x"], "categorical_fields": ["cat"], "gower_spans": [10.]}
    ref = reference_from_frame(spec,frame,split,params)
    payloads = [records[0], records[0], records[2], records[3], {"x": .1,"cat":"a","class":"major"}]
    occurrences = [{"occurrence_id": f"fixture:{i}", "dataset_id": "fixture", "payload": r,
        "payload_sha256": digest(r), "source_occurrence_ordinal": i+1,
        "source_artifact": "fixture.json", "source_artifact_sha256": "a"*64,
        "controls": {"b2": {"decision": {"accepted": i!=1}}}} for i,r in enumerate(payloads)]
    g = Geometry(ref,occurrences,fields,"class")
    return spec,records,frame,split,params,g


@pytest.fixture
def ctx(fixture,tmp_path):
    spec,_,_,_,_,g = fixture
    decisions = [{"occurrence_id": r["occurrence_id"], "payload_sha256": r["payload_sha256"],
        "dataset_id":"fixture", "policy":{"name":"combined-review"}, "action":"PROVISIONAL_PASS",
        "structural_judgment":"NOT_ESTABLISHED", "fingerprint":digest(r)} for r in g.occurrences]
    vectors = [{"occurrence_id":r["occurrence_id"], "fusion":{"uncalibrated_max": .2}} for r in g.occurrences]
    return Context(tmp_path,tmp_path,{"fingerprint":"a"*64,"decisions":decisions,"harmonized":{"vectors":vectors}},
                   {"fingerprint":"b"*64},[{"fingerprint":"c"*64,"records":g.occurrences}],{"fixture":g},{"fixture":spec},{})


def config(strategy="source-order",budget=3,**kwargs):
    return SelectionConfig(strategy=strategy,budget=budget,**kwargs)


@pytest.mark.parametrize("strategy",STRATEGIES)
def test_selection_deterministic_budget_and_original_identity(fixture,strategy):
    *_,g = fixture; eligible=list(range(5)); concern=dict.fromkeys(eligible,.2)
    before=copy.deepcopy(g.occurrences)
    a=select(g,eligible,concern,config(strategy))
    assert a == select(g,list(reversed(eligible)),concern,config(strategy))
    assert a["budget_achieved"] == 3 and a["shortfall"] == 0
    assert g.occurrences == before
    assert len(set(a["selected_indices"])) == 3


def test_mixed_metric_is_exact_existing_phase3_function(fixture):
    spec,records,_,_,_,g=fixture
    model=TrainEvidenceModel(spec,(0,1,2,3),records,M2Config())
    for i,o in enumerate(g.occurrences):
        assert np.array_equal(g.to_train[i],model.distances(o["payload"]))
    assert g.to_train[0,3] == 1.  # clipped numeric difference plus nominal mismatch
    assert g.to_train[0,2] == .25


def test_known_coverage_duplicates_and_dense_concentration(fixture):
    *_,g=fixture
    m=metrics(g,[0,1],list(range(5)),.05,.01)
    assert m["train_row_coverage"] == .5
    assert m["unique_train_feature_coverage"] == pytest.approx(1/3)
    assert m["exact_duplicate_rate"] == .5 and m["near_duplicate_rate"] == 1.
    assert m["nearest_train_region_hhi"] == 1.
    assert m["class_coverage"]["minor"]["coverage_by_same_declared_class"] == 0.
    n=metrics(g,[0,4],list(range(5)),.05,.01)
    assert n["exact_duplicate_rate"] == 0. and n["near_duplicate_rate"] == 1.


def test_source_and_diversity_controls_with_stable_ties(fixture):
    *_,g=fixture; ids=list(range(5)); c=dict.fromkeys(ids,.2)
    assert select(g,ids,c,config())["selected_indices"] == [0,1,2]
    assert select(g,ids,c,config("farthest-first"))["selected_indices"] == [0,3,2]
    assert select(g,ids,c,config("coverage-greedy"))["selected_indices"] == [0,2,3]


def test_quality_quota_dedup_and_exhaustion(fixture):
    *_,g=fixture; ids=list(range(5)); c=dict.fromkeys(ids,.2)
    result=select(g,ids,c,config("quality-coverage",9))
    assert result["selected_indices"][0] == 3
    assert result["budget_achieved"] == 4 and result["shortfall"] == 5
    assert result["minority_quota_requested"] == 4 and result["minority_quota_feasible"] == 1
    assert result["metrics"]["exact_duplicate_rate"] == 0.
    assert all(r["marginal_weighted_coverage"] >= 0 for r in result["trace"])


@pytest.mark.parametrize("budget",[0,1,8])
def test_empty_singleton_and_budget_exhaustion(fixture,budget):
    *_,g=fixture; r=select(g,list(range(5)),dict.fromkeys(range(5),.2),config(budget=budget))
    assert r["budget_achieved"] == min(budget,5)
    assert r["shortfall"] == max(0,budget-5)
    if budget <= 1: assert r["metrics"]["nearest_selected_distance"]["n"] == 0


def test_empty_pool_explicit(fixture):
    *_,g=fixture; r=select(g,[],{},config())
    assert r["shortfall"] == 3 and r["metrics"]["train_row_coverage"] == 0.


@pytest.mark.parametrize("bad",["missing_class","requested_class","missing_feature","null","bad_token","bool","extra"])
def test_complete_original_labeled_generation_contract(fixture,bad):
    spec,*_=fixture; payload={"x":1.,"cat":"a","class":"major"}
    if bad in ("missing_class","requested_class"): del payload["class"]
    if bad=="requested_class": payload["requested_class"]="major"
    if bad=="missing_feature": del payload["x"]
    if bad=="null": payload["x"]=None
    if bad=="bad_token": payload["class"]="unknown"
    if bad=="bool": payload["x"]=True
    if bad=="extra": payload["arbitrary"]=1
    assert not complete_record(payload,spec["specification"])


def test_integer_compatibility_and_no_range_rule(fixture):
    spec,*_=fixture; s=copy.deepcopy(spec["specification"]); s["features"][0]["source_declaration"]="integer [0,10]"
    assert complete_record({"x":1000.,"cat":"a","class":"minor"},s)
    assert not complete_record({"x":1.5,"cat":"a","class":"minor"},s)


def test_test_only_changes_do_not_enter_reference_or_geometry(fixture):
    spec,_,frame,split,params,g=fixture
    frame.loc[4]=[-999.,"CHANGED_TEST_ONLY","NEW_TEST_CLASS"]
    changed=reference_from_frame(spec,frame,split,params)
    assert changed == g.reference
    other=Geometry(changed,g.occurrences,g.fields,g.target)
    assert np.array_equal(g.to_train,other.to_train)


@pytest.mark.parametrize("bad",["train_value","overlap","foreign_span","foreign_dataset"])
def test_train_membership_and_fingerprints_refused(fixture,bad):
    spec,_,frame,split,params,_=copy.deepcopy(fixture)
    if bad=="train_value": frame.loc[0,"x"]=123.
    if bad=="overlap": split["train_indices"].append(4)
    if bad=="foreign_span": params["gower_spans"]=[999.]
    if bad=="foreign_dataset": split["dataset_id"]="foreign"
    with pytest.raises(ValueError): reference_from_frame(spec,frame,split,params)


def test_sparse_train_and_constant_fields(fixture):
    spec,_,frame,_,_,_=fixture
    split={"dataset_id":"fixture","train_indices":[0],"test_indices":[1,2,3,4],"train_fingerprint":_subset_fingerprint(frame,[0])}
    ref=reference_from_frame(spec,frame,split,{"numeric_fields":["x"],"categorical_fields":["cat"],"gower_spans":[0.]})
    assert ref["records"] == [{"x":0.,"cat":"a","class":"major"}]


@pytest.mark.parametrize("action",["REJECT_STRUCTURAL","REVIEW_REQUIRED","ABSTAIN"])
def test_nonprovisional_records_excluded(ctx,action):
    ctx.shadow["decisions"][0]["action"]=action
    if action=="REJECT_STRUCTURAL": ctx.shadow["decisions"][0]["structural_judgment"]="INVALID"
    eligible,_,ledger=pool(ctx,"fixture",config())
    assert 0 not in eligible and not ledger[0]["eligible"]


def test_b2_intersection_preserved(ctx):
    ids,_,_=pool(ctx,"fixture",config(control_intersection="b2"))
    assert ids == [0,2,3,4]


@pytest.mark.parametrize("mutation",["payload","label","order","count","metrics","duplicate","source","quota","reference"])
def test_dataset_audit_rejects_contradictions(ctx,mutation):
    value=construct(ctx,"fixture",config(),"fixture-revision")
    if mutation=="payload": value["selected_records"][0]["payload"]["x"]=999.
    if mutation=="label": value["selected_records"][0]["payload"].pop("class")
    if mutation=="order": value["selected_records"].reverse()
    if mutation=="count": value["budget_achieved"]=99
    if mutation=="metrics": value["metrics"]["exact_duplicate_rate"]=.99
    if mutation=="duplicate": value["selected_records"][1]=copy.deepcopy(value["selected_records"][0])
    if mutation=="source": value["source_crosswalk_fingerprint"]="0"*64
    if mutation=="quota": value["minority_quota_feasible"]=123
    if mutation=="reference": value["reference_fingerprint"]="0"*64
    value=envelope(value["schema_version"],{k:v for k,v in value.items() if k!="fingerprint"})
    with pytest.raises(ValueError): audit(ctx,value)


def test_guarded_outputs_and_label_preservation(ctx,tmp_path):
    value=construct(ctx,"fixture",config(),"fixture-revision"); path=tmp_path/"constructed"
    assert write_constructed(ctx,path,value)["status"] == "PASS"
    assert read_bundle(path)==value
    assert all(r["payload"]["class"]=="major" for r in value["selected_records"])
    assert write_constructed(ctx,path,value)["status"] == "PASS"
    other=construct(ctx,"fixture",config("farthest-first"),"fixture-revision")
    with pytest.raises(FileExistsError): write_constructed(ctx,path,other)
    (path/"dataset.csv").write_text("tampered")
    with pytest.raises(ValueError): read_bundle(path)


def test_cli_declares_required_source_option():
    from typer.testing import CliRunner

    from rcqasyn.phase5.cli import app
    result=CliRunner().invoke(app,["audit","--help"])
    assert result.exit_code==0 and "source-root" in result.stdout
