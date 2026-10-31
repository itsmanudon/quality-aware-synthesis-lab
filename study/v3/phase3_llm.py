"""Phase 3 LLM candidate generation per benchmark (generator, dataset, split seed).

Context = inner TRAIN only (outer TRAIN minus the VALIDATION carve; TEST is never read),
built by ``llm_pools.generation_context`` and rendered into the frozen v3 prompt. Each unit
requests ``pool_factor x B`` records in batches of ``llm_pools.BATCH_SIZE`` with the frozen
minority share. Per-batch provider seeds (``generation_provider_seed``) where the provider
takes a seed (not Anthropic).

``sync``     one call at a time (Ollama, Meta), raw body persisted before parsing.
``submit``   Batch API (Anthropic, OpenAI): all pending requests of the selected units, in
             chunks; handles appended to ``batches.jsonl``.
``collect``  fetch ended batches; every raw item is persisted before parsing; parsed records
             are stored exactly as returned.

Every call or batch passes ``budget.check_budget`` first (80% per-provider stop rule) and is
appended to ``budget.jsonl``. A request that fails or errors is retried at most once.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from rcqasyn.empirical.addendum import budget_rule
from rcqasyn.generation.parser import parse_generation_response
from rcqasyn.phase2.specifications import dataset_specification
from rcqasyn.utils.seeds import generation_provider_seed
from study.v3 import budget, providers

from .llm_pools import _append, _lines, batch_plan, generation_context, prompt_template
from .phase1 import SPLIT_SEEDS
from .phase3 import BENCHROOT, benchmark_ids, frozen, split_frames

MAX_ATTEMPTS = 2
CHUNK = 500
OUTER = -1  # "fold" slot of the context seed: the outer split itself, not a cross-fit fold


def _max_tokens(spec_model: Any, count: int, n_features: int) -> int:
    need = 400 + count * (n_features + 1) * 14
    if spec_model.provider in ("meta", "openai") and spec_model.defaults.get(
            "reasoning_effort") not in (None, "none"):
        need += 2048  # reasoning tokens count against the completion budget
    return int(min(16000, need))


def unit_requests(model: str, dataset: str, seed: int, out: Path) -> tuple[Path, list[dict]]:
    """Write the unit manifest and return (unit dir, every planned request)."""
    protocol = frozen()["generators"]["llm"]["phase3"]
    spec_model = providers.MODELS[model]
    f = split_frames(dataset, seed)
    spec, inner = f["spec"], f["inner"]
    spec_dict = dataset_specification(BENCHROOT, dataset)["specification"]
    positive = str(spec.minority_label)
    budget_b = budget_rule(int((inner[spec.target_column].astype(str) == positive).sum()))
    context, reference_ids = generation_context(inner, spec, spec_dict, dataset, seed, OUTER)
    held = {int(i) for i in f["validation"].index} | set(f["test_ids"])
    if set(reference_ids) & held:
        raise ValueError("a reference row lies outside inner TRAIN")
    template, template_sha = prompt_template()
    if template_sha != frozen()["generators"]["llm"]["prompt"]["sha256"]:
        raise ValueError("prompt template differs from the frozen SHA-256")
    context_json = json.dumps(context, sort_keys=True)
    directory = out / model.replace(":", "_") / f"{dataset}__s{seed}"
    directory.mkdir(parents=True, exist_ok=True)
    # A unit keeps the batch size it was first planned with (the pilot used 10 before
    # the protocol moved to 20 for cost), so finished requests are never re-planned.
    manifest_path = directory / "manifest.json"
    size = (json.loads(manifest_path.read_text(encoding="utf-8"))["batch_size"]
            if manifest_path.exists() else int(protocol["batch_size"]))
    plan = batch_plan(budget_b, int(protocol["pool_factor"]),
                      float(protocol["minority_share"]), positive, "negative", size)
    requests = []
    for label, count, index in plan:
        seed_value = (None if spec_model.provider == "anthropic" else
                      generation_provider_seed(seed, dataset, label, index))
        if spec_model.provider == "meta" and seed_value is not None:
            # Meta's API rejects seeds outside the signed 32-bit range (HTTP 400, observed
            # in the pilot); the reduced value is still distinct per batch in practice.
            seed_value %= 2 ** 31
        requests.append({"custom_id": f"{dataset}__s{seed}__{label}__{index}",
                         "requested_class": label, "batch_index": index,
                         "requested_count": count, "provider_seed": seed_value,
                         "max_tokens": _max_tokens(spec_model, count,
                                                   len(spec.feature_columns)),
                         "prompt": template.format(generation_context_json=context_json,
                                                   class_condition=label,
                                                   requested_count=count)})
    (directory / "manifest.json").write_text(json.dumps({
        "model": model, "model_id": spec_model.model_id, "dataset_id": dataset,
        "split_seed": seed, "budget": budget_b, "pool_factor": protocol["pool_factor"],
        "minority_share": protocol["minority_share"], "batch_size": size,
        "prompt_sha256": template_sha,
        "context_sha256": hashlib.sha256(context_json.encode()).hexdigest(),
        "reference_row_ids": reference_ids, "planned_requests": len(requests),
        "outer_split_fingerprint": f["split"]["split_fingerprint"], "test_used": False},
        indent=1, sort_keys=True), encoding="utf-8")
    return directory, requests


def _state(directory: Path) -> tuple[set[str], dict[str, int]]:
    done = {r["custom_id"] for r in _lines(directory / "calls.jsonl") if r["status"] == "ok"}
    attempts: dict[str, int] = {}
    for r in _lines(directory / "calls.jsonl"):
        attempts[r["custom_id"]] = attempts.get(r["custom_id"], 0) + 1
    for r in _lines(directory / "submitted.jsonl"):
        if r["custom_id"] not in done:
            attempts[r["custom_id"]] = max(attempts.get(r["custom_id"], 0), r["attempt"])
    return done, attempts


def _record(directory: Path, request: dict[str, Any], model: str, text: str,
            result: Any) -> None:
    spec_model = providers.MODELS[model]
    parsed = parse_generation_response(
        text, run_id=f"study-v3-phase3:{directory.name}", call_id=request["custom_id"],
        generator_id=model, generator_version=spec_model.model_id,
        prompt_version="study-v3-generation-v3", seed=request["provider_seed"],
        requested_class=request["requested_class"],
        requested_count=request["requested_count"], transport_version="v2")
    meta = {k: request[k] for k in ("custom_id", "requested_class", "batch_index",
                                    "requested_count", "provider_seed")}
    for item_index, candidate in enumerate(parsed.candidates):
        _append(directory / "candidates.jsonl", {**meta, "item_index": item_index,
                                                 "data": candidate.data})
    for failure in parsed.failures:
        _append(directory / "parse_failures.jsonl",
                {**meta, "error": failure.error, "recoverable": failure.recoverable})
    _append(directory / "calls.jsonl", {
        **meta, "status": "ok", "returned": len(parsed.candidates),
        "parse_failures": len(parsed.failures),
        "finish_reason": getattr(result, "finish_reason", None),
        "input_tokens": getattr(result, "input_tokens", None),
        "output_tokens": getattr(result, "output_tokens", None),
        "reasoning_tokens": getattr(result, "reasoning_tokens", None)})


def sync(model: str, units: list[tuple[str, int]], out: Path) -> None:
    spec_model = providers.MODELS[model]
    for dataset, seed in units:
        directory, requests = unit_requests(model, dataset, seed, out)
        done, attempts = _state(directory)
        started = time.perf_counter()
        for request in requests:
            key = request["custom_id"]
            if key in done or attempts.get(key, 0) >= MAX_ATTEMPTS:
                continue
            try:
                result = providers.call(
                    spec_model, request["prompt"], purpose=f"phase3-llm:{directory.name}",
                    max_tokens=request["max_tokens"], seed=request["provider_seed"],
                    response_format={"type": "json_object"},
                    raw_sink=lambda body, k=key, d=directory: _append(
                        d / "raw.jsonl", {"custom_id": k, "body": body}))
            except budget.BudgetStop:
                raise
            except Exception as error:  # noqa: BLE001  recorded; one retry allowed
                _append(directory / "calls.jsonl", {
                    "custom_id": key, "requested_class": request["requested_class"],
                    "batch_index": request["batch_index"], "status": "failed",
                    "error": f"{type(error).__name__}: {error}"[:500]})
                continue
            _record(directory, request, model, result.text, result)
        print(model, dataset, seed, f"{time.perf_counter() - started:.0f}s", flush=True)


def submit(model: str, units: list[tuple[str, int]], out: Path, max_chunks: int | None = None
           ) -> int:
    spec_model = providers.MODELS[model]
    pending: list[tuple[Path, dict[str, Any], int]] = []
    root = out / model.replace(":", "_")
    collected = {h["batch_id"] for h in _lines(root / "collected.jsonl")}
    for dataset, seed in units:
        directory, requests = unit_requests(model, dataset, seed, out)
        done, attempts = _state(directory)
        for request in requests:
            n = attempts.get(request["custom_id"], 0)
            if request["custom_id"] in done or n >= MAX_ATTEMPTS:
                continue
            if any(r["custom_id"] == request["custom_id"] and r["batch_id"] not in collected
                   for r in _lines(directory / "submitted.jsonl")):
                continue  # still in flight
            pending.append((directory, request, n + 1))
    # The budget guard only sees collected spend, so callers submit one chunk, collect it,
    # then submit the next (max_chunks=1) to keep in-flight cost inside the guard's view.
    current = budget.spend(spec_model.provider)
    headroom = (current.stop_at_usd or 0.0) - current.known_usd
    start, chunks = 0, 0
    while start < len(pending) and (max_chunks is None or chunks < max_chunks):
        # Largest chunk whose summed worst case fits under the 80% line; the guard inside
        # submit_batch re-checks it. If not even one request fits, the guard stops us.
        size, total = 0, 0.0
        for _, request, _ in pending[start:start + CHUNK]:
            cost = budget.worst_case_cost(spec_model.model_id,
                                          prompt_chars=len(request["prompt"]),
                                          max_output_tokens=request["max_tokens"], batch=True)
            if size and total + cost > headroom:
                break
            size, total = size + 1, total + cost
        chunk = pending[start:start + size]
        start, chunks = start + size, chunks + 1
        headroom -= total
        handle = providers.submit_batch(spec_model, [providers.BatchRequest(
            custom_id=r["custom_id"], prompt=r["prompt"], max_tokens=r["max_tokens"],
            seed=r["provider_seed"], response_format=None if spec_model.provider == "anthropic"
            else {"type": "json_object"}) for _, r, _ in chunk],
            purpose=f"phase3-llm-{start // CHUNK}-{int(time.time())}", work_dir=root / "work")
        _append(root / "batches.jsonl", {**handle, "collected": False})
        for directory, request, attempt in chunk:
            _append(directory / "submitted.jsonl", {"custom_id": request["custom_id"],
                                                    "attempt": attempt,
                                                    "batch_id": handle["batch_id"]})
        print(model, "submitted", len(chunk), handle["batch_id"], flush=True)
    return len(pending)


def collect(model: str, out: Path) -> int:
    spec_model = providers.MODELS[model]
    root = out / model.replace(":", "_")
    handles = _lines(root / "batches.jsonl")
    collected = {h["batch_id"] for h in _lines(root / "collected.jsonl")}
    open_batches = 0
    for handle in handles:
        if handle["batch_id"] in collected:
            continue
        status = providers.batch_status(spec_model, handle["batch_id"])
        if status != "ended":
            open_batches += 1
            print(model, handle["batch_id"], status, flush=True)
            continue

        def sink(item: dict[str, Any]) -> None:
            dataset, seed = item["custom_id"].split("__")[:2]
            _append(root / f"{dataset}__{seed}" / "raw.jsonl",
                    {"custom_id": item["custom_id"], "body": item})

        results = providers.collect_batch(spec_model, handle, raw_sink=sink)
        for custom_id in handle["custom_ids"]:
            dataset, seed = custom_id.split("__")[:2]
            directory = root / f"{dataset}__{seed}"
            _, requests = unit_requests(model, dataset, int(seed[1:]), out)
            request = next(r for r in requests if r["custom_id"] == custom_id)
            result = results.get(custom_id)
            if isinstance(result, providers.CallResult):
                _record(directory, request, model, result.text, result)
            else:
                _append(directory / "calls.jsonl", {
                    "custom_id": custom_id, "requested_class": request["requested_class"],
                    "batch_index": request["batch_index"], "status": "failed",
                    "error": json.dumps(result, default=str)[:500] if result else "MISSING"})
        _append(root / "collected.jsonl", {"batch_id": handle["batch_id"]})
        print(model, "collected", handle["batch_id"], flush=True)
    return open_batches


def summary(model: str, out: Path) -> dict[str, Any]:
    root = out / model.replace(":", "_")
    rows = {}
    for directory in sorted(p for p in root.glob("oml*__s*") if p.is_dir()):
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        calls = _lines(directory / "calls.jsonl")
        rows[directory.name] = {
            "planned": manifest["planned_requests"],
            "ok": sum(c["status"] == "ok" for c in calls),
            "failed": sum(c["status"] == "failed" for c in calls),
            "candidates": len(_lines(directory / "candidates.jsonl")),
            "requested": manifest["pool_factor"] * manifest["budget"],
            "output_tokens": sum(c.get("output_tokens") or 0 for c in calls),
            "input_tokens": sum(c.get("input_tokens") or 0 for c in calls)}
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("sync", "submit", "collect", "summary"))
    parser.add_argument("--model", required=True, choices=list(providers.MODELS))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--datasets", nargs="+", default=None)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(SPLIT_SEEDS))
    parser.add_argument("--max-chunks", type=int, default=None)
    args = parser.parse_args(argv)
    providers.load_env()
    units = [(d, s) for d in (args.datasets or benchmark_ids()) for s in args.seeds]
    if args.command == "sync":
        sync(args.model, units, args.out)
    elif args.command == "submit":
        print("pending:", submit(args.model, units, args.out, args.max_chunks))
    elif args.command == "collect":
        print("open batches:", collect(args.model, args.out))
    else:
        rows = summary(args.model, args.out)
        print(json.dumps(rows, indent=1))
        totals = {k: sum(r[k] for r in rows.values()) for k in
                  ("planned", "ok", "failed", "candidates", "requested", "input_tokens",
                   "output_tokens")}
        print(json.dumps(totals))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

