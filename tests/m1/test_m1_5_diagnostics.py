"""M1.5 network-free tests: seed-plan guard + diagnostic-only analysis."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from rcqasyn.config import load_experiment_config
from rcqasyn.experiments import run_experiment
from rcqasyn.experiments.diagnostics import (
    classify_b2_reason,
    copying_diagnostics,
    diversity_scaling,
    p1_human_review_sample,
    support_diagnostics,
)
from rcqasyn.utils.seeds import generation_provider_seed

_HUMAN_COLUMNS = ("human_valid", "human_failure_type", "human_severity",
                  "human_affected_fields", "human_notes")


@pytest.fixture
def replay_run(tmp_path: Path) -> Path:
    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    config = config.model_copy(update={"artifact_root": tmp_path, "run_id": "m15-replay"})
    result = run_experiment(config, project_root=Path.cwd(), replay=True)
    return result.artifact_dir


# --------------------------------------------------------------------------- #
# §5 seed-plan guard
# --------------------------------------------------------------------------- #

def test_seed_plan_asserts_unique_seeds_per_tuple_and_is_persisted(replay_run: Path) -> None:
    plan = json.loads((replay_run / "generation_seed_plan.json").read_text())
    seeds = [c["provider_seed"] for c in plan["calls"]]
    tuples = [(c["dataset_id"], c["requested_class"], c["batch_index"]) for c in plan["calls"]]
    assert plan["all_seeds_unique"] is True
    assert len(set(seeds)) == len(set(tuples)) == len(seeds)
    for call in plan["calls"]:
        assert call["provider_seed"] == generation_provider_seed(
            call["root_seed"], call["dataset_id"], call["requested_class"], call["batch_index"], base_seed=42,
        )


def test_seed_plan_raises_on_a_forced_collision(monkeypatch: pytest.MonkeyPatch) -> None:
    config, _ = load_experiment_config(Path("configs/experiments/replay.yaml"))
    from rcqasyn.experiments import runner

    monkeypatch.setattr(runner, "generation_provider_seed", lambda *a, **k: 777)

    class _Q:
        def __init__(self, label: str) -> None:
            self.label, self.count = label, 10

    class _Plan:
        dataset_id = "dev-small"
        batch_size = 5
        class_quotas = (_Q("no"), _Q("yes"))

    with pytest.raises(RuntimeError, match="seed confound"):
        runner._generation_seed_plan(config, _Plan())  # type: ignore[arg-type]


def test_seed_plan_generation_trace_records_derived_seed(replay_run: Path) -> None:
    traces = [json.loads(x) for x in (replay_run / "provider_calls.jsonl").read_text().splitlines() if x.strip()]
    gen = [t for t in traces if t["role"] == "generation"]
    assert gen and len({t["seed"] for t in gen}) == len(gen)
    for t in gen:
        assert t["metadata"]["batch_index"] == 0


# --------------------------------------------------------------------------- #
# §9 copying diagnostics
# --------------------------------------------------------------------------- #

def test_copying_diagnostics_reports_three_independent_flags(replay_run: Path) -> None:
    result = copying_diagnostics(replay_run, Path.cwd())
    assert (replay_run / "copying_diagnostics.json").is_file()
    keys = {"exact_synthetic_duplicate", "exact_reference_match", "exact_nonreference_train_match"}
    for record in result["records"]:
        assert keys <= record.keys()
        assert all(isinstance(record[k], bool) for k in keys)
    overall = result["overall"]
    assert overall["records"] == len(result["records"])
    assert overall["unique_records"] <= overall["records"]
    # reconciles with the run's own exact_train_match_count
    cmp = json.loads((replay_run / "comparison.json").read_text())
    train_matches = sum(r["exact_reference_match"] or r["exact_nonreference_train_match"] for r in result["records"])
    assert train_matches == cmp["baselines"]["b1"]["exact_train_match_count"]


def test_copying_diagnostics_does_not_touch_baseline_artifacts(replay_run: Path) -> None:
    before = (replay_run / "comparison.json").read_bytes()
    copying_diagnostics(replay_run, Path.cwd())
    support_diagnostics(replay_run, Path.cwd())
    assert (replay_run / "comparison.json").read_bytes() == before


# --------------------------------------------------------------------------- #
# §10 support diagnostics
# --------------------------------------------------------------------------- #

def test_support_diagnostics_are_deterministic_and_threshold_free(replay_run: Path) -> None:
    a = support_diagnostics(replay_run, Path.cwd())
    b = support_diagnostics(replay_run, Path.cwd())
    assert a["overall"] == b["overall"]
    # exploratory only: no acceptance/validity fields on any per-record row
    for row in a["records"]:
        assert not ({"accepted", "valid", "score", "threshold"} & row.keys())
    for row in a["records"]:
        d = row["nearest_train_distance"]
        assert d is None or d >= 0.0
        if row["nearest_same_class_train_distance"] is not None and d is not None:
            assert row["nearest_same_class_train_distance"] >= d - 1e-9
    assert "categorical" in a["distance_representation"]


def test_support_diagnostics_jsonl_row_per_candidate(replay_run: Path) -> None:
    support_diagnostics(replay_run, Path.cwd())
    rows = [json.loads(x) for x in (replay_run / "support_diagnostics.jsonl").read_text().splitlines() if x.strip()]
    raw = [json.loads(x) for x in (replay_run / "candidates_raw.jsonl").read_text().splitlines() if x.strip()]
    assert len(rows) == len(raw)


# --------------------------------------------------------------------------- #
# §15 B2 reason classification
# --------------------------------------------------------------------------- #

def test_classify_b2_reason() -> None:
    assert classify_b2_reason("duplicate") == "dataset_redundancy"
    assert classify_b2_reason("configured deterministic severity rejection",
                              "categorical-domain FAIL; missing_fields") == "structural_domain_failure"
    assert classify_b2_reason("all configured deterministic checks passed") == "other"


# --------------------------------------------------------------------------- #
# §16-17 P1 human-review sample
# --------------------------------------------------------------------------- #

def test_p1_human_review_sample_is_deterministic_unique_and_blank(replay_run: Path, tmp_path: Path) -> None:
    copying_diagnostics(replay_run, Path.cwd())
    support_diagnostics(replay_run, Path.cwd())
    out = tmp_path / "p1_human_review.csv"
    r1 = p1_human_review_sample([replay_run], Path.cwd(), out, target=6, seed=42)
    first = out.read_text()
    r2 = p1_human_review_sample([replay_run], Path.cwd(), tmp_path / "again.csv", target=6, seed=42)
    assert (tmp_path / "again.csv").read_text() == first
    assert r1 == {**r2, "path": r1["path"]}

    with out.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows
    assert len({row["canonical_hash"] for row in rows}) == len(rows)  # unique-prioritised
    for row in rows:
        assert all(row[c] == "" for c in _HUMAN_COLUMNS)
        assert row["provider_call_id"] and row["provider_seed"]  # traceable to the provider call
    assert r1["human_columns_blank"] is True


# --------------------------------------------------------------------------- #
# §21 diversity scaling roll-up
# --------------------------------------------------------------------------- #

def test_diversity_scaling_pairs_datasets(replay_run: Path) -> None:
    report = diversity_scaling([replay_run], [replay_run])
    assert report["datasets"][0]["dataset_id"] == "dev-small"
    row = report["datasets"][0]
    assert row["prior_duplicate_rate"] == row["p1_duplicate_rate"]
    assert report["no_significance_claim"] is True
