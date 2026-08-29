"""M1.4 regression tests for the generation seed / diversity confound.

The M1.3 P0-v2 pilot reused one configured ``provider_seed`` for every
generation batch, so identical same-class prompts replayed byte-identical raw
responses (exact 75% duplicate rate on every dataset).  The correction derives a
deterministic, unique provider seed per (dataset, requested class, batch index)
and persists the exact seed sent in the provider-call artifact.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rcqasyn.config import load_experiment_config
from rcqasyn.experiments import run_experiment
from rcqasyn.utils.seeds import PROVIDER_SEED_MODULUS, generation_provider_seed


def test_same_root_dataset_class_batch_gives_same_seed() -> None:
    first = generation_provider_seed(42, "page-blocks0", "negative", 0, base_seed=42)
    second = generation_provider_seed(42, "page-blocks0", "negative", 0, base_seed=42)
    assert first == second
    # Pinned value: locks the SHA-256 derivation and proves independence from
    # Python's randomized built-in hash().
    assert first == 1165294667


def test_different_batch_gives_different_seed() -> None:
    seeds = [
        generation_provider_seed(42, "page-blocks0", "negative", index, base_seed=42)
        for index in range(4)
    ]
    assert len(set(seeds)) == 4
    assert seeds == [1165294667, 2376344276, 1745729287, 2055655221]


def test_different_class_gives_different_seed() -> None:
    negative = generation_provider_seed(42, "page-blocks0", "negative", 0, base_seed=42)
    positive = generation_provider_seed(42, "page-blocks0", "positive", 0, base_seed=42)
    assert negative != positive


def test_different_dataset_gives_different_seed() -> None:
    page_blocks = generation_provider_seed(42, "page-blocks0", "negative", 0, base_seed=42)
    ecoli = generation_provider_seed(42, "Ecoli4", "negative", 0, base_seed=42)
    abalone = generation_provider_seed(42, "Abalone19", "negative", 0, base_seed=42)
    assert len({page_blocks, ecoli, abalone}) == 3


def test_seed_falls_within_provider_supported_uint32_range() -> None:
    for dataset_id in ("page-blocks0", "Ecoli4", "Abalone19"):
        for target_class in ("negative", "positive"):
            for batch_index in range(8):
                seed = generation_provider_seed(42, dataset_id, target_class, batch_index, base_seed=42)
                assert isinstance(seed, int)
                assert 0 <= seed < PROVIDER_SEED_MODULUS == 2**32


def test_configured_base_seed_still_influences_the_derived_seed() -> None:
    assert generation_provider_seed(42, "page-blocks0", "negative", 0, base_seed=1) != generation_provider_seed(
        42, "page-blocks0", "negative", 0, base_seed=2
    )
    assert generation_provider_seed(42, "page-blocks0", "negative", 0) != generation_provider_seed(
        42, "page-blocks0", "negative", 0, base_seed=0
    )


def test_invalid_arguments_are_rejected() -> None:
    with pytest.raises(ValueError, match="batch_index"):
        generation_provider_seed(42, "page-blocks0", "negative", -1)
    with pytest.raises(ValueError, match="non-empty"):
        generation_provider_seed(42, "", "negative", 0)


def test_provider_call_artifact_stores_the_exact_derived_batch_seed(tmp_path: Path) -> None:
    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    config = config.model_copy(update={"artifact_root": tmp_path, "run_id": "seed-audit"})
    assert config.generation.provider_seed == 42
    result = run_experiment(config, project_root=Path.cwd(), replay=True)

    traces = [
        json.loads(line)
        for line in (result.artifact_dir / "provider_calls.jsonl").read_text().splitlines()
    ]
    generation_traces = [trace for trace in traces if trace["role"] == "generation"]
    assert generation_traces

    by_class = {trace["requested_class"]: trace for trace in generation_traces}
    for target_class, trace in by_class.items():
        expected = generation_provider_seed(
            config.dataset.root_seed, config.dataset.dataset_id, target_class, 0, base_seed=42
        )
        assert trace["seed"] == expected
        assert trace["metadata"]["batch_index"] == 0

    # The reused-seed confound: same-class batches must no longer share a seed,
    # and different classes already diverge here.
    assert len({trace["seed"] for trace in generation_traces}) == len(generation_traces)


def test_candidate_records_carry_the_derived_seed(tmp_path: Path) -> None:
    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    config = config.model_copy(update={"artifact_root": tmp_path, "run_id": "seed-audit-candidates"})
    result = run_experiment(config, project_root=Path.cwd(), replay=True)

    candidates = [
        json.loads(line)
        for line in (result.artifact_dir / "candidates_raw.jsonl").read_text().splitlines()
    ]
    assert candidates
    valid_seeds = {
        generation_provider_seed(
            config.dataset.root_seed, config.dataset.dataset_id, target_class, 0, base_seed=42
        )
        for target_class in ("no", "yes")
    }
    for candidate in candidates:
        assert candidate["seed"] in valid_seeds
