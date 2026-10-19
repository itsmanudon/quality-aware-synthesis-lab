from __future__ import annotations

import copy
from decimal import Decimal

import pytest

from rcqasyn.phase2.common import digest, envelope
from rcqasyn.phase3.contracts import M2Config
from rcqasyn.phase3.validators import TrainEvidenceModel
from rcqasyn.phase6.repair import nearest_integer, propose_repair


@pytest.fixture
def model():
    spec=envelope("dataset-specification-v1",{"specification":{"dataset_id":"fixture",
        "features":[*[{"name":f,"type":"numerical","source_declaration":"integer [0,10]"} for f in ("x","y","z","w")],
                    {"name":"cat","type":"categorical","documented_categories":["a","b"]}],
        "target_semantics":{"target_column":"class","literal_labels":["negative","positive"]},
        "rules":[{"rule_id":"fixture:"+s,"authority":"AUTHORITATIVE","hard_rejection_allowed":True,"evidence":["fixture/schema"]} for s in ("schema","declared-categories","target-tokens")]}})
    records=[{"x":i,"y":i,"z":i,"w":i,"cat":"a" if i<3 else "b","class":"negative" if i<3 else "positive"} for i in range(4)]
    return TrainEvidenceModel(spec,(0,1,2,3),records,M2Config())


def occurrence(**changes):
    payload={"x":1,"y":1,"z":1,"w":1,"cat":"a","class":"negative",**changes}
    return {"occurrence_id":"fixture:parent","payload":payload,"payload_sha256":digest(payload),
            "dataset_id":"fixture","source_artifact":"fixture/source","source_artifact_sha256":"a"*64,"source_occurrence_ordinal":1}


def proposal(model,o):
    return propose_repair(o,model.specification,model.score(o)[0].model_dump(mode="json"))


@pytest.mark.parametrize("x,expected",[(.5,0),(1.5,2),(2.5,2),(3.5,4),(-.5,0),(-1.5,-2),(-2.5,-2),(-3.5,-4),(1.4999999999999998,1),(1.5000000000000002,2)])
def test_explicit_decimal_half_even_and_bound(x,expected):
    result,change=nearest_integer(x)
    assert result==expected and change<=Decimal(".5")


@pytest.mark.parametrize("x",[True,float("nan"),float("inf"),"1.5",None])
def test_unsupported_rounding_inputs_refused(x):
    with pytest.raises(ValueError): nearest_integer(x)


def test_three_fields_repair_preserves_original_and_integral_values(model):
    o=occurrence(x=1.5,y=2.5,z=-.5,w=10.0); before=copy.deepcopy(o)
    a=proposal(model,o)
    assert a==proposal(model,o) and o==before
    assert a["eligibility"]=="REPAIR_ELIGIBLE" and a["edited_fields"]==3
    assert a["repaired_payload"]=={**o["payload"],"x":2,"y":2,"z":0}
    assert isinstance(a["repaired_payload"]["w"],float)
    assert a["derived_occurrence_id"]!=o["occurrence_id"]
    assert all(e["absolute_change"]<=.5 for e in a["edits"])
    derived={**o,"occurrence_id":a["derived_occurrence_id"],"payload":a["repaired_payload"],"payload_sha256":a["repaired_payload_sha256"]}
    assert proposal(model,derived)["eligibility"]=="NOT_NEEDED"
    assert model.score(derived)[0].authoritative_validity=="NOT_ESTABLISHED"


def test_four_fields_refuses_entire_record(model):
    a=proposal(model,occurrence(x=1.1,y=2.1,z=3.1,w=4.1))
    assert a["eligibility"]=="REPAIR_INELIGIBLE" and a["derived_occurrence_id"] is None
    assert not a["edits"] and "MORE_THAN_THREE_INTEGER_FIELDS" in a["reasons"]


@pytest.mark.parametrize("defect",["class","feature","nominal","primitive","null","extra","requested_class"])
def test_other_violations_do_not_become_complete_repair(model,defect):
    o=occurrence(x=1.5)
    if defect=="class": o["payload"].pop("class")
    if defect=="feature": o["payload"].pop("y")
    if defect=="nominal": o["payload"]["cat"]="unsupported"
    if defect=="primitive": o["payload"]["y"]="1"
    if defect=="null": o["payload"]["y"]=None
    if defect=="extra": o["payload"]["additional"]=1
    if defect=="requested_class":
        o["payload"].pop("class"); o["requested_class"]="negative"
    o["payload_sha256"]=digest(o["payload"])
    a=proposal(model,o)
    assert a["eligibility"]=="REPAIR_INELIGIBLE" and a["repaired_payload"] is None


def test_integral_outlier_or_rare_category_is_not_repaired(model):
    a=proposal(model,occurrence(x=1000.,cat="b"))
    assert a["eligibility"]=="NOT_NEEDED" and not a["edits"]


def test_source_binding_mismatch_refused(model):
    o=occurrence(x=1.5); structural=model.score(o)[0].model_dump(mode="json")
    structural["payload_sha256"]="0"*64
    with pytest.raises(ValueError,match="source"):
        propose_repair(o,model.specification,structural)


@pytest.mark.parametrize("known",[True,False])
def test_independently_authoritative_postcondition_refuses(model,known):
    data=copy.deepcopy(model.specification)
    rule={"rule_id":"fixture:independent-bound","authority":"AUTHORITATIVE","hard_rejection_allowed":True,"evidence":["fixture/source-bound"]}
    if known: rule["numeric_bounds"]={"field":"x","maximum":1.8}
    data["specification"]["rules"].append(rule)
    data=envelope("dataset-specification-v1",{k:v for k,v in data.items() if k!="fingerprint"})
    model.specification=data; model.spec=data["specification"]
    a=proposal(model,occurrence(x=1.5))
    assert a["eligibility"]=="REPAIR_INELIGIBLE" and not a["repair_attempted"]
    assert any("AUTHORITATIVE" in reason for reason in a["reasons"])
