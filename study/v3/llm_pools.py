"""Fresh LLM candidate pools for Phase 2 dev folds (Gate 1 decision 3: local Ollama only).

For one (model, dev dataset, outer split seed, fold) this builds a generation context from
the fold's inner TRAIN rows only (outer TRAIN minus the held-out fold; outer TEST is dropped
before anything is read), renders the v3 prompt (``prompt_templates/generation_v3.txt``,
SHA-256 recorded) and requests ``pool_factor x budget`` records in batches of
``BATCH_SIZE``, split between the classes by ``minority_share``.

Invariants carried over from the M1 harness:

* every batch gets its own provider seed from ``generation_provider_seed`` (root = split
  seed, base = fold), never one reused seed;
* the raw provider body is appended to ``raw.jsonl`` before parsing;
* parsed records are stored exactly as returned (``candidates.jsonl``): nothing is clipped,
  coerced, imputed or regenerated here;
* every call goes through ``providers.call``, which budget-checks it and appends it to
  ``budget.jsonl`` (local calls cost 0 but are logged).

Resumable: a batch whose raw body is already in ``raw.jsonl`` is skipped. A failed call is
recorded in ``calls.jsonl``; a later invocation retries it once (``MAX_ATTEMPTS``), then the
batch stays failed and is reported, never silently refilled.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from rcqasyn.empirical.addendum import budget_rule
from rcqasyn.generation.parser import parse_generation_response
from rcqasyn.phase2.specifications import dataset_specification
from rcqasyn.utils.seeds import derive_seed, generation_provider_seed
from study.v3 import providers

from .crossfit import K_FOLDS
from .devroot import DEV, DEVROOT
from .phase1 import SPLIT_SEEDS
from .phase2 import fold_frames

HERE = Path(__file__).resolve().parent
PROMPT_PATH = HERE / "prompt_templates" / "generation_v3.txt"
PROMPT_VERSION = "study-v3-generation-v3"
BATCH_SIZE = 10
REFERENCES_PER_CLASS = 3
MAX_TOKENS = 4096
MAX_ATTEMPTS = 2  # the first call plus the one allowed retry


def prompt_template() -> tuple[str, str]:
    """Template text and SHA-256, with line endings normalised to LF.

    A Windows checkout with core.autocrlf may hold the file with CRLF; normalising keeps the
    rendered prompt and its recorded hash identical on every machine.
    """
    text = PROMPT_PATH.read_bytes().decode("utf-8").replace("\r\n", "\n")
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def _json_value(value: Any) -> Any:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, np.generic):
        return _json_value(value.item())
    return value


def generation_context(inner: pd.DataFrame, spec: Any, spec_dict: dict[str, Any],
                       dataset: str, split_seed: int, fold: int
                       ) -> tuple[dict[str, Any], list[int]]:
    """TRAIN-only context from the fold's inner rows; returns (context, reference row ids)."""
    target = spec.target_column
    fields = {f["name"]: {"type": f["type"], "declaration": f.get("source_declaration"),
                          "missing_rate": float(inner[f["name"]].isna().mean())}
              for f in spec_dict["features"]}
    numeric_summary = {}
    for column in spec.numerical_columns:
        values = pd.Series(pd.to_numeric(inner[column], errors="coerce"),
                           dtype=float).dropna().to_numpy(dtype=float)
        if len(values):
            q = np.quantile(values, [0.0, 0.25, 0.5, 0.75, 1.0])
            numeric_summary[column] = dict(zip(("min", "q25", "median", "q75", "max"),
                                               map(float, q), strict=True))
    labels = inner[target].astype(str)
    domains = {c: sorted(str(v) for v in inner[c].dropna().unique())
               for c in spec.categorical_columns}
    domains[target] = sorted(labels.unique().tolist())
    seed = derive_seed(split_seed, f"study-v3-llm-reference:{dataset}", fold)
    reference_ids: list[int] = []
    for label in sorted(labels.unique().tolist()):
        ids = sorted((int(i) for i, v in zip(inner.index, labels, strict=True) if v == label),
                     key=lambda i: hashlib.sha256(f"{seed}:{label}:{i}".encode()).hexdigest())
        reference_ids.extend(ids[:REFERENCES_PER_CLASS])
    references = [{k: _json_value(v) for k, v in inner.loc[i].to_dict().items()}
                  for i in reference_ids]
    counts = {str(k): int(v) for k, v in labels.value_counts().sort_index().items()}
    return {"dataset_id": dataset, "fields": fields, "target_column": target,
            "categorical_domains": domains, "numeric_summary": numeric_summary,
            "class_counts": counts,
            "class_proportions": {k: v / len(labels) for k, v in counts.items()},
            "reference_examples": references}, reference_ids


