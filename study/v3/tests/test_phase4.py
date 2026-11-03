"""Offline checks of the Phase 4 aggregation and test rules (synthetic units, no TEST data)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from study.v3 import phase4


def _unit(dataset: str, seed: int, rows: list[dict], unavailable: dict | None = None) -> dict:
    return {"dataset_id": dataset, "split_seed": seed, "rows": rows,
            "unavailable": unavailable or {}, "protocol_sha256": phase4.frozen_sha()}


def _row(method: str, learner: str, f1: float, mcc: float | None = None) -> dict:
    return {"method": method, "classifier": learner, "status": "ok", "f1": f1,
            "mcc": f1 if mcc is None else mcc, "average_precision": f1,
            "minority_recall": f1}


def test_holm_matches_definition() -> None:
    assert phase4.holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])


def test_per_learner_drops_cells_with_fewer_than_three_splits() -> None:
    cells = pd.DataFrame([{"dataset_id": "d", "method": "m", "classifier": "lr",
                           "split_seed": s, "f1": v} for s, v in ((1, .5), (2, .7))])
    assert phase4.per_learner(cells, "f1").empty
    cells.loc[len(cells)] = {"dataset_id": "d", "method": "m", "classifier": "lr",
                             "split_seed": 3, "f1": .9}
    out = phase4.per_learner(cells, "f1")
    assert out["value"].iloc[0] == pytest.approx(.7) and out["splits"].iloc[0] == 3


def test_paired_uses_only_learners_available_for_both() -> None:
    pl = pd.DataFrame([
        {"dataset_id": "d", "method": "merged", "classifier": "lr", "value": .8, "splits": 5},
        {"dataset_id": "d", "method": "merged", "classifier": "mlp", "value": .9, "splits": 5},
        {"dataset_id": "d", "method": "class-weighted", "classifier": "lr", "value": .6,
         "splits": 5}])
    assert phase4.paired(pl, "merged", "class-weighted")["d"] == pytest.approx(.2)


def test_report_end_to_end_and_partial_flag(tmp_path: Path) -> None:
    rng = np.random.default_rng(0)
    for stage in ("primary", "rest"):
        (tmp_path / stage / "units").mkdir(parents=True)
    for i in range(12):
        for seed in (13, 29, 43):
            base = rng.uniform(.3, .8)
            primary = [_row("merged", "lr", base + .05), _row("no-oversampling", "lr", base),
                       _row("u2", "lr", base + .01)]
            rest = [_row(m, "lr", base + rng.uniform(-.02, .02))
                    for m in ("class-weighted", "smote", "original_ugo", "quality-coverage",
                              "random")]
            rest.append({"method": "smote", "classifier": "svm", "status": "unavailable",
                         "reason": "SVM_SIZE_LIMIT"})
            for stage, rows in (("primary", primary), ("rest", rest)):
                (tmp_path / stage / "units" / f"d{i}__s{seed}.json").write_text(
                    json.dumps(_unit(f"d{i}", seed, rows)), encoding="utf-8")
    text = phase4.report([tmp_path / "primary", tmp_path / "rest"], tmp_path / "out", 36)
    summary = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    assert not summary["partial"] and summary["success_criterion_met"]
    assert "smote: SVM_SIZE_LIMIT: 36" in text
    text = phase4.report([tmp_path / "primary", tmp_path / "rest"], tmp_path / "out2", 200)
    assert "PARTIAL" in text


def test_report_refuses_units_from_another_protocol(tmp_path: Path) -> None:
    (tmp_path / "e" / "units").mkdir(parents=True)
    unit = _unit("d", 13, [_row("merged", "lr", .5)])
    unit["protocol_sha256"] = "0" * 64
    (tmp_path / "e" / "units" / "d__s13.json").write_text(json.dumps(unit), encoding="utf-8")
    with pytest.raises(SystemExit):
        phase4.report([tmp_path / "e"], tmp_path / "out", 1)


def test_phase3_nulls_converts_nan_and_leaves_clean_frames_unchanged() -> None:
    from study.v3 import phase3
    clean = pd.DataFrame({"a": [1.0, 2.0], "b": ["x", "y"]})
    assert phase3._nulls(clean) is clean
    holes = pd.DataFrame({"a": [1.0, np.nan], "b": [None, "y"]})
    out = phase3._nulls(holes)
    assert out.to_dict(orient="records") == [{"a": 1.0, "b": None}, {"a": None, "b": "y"}]
    json.dumps(out.to_dict(orient="records"), allow_nan=False)
