from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from rcqasyn.phase2.common import digest

from .contracts import M2Config, M2Evidence

FAMILIES = ("authoritative_structure", "local_support", "cross_feature")


def number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


@dataclass
class TrainEvidenceModel:
    """One deterministic TRAIN-only fit shared by the complementary validators."""

    specification: dict[str, Any]
    row_ids: tuple[int, ...]
    records: list[dict[str, Any]]
    config: M2Config

    def __post_init__(self) -> None:
        if len(self.row_ids) != len(self.records) or len(set(self.row_ids)) != len(self.row_ids):
            raise ValueError("TRAIN identities must be unique and match records")
        self.spec = self.specification["specification"]
        self.dataset = self.spec["dataset_id"]
        self.fields = list(self.spec["features"])
        self.numeric = [f["name"] for f in self.fields if f["type"] == "numerical"]
        self.categorical = [f["name"] for f in self.fields if f["type"] == "categorical"]
        self.target = self.spec["target_semantics"]["target_column"]
        self.reference = digest({"dataset_id": self.dataset, "train_row_ids": self.row_ids,
                                 "train_records": self.records})
        self.configuration = digest(self.config.model_dump(mode="json"))
        self.eligible = [r for r in self.records if not self.unsupported(r)]
        self.eligible_ids = [i for i, r in zip(self.row_ids, self.records, strict=True)
                             if not self.unsupported(r)]
        n = len(self.eligible)
        self.x = np.array([[r[f] for f in self.numeric] for r in self.eligible], dtype=float).reshape(n, len(self.numeric))
        self.categories = {f: sorted({r[f] for r in self.eligible}) for f in self.categorical}
        self.spans = np.ptp(self.x, axis=0) if n else np.ones(len(self.numeric))
        self.medians = np.median(self.x, axis=0) if n else np.zeros(len(self.numeric))
        iqr = np.subtract(*np.percentile(self.x, [75, 25], axis=0)) if n else np.ones(len(self.numeric))
        self.scales = np.where(iqr > 0, iqr, np.where(self.spans > 0, self.spans, 1.0))
        self.center = np.array([])
        self.precision = np.empty((0, 0))
        self.train_scores = np.array([])
        self.dimension = 0
        if n >= 2:
            z = np.array([self.encode(r) for r in self.eligible])
            self.dimension = z.shape[1]
            if self.dimension:
                self.center = z.mean(axis=0)
                covariance = np.atleast_2d(np.cov(z, rowvar=False, ddof=1))
                shrunk = ((1 - self.config.shrinkage) * covariance
                          + self.config.shrinkage * np.diag(np.diag(covariance))
                          + self.config.ridge * np.eye(self.dimension))
                self.precision = np.linalg.inv(shrunk)
                self.train_scores = np.array([self.global_score(v) for v in z])

    def unsupported(self, payload: dict[str, Any]) -> list[str]:
        return [f["name"] for f in self.fields
                if (not number(payload.get(f["name"])) if f["type"] == "numerical"
                    else not isinstance(payload.get(f["name"]), str))]

    def encode(self, payload: dict[str, Any]) -> np.ndarray:
        numeric = (np.array([payload[f] for f in self.numeric], dtype=float) - self.medians) / self.scales
        categorical = [float(payload[f] == c) for f in self.categorical for c in self.categories[f]]
        return np.concatenate([numeric, categorical])

    def global_score(self, vector: np.ndarray) -> float:
        delta = vector - self.center
        return float(np.sqrt(max(0.0, float(delta @ self.precision @ delta)) / self.dimension))

    def distances(self, payload: dict[str, Any]) -> np.ndarray:
        values = np.array([payload[f] for f in self.numeric], dtype=float)
        difference = np.abs(self.x - values)
        numerical = np.where(self.spans > 0, np.minimum(difference / np.where(self.spans > 0, self.spans, 1), 1), (difference > 0).astype(float))
        categorical = np.array([[float(r[f] != payload[f]) for f in self.categorical]
                                for r in self.eligible]).reshape(len(self.eligible), len(self.categorical))
        return np.concatenate([numerical, categorical], axis=1).mean(axis=1)

    def evidence(self, occurrence: dict[str, Any], family: str, **values: Any) -> M2Evidence:
        return M2Evidence.model_validate_json(__import__("json").dumps({
            "occurrence_id": occurrence["occurrence_id"], "payload_sha256": digest(occurrence["payload"]),
            "dataset_id": self.dataset, "specification_fingerprint": self.specification["fingerprint"],
            "validator_family": family, "reference_fingerprint": self.reference,
            "configuration_fingerprint": self.configuration, **values}))

    def score(self, occurrence: dict[str, Any]) -> list[M2Evidence]:
        if occurrence["dataset_id"] != self.dataset or occurrence["payload_sha256"] != digest(occurrence["payload"]):
            raise ValueError("foreign occurrence or changed payload")
        payload = occurrence["payload"]
        issues, missing = [], []
        fields = [*self.fields, {"name": self.target, "type": "categorical",
                                 "documented_categories": self.spec["target_semantics"]["literal_labels"]}]
        for field in fields:
            name, value = field["name"], payload.get(field["name"])
            if name not in payload:
                issues.append({"field": name, "reason": "ABSENT_DECLARED_FIELD"})
            elif value is None:
                missing.append(name)
            elif field["type"] == "categorical":
                if value not in field["documented_categories"]:
                    issues.append({"field": name, "reason": "UNDECLARED_NOMINAL_VALUE"})
            elif not number(value):
                issues.append({"field": name, "reason": "NONNUMERIC_PRIMITIVE"})
            elif field.get("source_declaration", "").startswith("integer") and value != int(value):
                issues.append({"field": name, "reason": "NONINTEGRAL_DECLARED_INTEGER"})
        issues += [{"field": f, "reason": "UNDECLARED_FIELD"} for f in sorted(set(payload) - {f["name"] for f in fields})]
        authoritative = {r["rule_id"]: r for r in self.spec["rules"] if r["authority"] == "AUTHORITATIVE"}
        structural = self.evidence(occurrence, "authoritative_structure",
            status="PARTIAL" if missing else "AVAILABLE",
            authoritative_validity="INVALID" if issues else "NOT_ESTABLISHED",
            quantities={"violations": issues, "preserved_null_fields": missing},
            reason_codes=["AUTHORITATIVE_SCHEMA_VIOLATION"] if issues else ["NO_ESTABLISHED_VIOLATION_NOT_PROOF_OF_VALIDITY"],
            unsupported_fields=missing, rule_or_model_evidence=authoritative,
            uncertainty="Only source-declared structural evidence. Original target semantics, physical "
            "meaning and cross-field constraints remain unresolved; no affirmative VALID decision.")
        result = [structural]
        unsupported = self.unsupported(payload)
        n = len(self.eligible)
        if unsupported or n < 2 or not self.fields:
            for family in FAMILIES[1:]:
                result.append(self.evidence(occurrence, family, status="UNAVAILABLE",
                    unsupported_fields=unsupported,
                    reason_codes=["MISSING_OR_UNSUPPORTED_FEATURES" if unsupported else "INSUFFICIENT_TRAIN_REFERENCE"],
                    quantities={"eligible_reference_rows": n, "excluded_train_rows": len(self.records) - n},
                    uncertainty="No statistical score is invented; reference or candidate evidence is insufficient."))
            return result
        distances = self.distances(payload)
        order = np.lexsort((np.array(self.eligible_ids), distances))
        neighbors = order[:min(self.config.k, n)]
        label = payload.get(self.target)
        same = [j for j in order if self.eligible[int(j)].get(self.target) == label] if label is not None else []
        reasons = ["STATISTICAL_SUPPORT_NOT_VALIDITY"]
        if label is None:
            reasons.append("DECLARED_CLASS_UNAVAILABLE")
        if label is not None and len(same) < self.config.k:
            reasons.append("SPARSE_OR_ABSENT_DECLARED_CLASS_REFERENCE")
        boundary_ties = int(np.sum(distances == distances[neighbors[-1]]))
        if boundary_ties > 1:
            reasons.append("NEIGHBOR_DISTANCE_TIES")
        result.append(self.evidence(occurrence, "local_support", status="AVAILABLE",
            raw_score=float(distances[neighbors].mean()), reason_codes=reasons,
            quantities={"k_requested": self.config.k, "k_used": len(neighbors),
                "nearest_distance": float(distances[neighbors[0]]),
                "neighbor_train_row_ids": [self.eligible_ids[int(j)] for j in neighbors],
                "feature_duplicate_count": int(np.sum(distances == 0)),
                "same_class_reference_count": len(same),
                "same_class_mean_distance": float(distances[same[:self.config.k]].mean()) if same else None,
                "neighbor_declared_class_fraction": float(np.mean([self.eligible[int(j)].get(self.target) == label for j in neighbors])) if label is not None else None,
                "constant_numeric_fields": [f for f, span in zip(self.numeric, self.spans, strict=True) if span == 0],
                "boundary_tie_count": boundary_ties, "excluded_train_rows": len(self.records) - n},
            rule_or_model_evidence={"model": "TRAIN-range-scaled clipped numeric L1 plus nominal mismatch; unweighted mean over features", "train_rows": n},
            uncertainty="Distances and neighbor fractions are descriptive, not probabilities or invalidity. "
            "Sparse minority support, duplicates, ties and scale sensitivity limit interpretation."))
        unseen = [f for f in self.categorical if payload[f] not in self.categories[f]]
        if unseen or not self.dimension:
            result.append(self.evidence(occurrence, "cross_feature", status="UNAVAILABLE",
                unsupported_fields=unseen, reason_codes=["UNSEEN_TRAIN_CATEGORY" if unseen else "NO_ENCODED_FEATURES"],
                uncertainty="No learned cross-feature relationship is available for this category; novelty is not invalidity."))
        else:
            score = self.global_score(self.encode(payload))
            result.append(self.evidence(occurrence, "cross_feature", status="AVAILABLE", raw_score=score,
                quantities={"dimension": self.dimension, "shrinkage": self.config.shrinkage,
                    "descriptive_train_tail_fraction": float((1 + np.sum(self.train_scores >= score)) / (n + 1)),
                    "excluded_train_rows": len(self.records) - n},
                reason_codes=["STATISTICAL_RELATIONSHIP_NOT_PHYSICAL_LAW", "RESUBSTITUTION_REFERENCE_NOT_CALIBRATED"],
                rule_or_model_evidence={"model": "robust-scaled numerical / TRAIN one-hot shrinkage covariance distance", "train_rows": n},
                uncertainty="Global elliptical approximation can miss nonlinear or multimodal relationships. "
                "TRAIN reference ranks use resubstitution; these are not calibrated p-values or validity judgments."))
        return result
