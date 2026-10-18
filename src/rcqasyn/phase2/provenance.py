from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from rcqasyn.datasets.registry import DatasetRegistry
from rcqasyn.experiments.diagnostics import _canonical
from rcqasyn.experiments.readers import validate_source
from rcqasyn.generation.parser import _decode_json
from rcqasyn.storage.artifacts import read_json
from rcqasyn.storage.ownership import file_hash
from rcqasyn.utils.hashing import sha256_text

from .common import digest, envelope, jsonl, snapshot, source_path, verify_envelope, verify_sources
from .contracts import CROSSWALK, Locator, Occurrence


def locator(root: Path, path: Path, line: int) -> dict[str, Any]:
    return Locator(artifact=path.relative_to(root).as_posix(), sha256=file_hash(path),
                   line=line).model_dump(mode="json")


def extract_crosswalk(root: Path, run_path: Path) -> dict[str, Any]:
    """Recover occurrences without consulting a corrected review CSV or any provider."""
    root, run = root.resolve(), run_path.resolve()
    if not run.is_relative_to(root):
        raise ValueError("run must belong to the source root")
    manifest = validate_source(run)
    if manifest.get("schema_version") != "m1-run-v1":
        raise ValueError("extractor supports completed legacy m1-run-v1 only")
    spec = DatasetRegistry(project_root=root).get(manifest["dataset_id"])
    sources = snapshot(root, [p for p in run.rglob("*") if p.is_file()]
                       + list((root / "configs/datasets").glob("*.yaml")))
    def locate(path: Path, line: int) -> dict[str, Any]:
        relative = path.relative_to(root).as_posix()
        return Locator(artifact=relative, sha256=sources[relative], line=line).model_dump(mode="json")

    raw_path = run / "candidates_raw.jsonl"
    raw = jsonl(raw_path)
    traces = [(i + 1, t) for i, t in enumerate(jsonl(run / "provider_calls.jsonl"))
              if t["role"] == "generation"]
    copying = read_json(run / "copying_diagnostics.json")["records"]
    support = jsonl(run / "support_diagnostics.jsonl")
    decisions = {b: jsonl(run / f"baselines/{b}/decisions.jsonl") for b in ("b1", "b2", "b3")}
    results = jsonl(run / "baselines/b3/judge_results.jsonl")
    judges = jsonl(run / "baselines/b3/provider_calls.jsonl")
    evidence = jsonl(run / "baselines/b2/evidence.jsonl")
    if not raw or any(len(v) != len(raw) for v in
                      [copying, support, results, judges, *decisions.values()]):
        raise ValueError("incomplete occurrence/control streams")
    for baseline, stream in decisions.items():
        if [d["candidate_id"] for d in stream] != [c["record_id"] for c in raw]:
            raise ValueError("control occurrence order mismatch")
        if jsonl(run / f"baselines/{baseline}/candidates.jsonl") != [
                c for c, d in zip(raw, stream, strict=True) if d["accepted"]]:
            raise ValueError("accepted candidate occurrence sequence mismatch")
    records = []
    cursor = 0
    for index, candidate in enumerate(raw):
        legacy_id, payload = candidate["record_id"], candidate["data"]
        legacy_hash = _canonical(payload, [*spec.feature_columns, spec.target_column])
        cp, sup = copying[index], support[index]
        if cp["record_id"] != legacy_id or cp["canonical_hash"] != legacy_hash:
            raise ValueError("recorded payload hash mismatch")
        if sup["record_id"] != legacy_id:
            raise ValueError("support occurrence order mismatch")
        matches = []
        for ordinal, (line, trace) in enumerate(traces, 1):
            meta = candidate["metadata"]
            if (trace["call_id"] != meta["provider_call_id"]
                    or trace["raw_response"] != candidate["raw_output"]
                    or trace.get("seed") != candidate.get("seed")
                    or trace.get("requested_class") != meta.get("requested_class")):
                continue
            response = _decode_json(trace["raw_response"])
            items = response.get("records") if isinstance(response, dict) else response
            item = meta["item_index"]
            if isinstance(items, list) and 0 <= item < len(items) and items[item] == payload:
                matches.append((ordinal, line, trace))
        if len(matches) != 1:
            raise ValueError(f"ambiguous or missing generation occurrence: {legacy_id}")
        ordinal, line, trace = matches[0]
        result, judge = results[index], judges[index]
        try:
            judged_payload = _decode_json(judge["prompt"].split("CANDIDATE:\n", 1)[1].strip())
            response = _decode_json(judge["raw_response"])
        except (ValueError, IndexError) as error:
            raise ValueError("missing judge payload witness") from error
        if (judged_payload != payload or result["candidate_id"] != legacy_id
                or result["judge_call_id"] != judge["call_id"]
                or any(result.get(k) != response.get(k) for k in
                       ("score", "verdict", "reasons", "affected_fields", "self_confidence"))):
            raise ValueError("judge occurrence witness mismatch")
        ids = decisions["b2"][index]["evidence_ids"]
        block = evidence[cursor:cursor + len(ids)]
        if ([e["evidence_id"] for e in block] != ids
                or any(e["candidate_id"] != legacy_id for e in block)):
            raise ValueError("B2 evidence occurrence block mismatch")
        controls: dict[str, dict[str, Any]] = {
            b: {"decision": stream[index],
                "locator": locate(run / f"baselines/{b}/decisions.jsonl", index + 1)}
            for b, stream in decisions.items()
        }
        controls["b2"]["evidence"] = block
        controls["b2"]["evidence_locators"] = [
            locator(root, run / "baselines/b2/evidence.jsonl", i + 1)
            for i in range(cursor, cursor + len(ids))]
        cursor += len(ids)
        controls["b3"].update(
            result=result, judge_trace=locator(root, run / "baselines/b3/provider_calls.jsonl",
                                             index + 1),
            result_locator=locator(root, run / "baselines/b3/judge_results.jsonl", index + 1),
        )
        relative = raw_path.relative_to(root).as_posix()
        descriptor = {"identity_version": "legacy-occurrence-id-v1",
                      "source_execution_id": manifest["run_id"],
                      "source_manifest_sha256": file_hash(run / "manifest.json"),
                      "source_artifact": relative,
                      "source_artifact_sha256": sources[relative],
                      "source_occurrence_ordinal": index + 1}
        record = Occurrence(
            occurrence_id="occ-" + digest(descriptor),
            legacy_candidate_id=legacy_id, dataset_id=spec.dataset_id,
            source_execution_id=manifest["run_id"], source_artifact=relative,
            source_artifact_sha256=sources[relative],
            source_manifest_sha256=descriptor["source_manifest_sha256"],
            source_attempt_id_or_evidenced_locator=Locator.model_validate_json(
                json.dumps(locator(root, run / "provider_calls.jsonl", line))),
            source_occurrence_ordinal=index + 1, response_ordinal=ordinal,
            item_index=candidate["metadata"]["item_index"], payload=payload,
            payload_sha256=digest(payload), recorded_payload_sha256=legacy_hash,
            raw_response_sha256=sha256_text(candidate["raw_output"]),
            generation_metadata={"provider_call_id": trace["call_id"],
                                 "provider_seed": trace.get("seed"),
                                 "batch_index": trace.get("metadata", {}).get("batch_index"),
                                 "requested_class": trace.get("requested_class")},
            controls=controls, diagnostics={**cp, **sup},
        )
        records.append(record.model_dump(mode="json"))
    if cursor != len(evidence) or len({r["occurrence_id"] for r in records}) != len(raw):
        raise ValueError("unconsumed evidence or duplicate occurrence identity")
    groups: dict[str, list[str]] = defaultdict(list)
    for row in records:
        groups[row["legacy_candidate_id"]].append(row["payload_sha256"])
    collisions = {k: v for k, v in groups.items() if len(v) > 1}
    verify_sources(root, sources)
    return envelope(CROSSWALK, {
        "crosswalk_version": CROSSWALK, "validation_status": "SOURCE_VALIDATED",
        "source_execution_id": manifest["run_id"], "source_files": sources,
        "records": records, "collisions": collisions,
        "summary": {"occurrences": len(records), "unique_occurrence_ids": len(records),
                    "unique_legacy_ids": len(groups),
                    "unique_payloads": len({r["payload_sha256"] for r in records}),
                    "collision_groups": len(collisions),
                    "different_content_collision_groups": sum(len(set(v)) > 1
                                                              for v in collisions.values()),
                    "unresolved_occurrences": 0},
        "legacy_limitations": "Unsealed legacy bytes; trace locator is not a durable attempt ID.",
    })


def validate_crosswalk(root: Path, value: dict[str, Any]) -> None:
    verify_envelope(value, CROSSWALK)
    verify_sources(root, value["source_files"])
    first = Occurrence.model_validate_json(json.dumps(value["records"][0]))
    if extract_crosswalk(root, source_path(root, first.source_artifact).parent) != value:
        raise ValueError("crosswalk differs from authoritative occurrence reconstruction")


def resolve_occurrence(value: dict[str, Any], occurrence_id: str) -> dict[str, Any]:
    matches = [r for r in value["records"] if r["occurrence_id"] == occurrence_id]
    if len(matches) != 1:
        raise ValueError("occurrence lookup is missing or ambiguous")
    return matches[0]
