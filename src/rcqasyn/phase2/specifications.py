from __future__ import annotations

from pathlib import Path
from typing import Any

from rcqasyn.datasets.loader import inspect_keel, load_dataset
from rcqasyn.datasets.profile import build_profile
from rcqasyn.datasets.registry import DatasetRegistry
from rcqasyn.datasets.split import make_split
from rcqasyn.storage.artifacts import read_json
from rcqasyn.storage.ownership import file_hash

from .common import envelope, snapshot, verify_envelope, verify_sources
from .contracts import DatasetSpecification, Rule


def dataset_specification(root: Path, dataset_id: str) -> dict[str, Any]:
    registry = DatasetRegistry(project_root=root)
    definition = registry.get(dataset_id)
    data = load_dataset(definition, registry)
    split = make_split(data, 42)
    recorded = read_json(root / f"data/manifests/{dataset_id}/split_manifest.json")
    if split.to_dict() != recorded:
        raise ValueError("dataset/split differs from frozen recorded source")
    acquisition = read_json(root / f"data/manifests/{dataset_id}/source.json")
    if file_hash(data.path) != acquisition["extracted_sha256"]:
        raise ValueError("dataset source checksum mismatch")
    schema = inspect_keel(data.path)
    profile = build_profile(data, split, reference_example_count=0, enabled=False)
    # This bounded projection deliberately excludes TEST/full-population lineage.
    train = profile.to_generation_context()
    declaration_ref = f"data/manifests/{dataset_id}/raw_schema.json"
    recorded_schema = read_json(root / declaration_ref)
    if (recorded_schema["attributes"] != [a.to_dict() for a in schema.attributes]
            or recorded_schema["inputs"] != list(schema.inputs)
            or recorded_schema["outputs"] != list(schema.outputs)):
        raise ValueError("archived raw schema differs from source declarations")
    sources = snapshot(root, [data.path, root / declaration_ref,
                       *list((root / f"data/manifests/{dataset_id}").glob("*.json")),
                       root / f"configs/datasets/{dataset_id.lower()}.yaml", root / "docs/datasets.md"])
    rules = [
        Rule(rule_id=f"{dataset_id}:schema", authority="AUTHORITATIVE",
             statement="Use the declared feature/target fields and primitive numerical/nominal types.",
             evidence=(declaration_ref,), hard_rejection_allowed=True),
        Rule(rule_id=f"{dataset_id}:target-tokens", authority="AUTHORITATIVE",
             statement="The source target declaration permits positive and negative.",
             evidence=(declaration_ref,), hard_rejection_allowed=True),
        Rule(rule_id=f"{dataset_id}:train-support", authority="INFERRED",
             statement="TRAIN ranges, frequencies and domains describe observed support only.",
             evidence=(f"data/manifests/{dataset_id}/profile.json",)),
        Rule(rule_id=f"{dataset_id}:original-target-mapping", authority="UNVERIFIED",
             statement="Original multiclass-to-binary mapping is not independently established "
             "by the locally archived documentation."),
    ]
    if definition.categorical_columns:
        rules.append(Rule(rule_id=f"{dataset_id}:declared-categories",
                          authority="AUTHORITATIVE",
                          statement="Nominal category declarations apply to this source version.",
                          evidence=(declaration_ref,), hard_rejection_allowed=True))
    attributes = {a.name.lower(): a for a in schema.attributes}
    features = tuple({
        "name": name, "type": "categorical" if name in definition.categorical_columns
        else "numerical", "source_declaration": attributes[name.lower()].declaration,
        "documented_categories": list(attributes[name.lower()].categories),
        "physical_definition": "UNVERIFIED; preserve the source field name",
        "numeric_bounds_semantics": "Declared source support, not an independently verified "
        "universal validity bound",
    } for name in definition.feature_columns)
    spec = DatasetSpecification(
        dataset_id=dataset_id,
        source_identity={"version": "KEEL unpartitioned archive; content identified",
                         "source_url": definition.source_url,
                         "source_page": definition.source_page,
                         "raw_sha256": file_hash(data.path), "acquisition": acquisition,
                         "normalized_dataset_fingerprint": data.fingerprint},
        original_task={"definition": "Binary classification of source class tokens",
                       "original_prebinary_mapping": "UNVERIFIED",
                       "decision_status": "RESEARCH_DECISION_REQUIRED"},
        target_semantics={"target_column": definition.target_column,
                          "minority_label": definition.minority_label,
                          "literal_labels": ["negative", "positive"],
                          "semantic_class_membership": "UNVERIFIED"},
        features=features, missing_policy=definition.missing_policy, rules=tuple(rules),
        train_profile=train,
        split_provenance={"root_seed": 42, "split_policy": definition.split.model_dump(),
                          **{k: v for k, v in recorded.items()
                             if k not in ("train_indices", "test_indices")}},
        ambiguity=("Rare/unseen/outlier/duplicate/low-probability is not automatically invalid.",
                   "Cross-field physical constraints and original target mapping need evidence.",
                   "Missing token '?' is preserved as null; no new imputation is introduced.",
                   "page-blocks0 exact-value TRAIN/TEST overlap is a historical limitation."
                   if dataset_id == "page-blocks0" else "No exact-value overlap found in audit."),
        evaluation_applicability="Exploratory audit of the retained selected cohort; no calibrated "
        "or population-wide correctness claim.",
        documentation_references=(declaration_ref, f"data/manifests/{dataset_id}/source.json",
                                  "docs/datasets.md", str(definition.source_page)),
    )
    return envelope("dataset-specification-v1", {"specification": spec.model_dump(mode="json"),
                     "validation_status": spec.status, "source_files": sources})


def specifications(root: Path) -> dict[str, Any]:
    ids = ("page-blocks0", "Ecoli4", "Abalone19")
    specs = [dataset_specification(root, name) for name in ids]
    return envelope("dataset-specifications-v1", {
        "specifications": specs, "validation_status": "DRAFT_REQUIRES_SUPERVISOR_APPROVAL",
        "semantics_gaps": [{"dataset_id": name, "status": "RESEARCH_DECISION_REQUIRED",
                           "gaps": ["original binary mapping", "physical field meanings/units",
                                    "cross-field hard constraints"]}
                          for name in ids],
        "public_documentation_attempt": "Official KEEL pages could not be retrieved on "
        "2026-10-18; no unverified mapping was promoted to authoritative.",
        "extensions": [{"dataset": name, "availability": "MISSING", "activated": False,
                        "approval_required": True,
                        "source": "https://archive.ics.uci.edu/dataset/222/bank+marketing"
                        if name == "bank-additional-full" else None,
                        "version_status": "UNVERIFIED",
                        "requirements": ["exact version", "source/license", "schema", "target"]}
                       for name in ("bank-additional-full", "DataCo Smart Supply Chain v5",
                                    "Steel Plates Faults", "Adult")],
    })


def validate_specifications(root: Path, value: dict[str, Any]) -> None:
    verify_envelope(value, "dataset-specifications-v1")
    for artifact in value["specifications"]:
        verify_envelope(artifact, "dataset-specification-v1")
        verify_sources(root, artifact["source_files"])
    if specifications(root) != value:
        raise ValueError("dataset specification differs from source/TRAIN reconstruction")
