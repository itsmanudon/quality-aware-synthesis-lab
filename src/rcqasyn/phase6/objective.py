from __future__ import annotations

import copy
import json
from typing import Any

import numpy as np

from rcqasyn.phase2.common import digest
from rcqasyn.phase3.contracts import M2Config
from rcqasyn.phase3.validators import TrainEvidenceModel
from rcqasyn.phase4.contracts import EvidenceVector, Policy
from rcqasyn.phase4.fusion import decide, mid_percentile
from rcqasyn.phase5.workflow import Context


def restore_model(ctx: Context, dataset: str) -> TrainEvidenceModel:
    """Restore recorded coefficients and TRAIN rows; do not call fitting/constructor."""
    p = ctx.m2["model_parameters"][dataset]; ref = ctx.geometries[dataset].reference
    model = object.__new__(TrainEvidenceModel)
    model.specification = ctx.specifications[dataset]; model.spec = model.specification["specification"]
    model.dataset = dataset; model.fields = list(model.spec["features"])
    model.numeric = p["numeric_fields"]; model.categorical = p["categorical_fields"]
    model.target = model.spec["target_semantics"]["target_column"]
    model.records = ref["records"]; model.row_ids = tuple(ref["train_indices"])
    model.config = M2Config.model_validate_json(json.dumps(ctx.m2["configuration"]))
    model.configuration = digest(model.config.model_dump(mode="json"))
    model.reference = ref["m2_train_reference_fingerprint"]
    model.eligible = [r for r in model.records if not model.unsupported(r)]
    model.eligible_ids = [i for i,r in zip(model.row_ids,model.records,strict=True) if not model.unsupported(r)]
    model.x = np.array([[r[f] for f in model.numeric] for r in model.eligible],dtype=float)
    model.spans = np.array(p["gower_spans"]); model.medians = np.array(p["robust_medians"])
    model.scales = np.array(p["robust_scales"]); model.categories = p["train_categories"]
    model.center = np.array(p["cross_feature_center"]); model.precision = np.array(p["cross_feature_precision"])
    model.dimension = len(model.center)
    model.train_scores = np.array([model.global_score(model.encode(r)) for r in model.eligible])
    return model


def frozen_vector(ctx: Context, parent_id: str, evidence: list[dict[str,Any]]) -> dict[str,Any]:
    base = copy.deepcopy(next(v for v in ctx.shadow["harmonized"]["vectors"] if v["occurrence_id"]==parent_id))
    base.pop("fingerprint")
    rows = {r["validator_family"]: r for r in evidence}
    first = rows["authoritative_structure"]
    base.update(occurrence_id=first["occurrence_id"],payload_sha256=first["payload_sha256"],
                input_evidence_fingerprints={f:digest(r) for f,r in rows.items()})
    for key in base["structural"]:
        base["structural"][key] = first[key]
    for f in ("local_support","cross_feature"):
        ref = ctx.shadow["harmonized"]["references"][first["dataset_id"]][f]
        score = rows[f]["raw_score"] if rows[f]["status"]=="AVAILABLE" else None
        percentile,state = mid_percentile(score,[r["raw_score"] for r in ref["members"]],ref["minimum_n"])
        base["normalized"][f].update(raw_score=rows[f]["raw_score"],percentile=percentile,state=state,input_status=rows[f]["status"])
    base["family_reasons"] = {f:{k:r[k] for k in ("reason_codes","uncertainty","unsupported_fields")} for f,r in rows.items()}
    values = [base["normalized"][f]["percentile"] for f in ("local_support","cross_feature")]
    complete = all(v is not None for v in values)
    base["fusion"].update(complete=complete,uncalibrated_max=max(values) if complete else None,uncalibrated_min=min(values) if complete else None)
    value = EvidenceVector.model_validate_json(json.dumps(base)).model_dump(mode="json")
    return {**value,"fingerprint":digest(value)}


def reevaluate(ctx: Context, model: TrainEvidenceModel, proposal: dict[str,Any]) -> dict[str,Any]:
    derived = {"occurrence_id":proposal["derived_occurrence_id"],"dataset_id":proposal["dataset_id"],
               "payload":proposal["repaired_payload"],"payload_sha256":proposal["repaired_payload_sha256"]}
    evidence = [r.model_dump(mode="json") for r in model.score(derived)]
    vector = frozen_vector(ctx,proposal["parent_occurrence_id"],evidence)
    policy = next(r["policy"] for r in ctx.shadow["decisions"] if r["policy"]["name"]=="combined-review")
    decision = decide(vector,Policy.model_validate_json(json.dumps(policy)))
    structural = evidence[0]
    compatible = structural["authoritative_validity"]!="INVALID" and structural["status"]=="AVAILABLE"
    return {"evidence":evidence,"vector":vector,"decision":decision,
            "post_repair_structural_status":"STRUCTURALLY_COMPATIBLE_NOT_HUMAN_VALID" if compatible else "STRUCTURALLY_INVALID" if structural["authoritative_validity"]=="INVALID" else "UNRESOLVED",
            "repair_outcome":"REPAIR_APPLIED" if compatible else "REPAIR_FAILED",
            "frozen_reference_fingerprints":{f:ctx.shadow["harmonized"]["references"][proposal["dataset_id"]][f]["fingerprint"] for f in ("local_support","cross_feature")}}