def batch_plan(budget: int, pool_factor: int, minority_share: float, positive: str,
               negative: str, batch_size: int = BATCH_SIZE) -> list[tuple[str, int, int]]:
    """(requested class, count, per-class batch index) for a pool of pool_factor x budget."""
    total = pool_factor * budget
    n_min = round(total * minority_share)
    plan = []
    for label, n in ((positive, n_min), (negative, total - n_min)):
        for index in range(math.ceil(n / batch_size)):
            plan.append((label, min(batch_size, n - index * batch_size), index))
    return plan


def _lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _append(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")


def unit_dir(out: Path, model: str, dataset: str, split_seed: int, fold: int) -> Path:
    return out / model.replace(":", "_") / f"{dataset}__s{split_seed}__f{fold}"


def generate_fold(model: str, dataset: str, split_seed: int, fold: int, out: Path, *,
                  pool_factor: int = 4, minority_share: float = 0.5) -> dict[str, Any]:
    spec_model = providers.MODELS[model]
    if spec_model.provider != "ollama":
        raise ValueError("Phase 2 LLM pools are local Ollama only (Gate 1 decision 3)")
    providers.require_ready(spec_model)
    spec, _loaded, inner, held, split = fold_frames(dataset, split_seed, fold)
    spec_dict = dataset_specification(DEVROOT, dataset)["specification"]
    positive = str(spec.minority_label)
    labels = sorted(set(inner[spec.target_column].astype(str)))
    negative = next(label for label in labels if label != positive)
    budget = budget_rule(int((inner[spec.target_column].astype(str) == positive).sum()))
    context, reference_ids = generation_context(inner, spec, spec_dict, dataset, split_seed, fold)
    if set(reference_ids) & {int(i) for i in held.index}:
        raise ValueError("a reference example comes from the held-out fold")
    template, template_sha = prompt_template()
    context_json = json.dumps(context, sort_keys=True)
    directory = unit_dir(out, model, dataset, split_seed, fold)
    directory.mkdir(parents=True, exist_ok=True)
    plan = batch_plan(budget, pool_factor, minority_share, positive, negative)
    manifest = {"model": model, "model_id": spec_model.model_id, "dataset_id": dataset,
                "split_seed": split_seed, "fold": fold, "budget": budget,
                "pool_factor": pool_factor, "minority_share": minority_share,
                "batch_size": BATCH_SIZE, "max_tokens": MAX_TOKENS,
                "prompt_version": PROMPT_VERSION, "prompt_sha256": template_sha,
                "context_sha256": hashlib.sha256(context_json.encode()).hexdigest(),
                "reference_row_ids": reference_ids,
                "outer_split_fingerprint": split["split_fingerprint"],
                "heldout_ids_sha256": hashlib.sha256(
                    json.dumps(sorted(int(i) for i in held.index)).encode()).hexdigest(),
                "planned_batches": len(plan), "test_used": False}
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True),
                                             encoding="utf-8")
    done = {(r["requested_class"], r["batch_index"]) for r in _lines(directory / "raw.jsonl")}
    attempts: dict[tuple[str, int], int] = {}
    for record in _lines(directory / "calls.jsonl"):
        key = (record["requested_class"], record["batch_index"])
        attempts[key] = attempts.get(key, 0) + 1
    for label, count, index in plan:
        key = (label, index)
        if key in done or attempts.get(key, 0) >= MAX_ATTEMPTS:
            continue
        seed = generation_provider_seed(split_seed, dataset, label, index, base_seed=fold)
        prompt = template.format(generation_context_json=context_json, class_condition=label,
                                 requested_count=count)
        meta = {"requested_class": label, "batch_index": index, "requested_count": count,
                "provider_seed": seed}
        started = time.perf_counter()
        try:
            result = providers.call(
                spec_model, prompt, purpose=f"phase2-llm-pool:{dataset}:s{split_seed}:f{fold}",
                max_tokens=MAX_TOKENS, seed=seed, response_format={"type": "json_object"},
                raw_sink=lambda body, meta=meta: _append(directory / "raw.jsonl",
                                                         {**meta, "body": body}))
        except Exception as error:  # noqa: BLE001  recorded; the batch may be retried once
            _append(directory / "calls.jsonl", {**meta, "status": "failed",
                                                "error": f"{type(error).__name__}: {error}"[:500],
                                                "seconds": time.perf_counter() - started})
            continue
        parsed = parse_generation_response(
            result.text, run_id=f"study-v3-phase2-llm:{dataset}:s{split_seed}:f{fold}",
            call_id=result.call_id or f"{label}-{index}", generator_id=model,
            generator_version=spec_model.model_id, prompt_version=PROMPT_VERSION, seed=seed,
            requested_class=label, requested_count=count, transport_version="v2")
        for item_index, candidate in enumerate(parsed.candidates):
            _append(directory / "candidates.jsonl", {**meta, "item_index": item_index,
                                                     "data": candidate.data})
        for failure in parsed.failures:
            _append(directory / "parse_failures.jsonl",
                    {**meta, "error": failure.error, "recoverable": failure.recoverable})
        _append(directory / "calls.jsonl", {
            **meta, "status": "ok", "returned": len(parsed.candidates),
            "parse_failures": len(parsed.failures), "finish_reason": result.finish_reason,
            "input_tokens": result.input_tokens, "output_tokens": result.output_tokens,
            "seconds": time.perf_counter() - started})
    calls = _lines(directory / "calls.jsonl")
    summary = {"planned_batches": len(plan),
               "raw_batches": len({(r["requested_class"], r["batch_index"])
                                   for r in _lines(directory / "raw.jsonl")}),
               "failed_calls": sum(c["status"] == "failed" for c in calls),
               "candidates": len(_lines(directory / "candidates.jsonl")),
               "requested": pool_factor * budget,
               "seconds": sum(c.get("seconds", 0.0) for c in calls)}
    (directory / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return summary


def load_pool(directory: Path, spec: Any) -> tuple[pd.DataFrame, dict[str, int]]:
    """Candidates whose keys are exactly the declared features + target, unmodified.

    Records with missing or extra keys cannot pass ``complete_record`` anyway; they are
    counted here instead of being forced into a rectangular frame (which would invent NaN
    cells or columns).
    """
    expected = {*spec.feature_columns, spec.target_column}
    rows, counts = [], {"returned": 0, "keyset_mismatch": 0}
    for record in _lines(directory / "candidates.jsonl"):
        counts["returned"] += 1
        data = record["data"]
        if set(data) != expected:
            counts["keyset_mismatch"] += 1
            continue
        rows.append(data)
    frame = pd.DataFrame(rows, columns=pd.Index([*spec.feature_columns, spec.target_column]))
    return frame, counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, choices=[
        n for n, s in providers.MODELS.items() if s.provider == "ollama"])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--datasets", nargs="+", default=list(DEV))
    parser.add_argument("--seeds", type=int, nargs="+", default=list(SPLIT_SEEDS))
    parser.add_argument("--folds", type=int, nargs="+", default=list(range(K_FOLDS)))
    parser.add_argument("--pool-factor", type=int, default=4)
    parser.add_argument("--minority-share", type=float, default=0.5)
    args = parser.parse_args(argv)
    providers.load_env()
    plan = [(d, s, f) for d in args.datasets for s in args.seeds for f in args.folds]
    for finished, (dataset, seed, fold) in enumerate(plan, start=1):
        summary = generate_fold(args.model, dataset, seed, fold, args.out,
                                pool_factor=args.pool_factor,
                                minority_share=args.minority_share)
        print(dataset, seed, fold, summary, flush=True)
        (args.out / f"progress-{args.model.replace(':', '_')}.json").write_text(json.dumps(
            {"planned": len(plan), "finished": finished, "last": [dataset, seed, fold]}),
            encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
