"""Blinded human-labelling sample of fresh Phase 2 LLM candidates (PLAN Phase 2 task 3).

Writes two kinds of file; the agent fills no human column in either:

``blind/review_blind.csv``  one row per sampled candidate: ``review_id``, ``dataset_id``,
    ``requested_class``, ``record_json`` (the record exactly as the model returned it) and
    the five empty human columns of ``docs/human-review.md``. No generator name, no gate,
    repair, admission or copying result, so labels are not influenced by automated
    decisions.
``blind/schema_<dataset>.json``  the declared field types, integer declarations and
    documented categories (from the dataset specification, not from TRAIN values), so
    reviewers can judge schema/domain conformance.
``key/review_key.csv``  for joining after labelling only: review_id -> model, dataset,
    split seed, fold, batch, item, payload SHA-256. Automated diagnostics are joined at
    analysis time, never shown to reviewers.

Sampling: per dataset, all returned records of the given models are ordered by SHA-256 of
their identity and the first ``per_dataset`` taken, alternating models round-robin so each
model is represented. Deterministic; no record is edited.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from rcqasyn.phase2.specifications import dataset_specification

from .devroot import DEV, DEVROOT

HUMAN_COLUMNS = ("human_valid", "human_failure_type", "human_severity",
                 "human_affected_fields", "human_notes")


def _candidates(pools: Path, model: str, dataset: str) -> list[dict[str, Any]]:
    out = []
    for unit in sorted((pools / model.replace(":", "_")).glob(f"{dataset}__s*__f*")):
        path = unit / "candidates.jsonl"
        if not path.exists():
            continue
        _, seed, fold = unit.name.split("__")
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            record = json.loads(line)
            identity = {"model": model, "dataset_id": dataset, "split_seed": int(seed[1:]),
                        "fold": int(fold[1:]), "requested_class": record["requested_class"],
                        "batch_index": record["batch_index"],
                        "item_index": record["item_index"]}
            payload = json.dumps(record["data"], sort_keys=True)
            key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
            out.append({**identity, "record_json": payload, "order": key,
                        "payload_sha256": hashlib.sha256(payload.encode()).hexdigest()})
    return sorted(out, key=lambda r: r["order"])


def sample(pools: Path, models: list[str], datasets: list[str], per_dataset: int
           ) -> list[dict[str, Any]]:
    chosen = []
    for dataset in datasets:
        queues = [_candidates(pools, m, dataset) for m in models]
        picked: list[dict[str, Any]] = []
        while len(picked) < per_dataset and any(queues):
            for queue in queues:
                if queue and len(picked) < per_dataset:
                    picked.append(queue.pop(0))
        chosen.extend(picked)
    for row in chosen:
        row["review_id"] = "v3r-" + row["order"][:16]
    return sorted(chosen, key=lambda r: r["review_id"])


def export(pools: Path, models: list[str], datasets: list[str], per_dataset: int,
           out: Path) -> dict[str, Any]:
    rows = sample(pools, models, datasets, per_dataset)
    blind, key = out / "blind", out / "key"
    blind.mkdir(parents=True, exist_ok=True)
    key.mkdir(parents=True, exist_ok=True)
    with (blind / "review_blind.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["review_id", "dataset_id", "requested_class", "record_json",
                         *HUMAN_COLUMNS])
        for r in rows:
            writer.writerow([r["review_id"], r["dataset_id"], r["requested_class"],
                             r["record_json"], *([""] * len(HUMAN_COLUMNS))])
    with (key / "review_key.csv").open("w", newline="", encoding="utf-8") as handle:
        columns = ["review_id", "model", "dataset_id", "split_seed", "fold",
                   "requested_class", "batch_index", "item_index", "payload_sha256"]
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    for dataset in sorted({r["dataset_id"] for r in rows}):
        spec = dataset_specification(DEVROOT, dataset)["specification"]
        schema = {"dataset_id": dataset,
                  "target": spec["target_semantics"],
                  "fields": [{k: f.get(k) for k in ("name", "type", "source_declaration",
                                                     "documented_categories")}
                             for f in spec["features"]]}
        (blind / f"schema_{dataset}.json").write_text(json.dumps(schema, indent=1),
                                                       encoding="utf-8")
    counts: dict[str, dict[str, int]] = {}
    for r in rows:
        counts.setdefault(r["dataset_id"], {}).setdefault(r["model"], 0)
        counts[r["dataset_id"]][r["model"]] += 1
    summary = {"rows": len(rows), "per_dataset_and_model": counts, "models": models,
               "human_columns_filled_by_agent": 0}
    (out / "export_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pools", type=Path, required=True)
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--datasets", nargs="+", default=list(DEV))
    parser.add_argument("--per-dataset", type=int, default=15)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(export(args.pools, args.models, args.datasets, args.per_dataset,
                            args.out), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
