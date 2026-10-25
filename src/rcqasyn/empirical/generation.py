"""Train-only established oversamplers, with no integer/categorical coercion."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE, SMOTENC, RandomOverSampler
from sklearn.preprocessing import StandardScaler

from rcqasyn.phase2.common import digest, envelope
from rcqasyn.phase3.contracts import M2Config
from rcqasyn.phase3.validators import TrainEvidenceModel
from rcqasyn.phase5.geometry import Geometry, complete_record


def generate(train: pd.DataFrame, spec: Any, method: str, budget: int,
             seed: int) -> tuple[pd.DataFrame, dict[str, Any]]:
    if budget < 1 or not train.index.is_unique:
        raise ValueError("invalid generation budget/TRAIN identities")
    positive = spec.minority_label
    n = int((train[spec.target_column] == positive).sum())
    if n < 2:
        raise ValueError("insufficient TRAIN minority support")
    x: Any = train[list(spec.feature_columns)].copy()
    strategy: Any = {positive: n+budget}
    scaler: Any = None
    sampler: Any
    if method != "RandomOverSampler":
        if x.isna().any().any():
            raise ValueError("offline interpolation does not impute missing source fields")
        scaler = StandardScaler().fit(x[list(spec.numerical_columns)])
        x[list(spec.numerical_columns)] = scaler.transform(x[list(spec.numerical_columns)])
    k = min(5, n-1)
    if method == "RandomOverSampler":
        sampler = RandomOverSampler(sampling_strategy=strategy, random_state=seed)
    elif method == "SMOTENC" and spec.categorical_columns:
        sampler = SMOTENC(categorical_features=list(spec.categorical_columns),
                          sampling_strategy=strategy, random_state=seed, k_neighbors=k)
    elif method == "SMOTE" and not spec.categorical_columns:
        sampler = SMOTE(sampling_strategy=strategy, random_state=seed, k_neighbors=k)
    else:
        raise ValueError("oversampler incompatible with declared feature types")
    # Float numerical dtypes prevent library reconstruction truncating interpolated integers.
    x[list(spec.numerical_columns)] = x[list(spec.numerical_columns)].astype(float)
    xr, yr = sampler.fit_resample(x, train[spec.target_column])
    generated = xr.iloc[len(train):].copy().reset_index(drop=True)
    if scaler is not None:
        generated[list(spec.numerical_columns)] = scaler.inverse_transform(
            generated[list(spec.numerical_columns)])
    elif method == "RandomOverSampler":
        # Copy original values rather than introduce a floating inverse-transform round trip.
        generated = train.iloc[sampler.sample_indices_[len(train):]][
            list(spec.feature_columns)].reset_index(drop=True).copy()
    generated[spec.target_column] = np.asarray(yr)[len(train):]
    if len(generated) != budget or set(generated[spec.target_column]) != {positive}:
        raise ValueError("oversampler output budget/class contradiction")
    provenance = {"generator": method, "seed": seed, "budget": budget, "k_neighbors": k,
                  "fit_row_ids": [int(i) for i in train.index],
                  "train_payload_fingerprint": digest(train.to_dict(orient="split")),
                  "sampling_strategy": strategy, "integer_rounding": False,
                  "numerical_scaler": {"mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist()}
                  if scaler is not None else None,
                  "payload_fingerprint": digest(generated.to_dict(orient="records"))}
    if method == "RandomOverSampler":
        provenance["copied_train_row_ids"] = [int(train.index[i]) for i in
                                                sampler.sample_indices_[len(train):]]
    return generated, provenance


def fresh_geometry(train: pd.DataFrame, candidates: pd.DataFrame, specification: dict[str, Any],
                   split_fingerprint: str, provenance: dict[str, Any]
                   ) -> tuple[Geometry, dict[str, list[int]], dict[int, float], dict[str, Any]]:
    """Refit existing M2 and reuse existing M7; no historical model/reference."""
    train_records = train.to_dict(orient="records")
    row_ids = tuple(int(i) for i in train.index)
    model = TrainEvidenceModel(specification, row_ids, train_records, M2Config())
    spec = specification["specification"]
    rows = []
    for ordinal, payload in enumerate(candidates.to_dict(orient="records")):
        identity = "offline:"+digest({"split": split_fingerprint, "ordinal": ordinal,
                                      "generator": provenance, "payload": payload})
        rows.append({"occurrence_id": identity, "payload": payload,
                     "payload_sha256": digest(payload), "dataset_id": spec["dataset_id"],
                     "source_occurrence_ordinal": ordinal})
    scores = [[e.model_dump(mode="json") for e in model.score(row)] for row in rows]
    ranks: dict[str, dict[int, float]] = {}
    for family in ["local_support", "cross_feature"]:
        raw = {i: next(e["raw_score"] for e in es if e["validator_family"] == family)
               for i, es in enumerate(scores)}
        reference = np.array([v for v in raw.values() if v is not None])
        ranks[family] = {i: float((np.sum(reference < s)+.5*np.sum(reference == s))/len(reference))
                         for i, s in raw.items() if s is not None and len(reference) >= 10}
    schema = [i for i, row in enumerate(rows) if complete_record(row["payload"], spec)
              and scores[i][0]["authoritative_validity"] != "INVALID"]
    local = [i for i in schema if ranks["local_support"].get(i, 1) < .9]
    glob = [i for i in schema if ranks["cross_feature"].get(i, 1) < .9]
    combined = sorted(set(local) & set(glob))
    concerns = {i: max(ranks["local_support"].get(i, 1), ranks["cross_feature"].get(i, 1))
                for i in range(len(rows))}
    reference = envelope("m7-train-reference-v1", {
        "train_indices": list(row_ids), "records": train_records,
        "supported_indices": model.eligible_ids,
        "excluded_indices": [i for i in row_ids if i not in model.eligible_ids],
        "numeric_fields": model.numeric, "categorical_fields": model.categorical,
        "gower_spans": model.spans.tolist(), "dataset_id": model.dataset,
        "real_test_values_used": False, "split_fingerprint": split_fingerprint})
    geometry = Geometry(reference, rows, spec["features"], model.target)
    evidence = {"scores": scores, "ranks": ranks, "train_reference": reference,
                "model_reference_fingerprint": model.reference,
                "model_parameters": {"medians": model.medians.tolist(),
                                     "scales": model.scales.tolist(),
                                     "center": model.center.tolist(),
                                     "precision": model.precision.tolist()},
                "candidate_records": rows, "generation": provenance}
    return geometry, {"schema": schema, "local": local, "global": glob,
                      "combined": combined}, concerns, evidence
