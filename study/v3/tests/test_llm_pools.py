"""Offline tests for the Phase 2 LLM pool helpers (no provider calls)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from study.v3.llm_pools import (
    BATCH_SIZE,
    REFERENCES_PER_CLASS,
    batch_plan,
    generation_context,
    load_pool,
    prompt_template,
)

SPEC = SimpleNamespace(numerical_columns=("a",), categorical_columns=("k",),
                       feature_columns=("a", "k"), target_column="Class",
                       minority_label="positive")
SPEC_DICT = {"features": [{"name": "a", "type": "numerical", "source_declaration": "integer"},
                          {"name": "k", "type": "categorical", "source_declaration": "nominal"}]}


def _inner() -> pd.DataFrame:
    return pd.DataFrame({"a": [1, 2, 3, 4, 5, 6, 7, 8],
                         "k": ["x", "y", "x", "y", "x", "y", "x", "y"],
                         "Class": ["positive"] * 4 + ["negative"] * 4},
                        index=pd.Index([10, 11, 12, 13, 20, 21, 22, 23]))


def test_batch_plan_splits_the_pool_by_class_share() -> None:
    plan = batch_plan(30, 4, 0.5, "positive", "negative")
    assert sum(c for label, c, _ in plan if label == "positive") == 60
    assert sum(c for label, c, _ in plan if label == "negative") == 60
    assert max(c for _, c, _ in plan) == BATCH_SIZE
    assert [i for label, _, i in plan if label == "positive"] == list(range(6))
    uneven = batch_plan(31, 4, 0.5, "positive", "negative")
    assert sum(c for _, c, _ in uneven) == 124 and min(c for _, c, _ in uneven) == 2


def test_generation_context_uses_inner_rows_and_declarations_only() -> None:
    inner = _inner()
    context, refs = generation_context(inner, SPEC, SPEC_DICT, "toy", 13, 0)
    assert context["fields"]["a"]["declaration"] == "integer"
    assert context["class_counts"] == {"negative": 4, "positive": 4}
    assert context["numeric_summary"]["a"]["max"] == 8.0
    assert len(refs) == 2 * REFERENCES_PER_CLASS and set(refs) <= set(inner.index)
    assert [r["Class"] for r in context["reference_examples"]].count("positive") == 3
    assert generation_context(inner, SPEC, SPEC_DICT, "toy", 13, 0)[1] == refs
    json.dumps(context)  # JSON-serializable without default=


def test_prompt_template_renders_with_doubled_braces() -> None:
    template, sha = prompt_template()
    text = template.format(generation_context_json="{}", class_condition="positive",
                           requested_count=10)
    assert '{"records":[{"field": "value"}]}' in text and len(sha) == 64


def test_load_pool_keeps_exact_keysets_unmodified(tmp_path: Path) -> None:
    lines = [{"data": {"a": 1.5, "k": "x", "Class": "positive"}},
             {"data": {"a": 2, "k": "z", "Class": "positive", "extra": 1}},
             {"data": {"a": "3", "Class": "negative"}}]
    (tmp_path / "candidates.jsonl").write_text(
        "\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    frame, counts = load_pool(tmp_path, SPEC)
    assert counts == {"returned": 3, "keyset_mismatch": 2}
    assert frame.to_dict(orient="records") == [{"a": 1.5, "k": "x", "Class": "positive"}]


def test_label_sample_round_robins_models_and_is_deterministic(tmp_path: Path) -> None:
    from study.v3.label_sample import HUMAN_COLUMNS, sample

    for model, n in (("m_a", 5), ("m_b", 1)):
        unit = tmp_path / model / "toy__s13__f0"
        unit.mkdir(parents=True)
        (unit / "candidates.jsonl").write_text("\n".join(json.dumps(
            {"requested_class": "positive", "batch_index": 0, "item_index": i,
             "data": {"a": i, "Class": "positive"}}) for i in range(n)) + "\n",
            encoding="utf-8")
    rows = sample(tmp_path, ["m_a", "m_b"], ["toy"], 4)
    assert len(rows) == 4 and sorted(r["model"] for r in rows) == ["m_a"] * 3 + ["m_b"]
    assert rows == sample(tmp_path, ["m_a", "m_b"], ["toy"], 4)
    assert all(r["review_id"].startswith("v3r-") for r in rows)
    assert HUMAN_COLUMNS[0] == "human_valid" and len(HUMAN_COLUMNS) == 5
