from __future__ import annotations

import json
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from rcqasyn.datasets.loader import load_dataset
from rcqasyn.datasets.registry import DatasetRegistry
from rcqasyn.datasets.split import _subset_fingerprint
from rcqasyn.metrics.utility import _fit_score, resolve_estimators
from rcqasyn.phase2.common import csv_text, digest, envelope, read_bundle, write_bundle
from rcqasyn.phase5.geometry import complete_record
from rcqasyn.phase5.workflow import Context, load_context

METRICS=("f1","average_precision","pr_auc","balanced_accuracy","mcc","auroc")


def score_regime(real_train: pd.DataFrame, evaluation: pd.DataFrame, synthetic: pd.DataFrame,
                 spec: Any, classifier: str, regime: str, seed: int) -> dict[str,Any]:
    if classifier not in resolve_estimators(seed): raise ValueError("unsupported frozen classifier")
    if regime not in ("TRTR","TSTR","HYBRID_MINORITY"): raise ValueError("unknown utility regime")
    reason=None
    if regime=="TRTR": training=real_train
    elif regime=="TSTR":
        training=synthetic
        if synthetic.empty or synthetic[spec.target_column].nunique()<2:
            reason="UNAVAILABLE_SYNTHETIC_TRAINING_REQUIRES_BOTH_LITERAL_CLASSES"
    else:
        minority=synthetic.loc[synthetic[spec.target_column]==spec.minority_label].copy() if not synthetic.empty else synthetic
        training=pd.concat([real_train,minority],ignore_index=True)
        if minority.empty: reason="UNAVAILABLE_NO_SYNTHETIC_MINORITY_AUGMENTATION"
    if reason:
        result={"status":"unavailable","reason":reason,**dict.fromkeys(METRICS)}
    else:
        result=_fit_score(training,evaluation,spec,resolve_estimators(seed)[classifier])
    return {"regime":regime,"classifier":classifier,"seed":seed,
        "training_n":len(training),"training_class_counts":dict(Counter(training[spec.target_column].astype(str))),
        "evaluation_n":len(evaluation),"evaluation_class_counts":dict(Counter(evaluation[spec.target_column].astype(str))),
        "synthetic_input_n":len(synthetic),"evaluation_result":result,
        "interpretation":"Literal task-class utility on the reused historical TEST split; not human validity performance"}


def outer_frames(frame: pd.DataFrame, split: dict[str,Any]) -> tuple[pd.DataFrame,pd.DataFrame]:
    a,b=split["train_indices"],split["test_indices"]
    if (len(set(a))!=len(a) or len(set(b))!=len(b) or set(a)&set(b) or set(a)|set(b)!=set(frame.index)
            or _subset_fingerprint(frame,a)!=split["train_fingerprint"]
            or _subset_fingerprint(frame,b)!=split["test_fingerprint"]):
        raise ValueError("utility partition/source contradiction")
    return frame.loc[a].copy(),frame.loc[b].copy()


def synthetic_sources(ctx: Context, core: Path, dataset: str) -> list[dict[str,Any]]:
    result=[]; g=ctx.geometries[dataset]
    structural={r["occurrence_id"]:r for r in ctx.m2["evidence"] if r["validator_family"]=="authoritative_structure"}
    for b in ("b1","b2","b3"):
        rows=[o for o in g.occurrences if o["controls"][b]["decision"]["accepted"]
              and structural[o["occurrence_id"]]["authoritative_validity"]!="INVALID"
              and complete_record(o["payload"],ctx.specifications[dataset]["specification"])]
        result.append({"name":b.upper()+"-structural-complete","records":rows,
                       "fingerprint":digest([{k:r[k] for k in ("occurrence_id","payload_sha256")} for r in rows]),
                       "eligibility":"Recorded control acceptance INTERSECT authoritative-structure-compatible complete payloads; separately named filtered control"})
    manifest=read_bundle(core/"manifest")
    for row in manifest["constructions"]:
        if row["dataset_id"]!=dataset: continue
        name=f"{dataset}-{row['strategy']}-{row['condition']}"
        value=read_bundle(core/"constructions"/name)
        if value["fingerprint"]!=row["fingerprint"]: raise ValueError("utility construction source mismatch")
        result.append({"name":row["strategy"]+":"+row["condition"],"records":value["selected_records"],
                       "fingerprint":value["fingerprint"],"eligibility":"Audited M7 fixed-budget provisional construction"})
    return result


def run_utility(root: Path, source: Path, core: Path, output: Path, plan: dict[str,Any]) -> dict[str,Any]:
    start=time.perf_counter(); ctx=load_context(root,source)
    manifest=read_bundle(core/"manifest")
    if manifest["plan_fingerprint"]!=digest(plan): raise ValueError("utility plan differs from predeclared core study")
    registry=DatasetRegistry(project_root=source); rows=[]; populations=[]
    for d in sorted(ctx.geometries):
        spec=registry.get(d); loaded=load_dataset(spec,registry)
        split=json.loads((source/f"data/manifests/{d}/split_manifest.json").read_text())
        train,test=outer_frames(loaded.frame,split)
        populations.append({"dataset_id":d,"split_fingerprint":split["split_fingerprint"],
            "train_fingerprint":split["train_fingerprint"],"test_fingerprint":split["test_fingerprint"],
            "train_indices":split["train_indices"],"test_indices":split["test_indices"],
            "train_class_counts":dict(Counter(train[spec.target_column])),"test_class_counts":dict(Counter(test[spec.target_column]))})
        empty=pd.DataFrame(columns=[*spec.feature_columns,spec.target_column])
        for classifier in plan["utility"]["classifiers"]:
            rows.append({"dataset_id":d,"method":"REAL_TRAIN","source_fingerprint":split["train_fingerprint"],
                         **score_regime(train,test,empty,spec,classifier,"TRTR",plan["utility"]["seed"])})
        for synthetic in synthetic_sources(ctx,core,d):
            frame=pd.DataFrame([r["payload"] for r in synthetic["records"]],columns=[*spec.feature_columns,spec.target_column])
            if any(not complete_record(r["payload"],ctx.specifications[d]["specification"]) for r in synthetic["records"]):
                raise ValueError("invalid or missing-class synthetic record cannot enter utility")
            for classifier in plan["utility"]["classifiers"]:
                for regime in ("TSTR","HYBRID_MINORITY"):
                    rows.append({"dataset_id":d,"method":synthetic["name"],"source_fingerprint":synthetic["fingerprint"],
                        **score_regime(train,test,frame,spec,classifier,regime,plan["utility"]["seed"])})
    value=envelope("m9-classification-utility-v1",{"predeclared_plan_fingerprint":digest(plan),
        "implementation_revision":subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip(),
        "core_manifest_fingerprint":manifest["fingerprint"],"populations":populations,"results":rows,
        "result_content_fingerprint":digest(rows),"source_metric_module":"Frozen rcqasyn.metrics.utility._fit_score",
        "classifier_parameters":{name:model.get_params(deep=True) for name,model in resolve_estimators(plan["utility"]["seed"]).items()},
        "status_counts":dict(Counter(r["evaluation_result"]["status"] for r in rows)),
        "test_used_for_evaluation_only":True,"test_used_for_selection_or_tuning":False,
        "test_previously_evaluated":True,"human_validity_metrics_computed":False,
        "independent_repetitions":1,"replay_is_not_an_independent_repetition":True,
        "runtime_seconds":time.perf_counter()-start})
    write_bundle(output,value,{"utility.csv":csv_text([{k:v for k,v in r.items() if k!="evaluation_result"}|r["evaluation_result"] for r in rows])})
    return value
