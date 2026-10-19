from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, cast

import numpy as np
import pandas as pd

from rcqasyn.datasets.split import _subset_fingerprint
from rcqasyn.phase2.common import digest, envelope, verify_envelope
from rcqasyn.phase3.validators import TrainEvidenceModel, number


def feature_supported(payload: dict[str, Any], fields: list[dict[str, Any]]) -> bool:
    return all(number(payload.get(f["name"])) if f["type"] == "numerical"
               else isinstance(payload.get(f["name"]), str) for f in fields)


def complete_record(payload: dict[str, Any], specification: dict[str, Any]) -> bool:
    fields = specification["features"]; target = specification["target_semantics"]
    if (set(payload) != {f["name"] for f in fields} | {target["target_column"]}
            or payload.get(target["target_column"]) not in target["literal_labels"]
            or not feature_supported(payload, fields)):
        return False
    return all((not f.get("source_declaration", "").startswith("integer") or
                payload[f["name"]] == int(payload[f["name"]])) if f["type"] == "numerical"
               else payload[f["name"]] in f["documented_categories"] for f in fields)


@dataclass
class FrozenDistance:
    numeric: list[str]
    categorical: list[str]
    spans: np.ndarray
    eligible: list[dict[str, Any]]

    @property
    def x(self) -> np.ndarray:
        return np.array([[r[f] for f in self.numeric] for r in self.eligible], dtype=float).reshape(len(self.eligible), len(self.numeric))

    def matrix(self, queries: list[dict[str, Any]]) -> np.ndarray:
        # Reuse the exact frozen M2 mixed-type distance implementation, without fitting a model.
        return np.array([TrainEvidenceModel.distances(cast(TrainEvidenceModel, self), r) for r in queries]).reshape(len(queries), len(self.eligible))


def reference_from_frame(spec: dict[str, Any], frame: pd.DataFrame, split: dict[str, Any],
                         parameters: dict[str, Any]) -> dict[str, Any]:
    verify_envelope(spec, "dataset-specification-v1")
    train, test = split["train_indices"], split["test_indices"]
    d = spec["specification"]["dataset_id"]
    if (split["dataset_id"] != d or not train or len(set(train)) != len(train)
            or len(set(test)) != len(test) or set(train) & set(test)
            or set(train) | set(test) != set(frame.index)
            or _subset_fingerprint(frame, train) != split["train_fingerprint"]):
        raise ValueError("foreign TRAIN, changed values or REAL TEST membership contamination")
    selected = frame.loc[train].astype(object)
    records = selected.where(pd.notna(selected), None).to_dict(orient="records")
    fields = spec["specification"]["features"]
    supported = [(i, r) for i, r in zip(train, records, strict=True) if feature_supported(r, fields)]
    numeric = [f["name"] for f in fields if f["type"] == "numerical"]
    categorical = [f["name"] for f in fields if f["type"] == "categorical"]
    if parameters["numeric_fields"] != numeric or parameters["categorical_fields"] != categorical:
        raise ValueError("frozen distance fields differ from specification")
    actual = np.ptp([[r[f] for f in numeric] for _, r in supported], axis=0) if supported else np.ones(len(numeric))
    if not np.array_equal(actual, parameters["gower_spans"]):
        raise ValueError("frozen numerical spans differ from TRAIN")
    return envelope("m7-train-reference-v1", {"dataset_id": d,
        "specification_fingerprint": spec["fingerprint"], "train_indices": train,
        "recorded_train_fingerprint": split["train_fingerprint"],
        "m2_train_reference_fingerprint": digest({"dataset_id": d, "train_row_ids": train, "train_records": records}),
        "records": records, "supported_indices": [i for i, _ in supported],
        "excluded_indices": [i for i in train if i not in {j for j, _ in supported}],
        "numeric_fields": numeric, "categorical_fields": categorical,
        "gower_spans": list(parameters["gower_spans"]), "metric_version": "phase3-mixed-distance-v1",
        "real_test_values_used": False, "no_refit": True})


