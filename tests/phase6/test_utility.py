from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from rcqasyn.datasets.split import _subset_fingerprint
from rcqasyn.phase6 import utility


def frames():
    train=pd.DataFrame({"x":[0.,1.,2.,3.],"class":["negative","negative","positive","positive"]})
    test=pd.DataFrame({"x":[.5,2.5],"class":["negative","positive"]})
    spec=SimpleNamespace(target_column="class",minority_label="positive",feature_columns=["x"],numerical_columns=["x"],categorical_columns=[])
    return train,test,spec


def test_tstr_one_class_is_unavailable_not_hybrid():
    train,test,spec=frames()
    result=utility.score_regime(train,test,train.iloc[:2],spec,"logistic_regression","TSTR",42)
    assert result["evaluation_result"]["status"]=="unavailable" and result["training_n"]==2
    assert result["evaluation_result"]["f1"] is None


def test_hybrid_without_synthetic_minority_is_unavailable():
    train,test,spec=frames()
    result=utility.score_regime(train,test,train.iloc[:2],spec,"logistic_regression","HYBRID_MINORITY",42)
    assert result["evaluation_result"]["status"]=="unavailable"


def test_trtr_tstr_and_hybrid_use_correct_training_populations(monkeypatch):
    train,test,spec=frames(); fitted=[]
    def record(a,b,*args):
        fitted.append(a.copy()); return {"status":"ok","f1":.5}
    monkeypatch.setattr(utility,"_fit_score",record)
    utility.score_regime(train,test,train,spec,"logistic_regression","TRTR",42)
    utility.score_regime(train,test,train,spec,"logistic_regression","TSTR",42)
    utility.score_regime(train,test,train,spec,"logistic_regression","HYBRID_MINORITY",42)
    assert len(fitted[0])==4 and len(fitted[1])==4 and len(fitted[2])==6
    assert list(fitted[2]["class"]).count("positive")==4


@pytest.mark.parametrize("regime",["TRTR","TSTR","HYBRID_MINORITY"])
def test_actual_frozen_metric_execution_deterministic(regime):
    train,test,spec=frames()
    a=utility.score_regime(train,test,train,spec,"logistic_regression",regime,42)
    assert a==utility.score_regime(train,test,train,spec,"logistic_regression",regime,42)
    assert a["evaluation_result"]["status"]=="ok"
    assert a["evaluation_result"]["pr_auc"]==a["evaluation_result"]["average_precision"]


def test_outer_identity_and_fingerprint_enforced():
    train,test,_=frames(); frame=pd.concat([train,test],ignore_index=True)
    split={"train_indices":[0,1,2,3],"test_indices":[4,5],"train_fingerprint":_subset_fingerprint(frame,[0,1,2,3]),"test_fingerprint":_subset_fingerprint(frame,[4,5])}
    a,b=utility.outer_frames(frame,split)
    assert len(a)==4 and len(b)==2 and not set(a.index)&set(b.index)
    frame.loc[4,"x"]=999.
    with pytest.raises(ValueError): utility.outer_frames(frame,split)


def test_unknown_regime_and_classifier_refused():
    train,test,spec=frames()
    with pytest.raises(ValueError): utility.score_regime(train,test,train,spec,"neural","TSTR",42)
    with pytest.raises(ValueError): utility.score_regime(train,test,train,spec,"random_forest","MIXED_TSTR",42)


def test_cli_source_root_option():
    from typer.testing import CliRunner

    from rcqasyn.phase6.cli import app
    result=CliRunner().invoke(app,["core","--help"])
    assert result.exit_code==0 and "source-root" in result.stdout
