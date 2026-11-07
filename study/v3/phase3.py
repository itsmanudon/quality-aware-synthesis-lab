"""Phase 3 benchmark pipeline, main-venv side (frozen protocol; see protocol.json).

Per benchmark (dataset, outer split seed): outer split by ``make_split`` on the converted
benchmark root; VALIDATION = stratified 20% of TRAIN (``carve_validation``); inner TRAIN =
TRAIN minus VALIDATION. Every generator, gate and curator sees inner TRAIN only. Final models
are chosen on VALIDATION and refitted on TRAIN by ``u3_eval.py`` (U2 venv), which alone
reads TEST.

Subcommands:

``jobs``     U2-side generation jobs (no TEST ids) for ``u3_pools.py``.
``curate``   for each unit: merged candidate pool = U2-side SMOTE + U2 native + U2 flow-gate
             pools (4 x B each) + every available LLM pool; the frozen rounding variant where
             integer fields are declared; the q = 0.90 gate; then the equal-budget curators
             (random, schema-random, QC, CLLM-style, discriminator-realism, B2 at equal budget)
             and the merged method (boundary filter + QC), plus per-generator merged
             variants; and the main-venv oversampler comparators (ROS, Borderline-SMOTE, ADASYN,
             SMOTE-Tomek; addendum v2 unavailability rules). Writes one evaluation job per unit
             (selected minority rows, removals, flags) including TEST ids for u3_eval.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

from rcqasyn.baselines.validators import ValidatorSuite, rejects
from rcqasyn.contracts.candidate import CandidateRecord
from rcqasyn.contracts.enums import Severity
from rcqasyn.datasets.loader import load_dataset
from rcqasyn.datasets.registry import DatasetRegistry
from rcqasyn.datasets.split import make_split
from rcqasyn.empirical.addendum import budget_rule
from rcqasyn.empirical.addendum_v2 import (
    Unavailable,
    cllm_style,
    discriminator_realism,
    encoder,
)
from rcqasyn.empirical.generation import fresh_geometry, generate
from rcqasyn.phase2.common import digest
from rcqasyn.phase2.specifications import dataset_specification
from rcqasyn.phase5.geometry import metrics
from rcqasyn.phase6.utility import outer_frames

from .claims import claim, release
from .devroot import sha256_file
from .llm_pools import load_pool
from .phase1 import SPLIT_SEEDS, carve_validation, construct
from .repair_v3 import repair_pool
from .utility import Space, band, boundary_share, utility_filter

HERE = Path(__file__).resolve().parent
BENCHROOT = (HERE / "runs" / "benchroot").resolve()
SELECTION_SEED = 13
U2_POOLS = ("pool:smote", "pool:u2_native", "pool:u2_flow_gate")
GATE_UNAVAILABLE = "GATE_NO_COMPLETE_TRAIN_ROW"
GATED_CURATORS = ("random", "schema-random", "quality-coverage", "cllm-style",
                  "discriminator-realism")


def frozen() -> dict[str, Any]:
    return json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))


def benchmark_ids() -> list[str]:
    sources = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))["datasets"]
    return [f"oml{d['openml_id']}" for d in sources if d["role"] == "benchmark"]


def split_frames(dataset: str, seed: int) -> dict[str, Any]:
    registry = DatasetRegistry(project_root=BENCHROOT)
    spec = registry.get(dataset)
    loaded = load_dataset(spec, registry)
    split = make_split(loaded, seed).to_dict()
    train, test = outer_frames(loaded.frame, split)
    inner_ids, val_ids = carve_validation(train, spec.target_column, dataset, seed)
    return {"spec": spec, "loaded": loaded, "split": split, "train": train,
            "test_ids": [int(i) for i in test.index], "inner": train.loc[inner_ids],
            "validation": train.loc[val_ids]}


def jobs(out: Path, datasets: list[str], seeds: list[int]) -> None:
    rows = []
    for dataset in datasets:
        for seed in seeds:
            f = split_frames(dataset, seed)
            spec, inner = f["spec"], f["inner"]
            budget = budget_rule(int((inner[spec.target_column] == spec.minority_label).sum()))
            rows.append({"dataset_id": dataset, "split_seed": seed, "budget": budget,
                         "dat_path": str(Path(f["loaded"].path).resolve()),
                         "dat_sha256": sha256_file(Path(f["loaded"].path)),
                         "inner_ids": [int(i) for i in inner.index],
                         "validation_ids": [int(i) for i in f["validation"].index]})
            print(dataset, seed, budget, len(inner), flush=True)
    out.mkdir(parents=True, exist_ok=True)
    (out / "jobs.json").write_text(json.dumps(rows, sort_keys=True), encoding="utf-8")


def _nulls(frame: pd.DataFrame) -> pd.DataFrame:
    """NaN cells as None (JSON null); a frame without missing cells is returned unchanged."""
    if not bool(frame.isna().to_numpy().any()):
        return frame
    return frame.astype(object).where(frame.notna(), None)


def _records(frame: pd.DataFrame, spec: Any, *, minority_only: bool = True) -> list[dict]:
    rows = frame.loc[frame[spec.target_column] == spec.minority_label] if minority_only else frame
    records: list[dict[str, Any]] = pd.DataFrame(rows[list(spec.feature_columns)]).to_dict(
        orient="records")
    return [{k: (None if pd.isna(v) else v.item() if hasattr(v, "item") else v)
             for k, v in r.items()} for r in records]


def _u2_frame(output: dict[str, Any], spec: Any) -> pd.DataFrame:
    if output.get("status") != "ok" or not output.get("records"):
        return pd.DataFrame(columns=pd.Index([*spec.feature_columns, spec.target_column]))
    by_lower = {c.lower(): c for c in spec.feature_columns}
    frame = pd.DataFrame(output["records"]).rename(columns=lambda c: by_lower[str(c).lower()])
    frame = frame.reindex(columns=list(spec.feature_columns))
    frame[spec.target_column] = output["labels"]
    return frame


def _b2_equal(inner: pd.DataFrame, spec: Any, candidates: pd.DataFrame, budget: int
              ) -> tuple[list[int], dict[str, Any]]:
    """B2 unchanged (ValidatorSuite + rejects, HIGH/CRITICAL, exact duplicates) at budget B."""
    numeric_summary = {}
    for column in spec.numerical_columns:
        values = pd.Series(pd.to_numeric(inner[column], errors="coerce"), dtype=float).dropna()
        if len(values):
            q = np.quantile(values.to_numpy(), [0, .25, .5, .75, 1])
            numeric_summary[column] = dict(zip(("min", "q25", "median", "q75", "max"),
                                               map(float, q), strict=True))
    domains = {c: tuple(sorted(str(v) for v in inner[c].dropna().unique()))
               for c in spec.categorical_columns}
    domains[spec.target_column] = tuple(sorted(str(v) for v in inner[spec.target_column].unique()))
    profile: Any = SimpleNamespace(domains=domains, numeric_summary=numeric_summary)
    suite = ValidatorSuite(spec, profile)
    accepted, seen = [], set()
    from datetime import UTC, datetime

    for position, payload in enumerate(candidates.to_dict(orient="records")):
        data = {k: (None if isinstance(v, float) and np.isnan(v) else v)
                for k, v in payload.items()}
        record = CandidateRecord(record_id=f"b2eq-{position}", version=1, data=data,
                                 raw_output="", generator_id="study-v3-pool",
                                 generator_version="1", prompt_version=None, seed=None,
                                 created_at=datetime.now(UTC),
                                 metadata={"requested_class": str(spec.minority_label)})
        key = digest(data)
        duplicate = key in seen
        seen.add(key)
        evidence = suite.validate(record, expected_class=str(spec.minority_label))
        if not duplicate and not rejects(evidence, frozenset({Severity.HIGH,
                                                              Severity.CRITICAL})):
            accepted.append(position)
    chosen = np.random.default_rng(SELECTION_SEED).permutation(accepted)[:budget].tolist()
    return [int(i) for i in chosen], {"b2_accepted_n": len(accepted)}


def _tomek(inner: pd.DataFrame, spec: Any, budget: int, seed: int
           ) -> tuple[pd.DataFrame, list[int], dict[str, Any]]:
    """SMOTE(NC) to +B, then imblearn TomekLinks(sampling_strategy='all') as in SMOTETomek."""
    from imblearn.under_sampling import TomekLinks

    method = "SMOTENC" if spec.categorical_columns else "SMOTE"
    synthetic, _ = generate(inner, spec, method, budget, seed)
    synthetic = synthetic.loc[synthetic[spec.target_column] == spec.minority_label]
    combined = pd.concat([inner, synthetic], ignore_index=True)
    encode = encoder(inner, spec)
    x = np.asarray(encode(combined), dtype=float)
    numeric = [i for i, c in enumerate(spec.feature_columns) if c in spec.numerical_columns]
    if not spec.categorical_columns and numeric:
        x = (x - x[:len(inner)].mean(axis=0)) / np.where(x[:len(inner)].std(axis=0) > 0,
                                                         x[:len(inner)].std(axis=0), 1)
    links = TomekLinks(sampling_strategy="all").fit(x, combined[spec.target_column].astype(str))
    links.fit_resample(x, combined[spec.target_column].astype(str))
    kept = {int(i) for i in links.sample_indices_}
    inner_ids = [int(i) for i in inner.index.to_numpy()]
    removed = [inner_ids[i] for i in range(len(inner)) if i not in kept]
    kept_synth = synthetic.iloc[[i - len(inner) for i in sorted(kept) if i >= len(inner)]]
    return kept_synth, removed, {"removed_real_n": len(removed),
                                 "removed_synthetic_n": len(synthetic) - len(kept_synth)}


def curate_unit(dataset: str, seed: int, u2_dir: Path, llm_dir: Path | None,
                generators: list[str]) -> dict[str, Any]:
    protocol = frozen()
    method_cfg = protocol["merged_method"]
    f = split_frames(dataset, seed)
    spec, inner, split = f["spec"], f["inner"], f["split"]
    specification = dataset_specification(BENCHROOT, dataset)
    spec_dict = specification["specification"]
    target, positive = spec.target_column, spec.minority_label
    budget = budget_rule(int((inner[target] == positive).sum()))
    export = json.loads((u2_dir / "units" / f"{dataset}__s{seed}.json").read_text("utf-8"))
    if export["job"]["budget"] != budget:
        raise ValueError("budget differs from the U2 export")
    unit: dict[str, Any] = {"dataset_id": dataset, "split_seed": seed, "budget": budget,
                            "outer_split_fingerprint": split["split_fingerprint"],
                            "methods": {}, "pools": {}, "unavailable": {}}
    sources: dict[str, pd.DataFrame] = {name: _u2_frame(export["outputs"].get(name, {}), spec)
                                        for name in U2_POOLS}
    for g in generators:
        directory = (llm_dir / g.replace(":", "_") / f"{dataset}__s{seed}") if llm_dir else None
        if directory is None or not (directory / "candidates.jsonl").exists():
            unit["unavailable"][f"pool:llm:{g}"] = "NO_LLM_POOL"
            continue
        frame, counts = load_pool(directory, spec)
        unit["pools"][f"llm:{g}"] = counts
        sources[f"pool:llm:{g}"] = frame
    integer = any(x.get("source_declaration", "").startswith("integer")
                  for x in spec_dict["features"])
    llm_names = [n for n in sources if n.startswith("pool:llm:")]
    variants: dict[str, list[str]] = {"merged": list(sources),
                                      "merged[no-llm]": list(U2_POOLS)}
    for n in llm_names:
        variants[f"merged[{n.removeprefix('pool:')}]"] = [*U2_POOLS, n]
    space = Space(inner, spec)
    fingerprint = digest({"outer": split["split_fingerprint"],
                          "validation": [int(i) for i in f["validation"].index]})

    def build(names: list[str], rounded: bool) -> tuple[Any, ...] | None:
        frames = [sources[n] for n in names if not sources[n].empty]
        if not frames:
            return None
        pool = pd.concat(frames, ignore_index=True)
        info: dict[str, Any] = {"candidates_n": len(pool)}
        if rounded and integer:
            pool, outcome = repair_pool(pool, spec_dict)
            info["repair"] = outcome["outcomes"]
        # Missing cells reach the gate as null (preserve_as_null), not NaN: the gate's JSON
        # fingerprints refuse NaN. Datasets without missing cells are passed unchanged.
        g, admitted, concerns, _ = fresh_geometry(
            _nulls(inner), _nulls(pool), specification, fingerprint,
            {"generator": "study-v3-phase3:" + "+".join(names), "rounded": rounded,
             "fit_row_ids": [int(i) for i in inner.index],
             "payload_fingerprint": digest(_nulls(pool).to_dict(orient="records"))})
        info.update({f"{k}_admitted_n": len(v) for k, v in admitted.items()})
        return g, admitted, concerns, pool, info

    def selected(g: Any, chosen: list[int]) -> list[dict]:
        frame = pd.DataFrame([g.occurrences[i]["payload"] for i in chosen],
                             columns=pd.Index([*spec.feature_columns, target]))
        return _records(frame, spec)

    def add(name: str, records: list[dict], info: dict[str, Any], **extra: Any) -> None:
        if len(records) < budget:
            unit["unavailable"][name] = f"MATCHED_BUDGET_SHORTFALL ({len(records)} < {budget})"
            return
        unit["methods"][name] = {"add": records, "remove_ids": [], **extra, "info": info}

    beta, rho = float(method_cfg["beta"]), float(method_cfg["rho"])
    for variant, names in variants.items():
        for rounded in ((True, False) if integer else (True,)):
            label = variant + ("" if rounded or not integer else "[unrounded]")
            try:
                built = build(names, rounded)
            except ValueError as error:
                if "no supported TRAIN feature reference" not in str(error):
                    raise
                # The gate's geometry is fitted on complete TRAIN rows only; with none (ipums:
                # every row has a missing cell) no gated method exists for this unit.
                unit["unavailable"][label] = GATE_UNAVAILABLE
                if label == "merged":
                    for name in GATED_CURATORS:
                        unit["unavailable"][name] = GATE_UNAVAILABLE
                    pool = pd.concat([sources[n] for n in names if not sources[n].empty],
                                     ignore_index=True)
                    try:  # B2 needs no geometry
                        chosen, extra = _b2_equal(inner, spec, pool, budget)
                        add("b2-equal-budget", _records(pool.iloc[chosen], spec), extra)
                    except (ValueError, TypeError, RuntimeError) as b2_error:
                        unit["unavailable"]["b2-equal-budget"] = (
                            f"{type(b2_error).__name__}: {b2_error}"[:300])
                continue
            if built is None:
                unit["unavailable"][label] = "EMPTY_POOL"
                continue
            g, admitted, concerns, pool, info = built
            unit["pools"][label] = info
            eligible = admitted["combined"]
            if len(eligible) < budget:
                unit["unavailable"][label] = f"MATCHED_BUDGET_SHORTFALL ({len(eligible)})"
                continue
            payloads = pd.DataFrame([g.occurrences[i]["payload"] for i in eligible],
                                    columns=pd.Index([*spec.feature_columns, target]))
            ids = {i: g.occurrences[i]["occurrence_id"] for i in eligible}
            share = boundary_share(space, inner, payloads, target, str(positive))
            values = dict(zip(eligible, band(share, beta).tolist(), strict=True))
            kept = utility_filter(eligible, values, rho, budget, ids)
            frame, built_info = construct(g, kept, concerns, "quality-coverage", budget, 42)
            add(label, _records(frame, spec), built_info)
            if label != "merged":
                continue
            # Equal-budget curators over the same merged (rounded) pool.
            for name, subset, strategy in (("random", eligible, "random"),
                                           ("schema-random", admitted["schema"], "random"),
                                           ("quality-coverage", eligible, "quality-coverage")):
                frame, built_info = construct(g, subset, concerns, strategy, budget,
                                              SELECTION_SEED if strategy == "random" else 42)
                add(name, _records(frame, spec), built_info)
            for name, curator in (("cllm-style", cllm_style),
                                  ("discriminator-realism", discriminator_realism)):
                try:
                    chosen, extra = curator(inner, spec, g, eligible, budget)
                    add(name, selected(g, chosen), {**extra, **metrics(g, chosen, eligible,
                                                                       .05, .01)})
                except (ValueError, TypeError, RuntimeError, Unavailable) as error:
                    unit["unavailable"][name] = f"{type(error).__name__}: {error}"[:300]
            try:
                chosen, extra = _b2_equal(inner, spec, pool, budget)
                frame = pool.iloc[chosen]
                add("b2-equal-budget", _records(frame, spec), extra)
            except (ValueError, TypeError, RuntimeError) as error:
                unit["unavailable"]["b2-equal-budget"] = f"{type(error).__name__}: {error}"[:300]
    # Main-venv oversampler comparators at budget B (addendum v2 unavailability rules).
    from rcqasyn.empirical.addendum_v2 import resample

    try:
        # ROS copies TRAIN rows (missing cells included); its TRAIN fingerprint needs null.
        ros, _ = generate(_nulls(inner), spec, "RandomOverSampler", budget, seed)
        add("ros", _records(ros, spec), {})
    except (ValueError, TypeError, RuntimeError) as error:
        unit["unavailable"]["ros"] = f"{type(error).__name__}: {error}"[:300]
    for name, method in (("borderline-smote", "Borderline-SMOTE"), ("adasyn", "ADASYN")):
        try:
            frame, info = resample(inner, spec, method, "budget", budget)
            synthetic = frame.iloc[len(inner):] if len(frame) >= len(inner) else frame.iloc[0:0]
            add(name, _records(synthetic, spec), {k: v for k, v in info.items()
                                                  if k != "output_fingerprint"})
        except (ValueError, TypeError, RuntimeError, Unavailable) as error:
            unit["unavailable"][name] = f"{type(error).__name__}: {error}"[:300]
    try:
        if inner[list(spec.feature_columns)].isna().any().any():
            raise Unavailable("MISSING_SOURCE_FIELDS_NOT_IMPUTED")
        synth, removed, info = _tomek(inner, spec, budget, seed)
        unit["methods"]["smote-tomek"] = {"add": _records(synth, spec), "remove_ids": removed,
                                          "info": info}
    except (ValueError, TypeError, RuntimeError, Unavailable) as error:
        unit["unavailable"]["smote-tomek"] = f"{type(error).__name__}: {error}"[:300]
    unit["methods"]["no-oversampling"] = {"add": [], "remove_ids": [], "info": {}}
    unit["methods"]["class-weighted"] = {"add": [], "remove_ids": [], "class_weight": True,
                                         "info": {}}
    for name in ("smote", "kmeans_smote", "rwo", "original_ugo", "u2"):
        output = export["outputs"].get(name, {})
        if output.get("status") != "ok":
            unit["unavailable"][name] = output.get("reason", "MISSING")
            continue
        # Generators that may stop short (UGO, U2's gate rejects without refilling) are
        # evaluated with what they produced; the equal-budget rule binds the curators.
        unit["methods"][name] = {"add": _records(_u2_frame(output, spec), spec),
                                 "remove_ids": [], "info": {"n": output["n"],
                                                            "budget": budget}}
    return unit


def curate(u2_dir: Path, llm_dir: Path | None, generators: list[str], out: Path,
           datasets: list[str], seeds: list[int]) -> None:
    (out / "units").mkdir(parents=True, exist_ok=True)
    for dataset in datasets:
        for seed in seeds:
            path = out / "units" / f"{dataset}__s{seed}.json"
            if path.exists() or not claim(path):
                continue  # done, or another curation worker holds it
            start = time.perf_counter()
            unit = curate_unit(dataset, seed, u2_dir, llm_dir, generators)
            f = split_frames(dataset, seed)
            unit.update({"dat_path": str(Path(f["loaded"].path).resolve()),
                         "dat_sha256": sha256_file(Path(f["loaded"].path)),
                         "inner_ids": [int(i) for i in f["inner"].index],
                         "validation_ids": [int(i) for i in f["validation"].index],
                         "test_ids": f["test_ids"], "feature_columns":
                         list(f["spec"].feature_columns),
                         "runtime_seconds": time.perf_counter() - start})
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(unit, sort_keys=True, default=str), encoding="utf-8")
            tmp.replace(path)
            release(path)
            print(dataset, seed, len(unit["methods"]), "methods,",
                  len(unit["unavailable"]), "unavailable,",
                  f"{unit['runtime_seconds']:.0f}s", Counter(
                      k.split(":")[0] for k in unit["unavailable"]), flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    j = sub.add_parser("jobs")
    j.add_argument("--out", type=Path, required=True)
    j.add_argument("--datasets", nargs="+", default=None)
    j.add_argument("--seeds", type=int, nargs="+", default=list(SPLIT_SEEDS))
    c = sub.add_parser("curate")
    c.add_argument("--u2", type=Path, required=True)
    c.add_argument("--llm", type=Path, default=None)
    c.add_argument("--generators", nargs="*", default=[])
    c.add_argument("--out", type=Path, required=True)
    c.add_argument("--datasets", nargs="+", default=None)
    c.add_argument("--seeds", type=int, nargs="+", default=list(SPLIT_SEEDS))
    args = parser.parse_args(argv)
    datasets = args.datasets or benchmark_ids()
    if args.command == "jobs":
        jobs(args.out, datasets, args.seeds)
    else:
        curate(args.u2, args.llm, args.generators, args.out, datasets, args.seeds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