@dataclass
class Geometry:
    reference: dict[str, Any]
    occurrences: list[dict[str, Any]]
    fields: list[dict[str, Any]]
    target: str

    def __post_init__(self) -> None:
        verify_envelope(self.reference, "m7-train-reference-v1")
        r = self.reference
        records = dict(zip(r["train_indices"], r["records"], strict=True))
        self.train = [records[i] for i in r["supported_indices"]]
        if not self.train or not self.fields:
            raise ValueError("no supported TRAIN feature reference")
        self.feature_hash = lambda payload: digest({f["name"]: payload[f["name"]] for f in self.fields})
        self.feature_ids = [self.feature_hash(row) if feature_supported(row, self.fields) else None for row in (o["payload"] for o in self.occurrences)]
        metric = FrozenDistance(r["numeric_fields"], r["categorical_fields"], np.array(r["gower_spans"]), self.train)
        supported = [i for i, o in enumerate(self.occurrences) if feature_supported(o["payload"], self.fields)]
        queries = [self.occurrences[i]["payload"] for i in supported]
        self.to_train = np.full((len(self.occurrences), len(self.train)), np.nan)
        self.to_train[supported] = metric.matrix(queries)
        self.pairwise = np.full((len(self.occurrences), len(self.occurrences)), np.nan)
        other = FrozenDistance(metric.numeric, metric.categorical, metric.spans, queries)
        self.pairwise[np.ix_(supported, supported)] = other.matrix(queries)
        region_keys = [digest({"features": self.feature_hash(row), "label": row.get(self.target)}) for row in self.train]
        feature_keys = [self.feature_hash(row) for row in self.train]
        self.regions = list(dict.fromkeys(region_keys))
        self.region_indices = [region_keys.index(k) for k in self.regions]
        self.feature_indices = [feature_keys.index(k) for k in dict.fromkeys(feature_keys)]
        self.region_labels = [self.train[i].get(self.target) for i in self.region_indices]
        counts = Counter(row.get(self.target) for row in self.train if row.get(self.target) is not None)
        self.minority = min(counts, key=lambda label: (counts[label], str(label))) if counts else None
        self.class_counts = dict(counts)
        region_counts = Counter(self.region_labels)
        self.uniform_weights = np.full(len(self.regions), 1/len(self.regions))
        self.balanced_weights = np.array([1/(len(region_counts)*region_counts[label]) for label in self.region_labels])

    def cover(self, radius: float) -> np.ndarray:
        return self.to_train[:, self.region_indices] <= radius


def describe(values: np.ndarray) -> dict[str, Any]:
    finite = values[np.isfinite(values)]
    return {"n": len(finite), "mean": float(np.mean(finite)) if len(finite) else None,
            "quantiles": dict(zip(("min", "q25", "median", "q75", "max"),
                [float(v) for v in np.percentile(finite, [0, 25, 50, 75, 100])], strict=True)) if len(finite) else {}}


def metrics(g: Geometry, selected: list[int], eligible: list[int], radius: float, tolerance: float) -> dict[str, Any]:
    n = len(selected); rows = [g.occurrences[i] for i in selected]
    near_train = np.min(g.to_train[selected], axis=1) if n else np.array([])
    distances = g.pairwise[np.ix_(selected, selected)].copy()
    pairs = distances[np.triu_indices(n, 1)]
    if n:
        np.fill_diagonal(distances, np.inf)
    nearest = distances.min(axis=1) if n else np.array([])
    min_to_selected = np.min(g.to_train[selected], axis=0) if n else np.full(len(g.train), np.inf)
    covered = min_to_selected <= radius
    class_coverage = {}
    for label in sorted(g.class_counts):
        mask = np.array([r.get(g.target) == label for r in g.train])
        chosen = [i for i in selected if g.occurrences[i]["payload"][g.target] == label]
        own = np.min(g.to_train[chosen], axis=0) <= radius if chosen else np.zeros(len(g.train), dtype=bool)
        class_coverage[label] = {"train_n": int(mask.sum()), "selected_declared_class_n": len(chosen),
            "coverage_by_any_selected": float(covered[mask].mean()),
            "coverage_by_same_declared_class": float(own[mask].mean())}
    density = (g.to_train <= radius).mean(axis=1)
    density_cutoff = float(np.quantile(density[eligible], .75)) if eligible else None
    assignments = Counter(np.argmin(g.to_train[selected][:, g.feature_indices], axis=1)) if n else Counter()
    exact = len({digest(r["payload"]) for r in rows})
    return {"selected_n": n, "unique_occurrences": len({r["occurrence_id"] for r in rows}),
        "unique_payloads": exact, "exact_duplicate_rate": 1-exact/n if n else 0.,
        "unique_feature_payloads": len({g.feature_ids[i] for i in selected}),
        "near_duplicate_rate": float(np.mean(nearest <= tolerance)) if n >= 2 else None,
        "near_duplicate_denominator": n if n >= 2 else 0,
        "nearest_train_distance": describe(near_train), "nearest_selected_distance": describe(nearest),
        "pairwise_separation": describe(pairs),
        "train_row_coverage": float(covered.mean()),
        "unique_train_feature_coverage": float(covered[g.feature_indices].mean()),
        "train_region_coverage": float(covered[g.region_indices].mean()),
        "class_balanced_region_coverage": float(np.sum(g.balanced_weights*covered[g.region_indices])),
        "class_coverage": class_coverage, "minority_literal_label": g.minority,
        "train_n": len(g.train), "train_unique_features": len(g.feature_indices),
        "train_unique_feature_label_regions": len(g.regions),
        "train_excluded_unsupported": len(g.reference["excluded_indices"]),
        "coverage_radius": radius, "near_duplicate_tolerance": tolerance,
        "mean_train_neighbor_fraction": float(density[selected].mean()) if n else None,
        "dense_region_reference_q75": density_cutoff,
        "dense_region_selection_fraction": float(np.mean(density[selected] >= density_cutoff)) if n and density_cutoff is not None else None,
        "nearest_train_region_hhi": sum((count/n)**2 for count in assignments.values()) if n else None,
        "label_counts": dict(Counter(r["payload"][g.target] for r in rows))}
