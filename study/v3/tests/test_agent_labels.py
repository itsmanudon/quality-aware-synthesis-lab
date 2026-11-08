from __future__ import annotations

import json

from study.v3.agent_labels import SAMPLE, check_record, label_row

SCHEMA = json.loads((SAMPLE / "blind" / "schema_Abalone19.json").read_text(encoding="utf-8"))
GOOD = {"sex": "F", "length": 0.62, "diameter": 0.49, "height": 0.17, "whole_weight": 1.21,
        "shucked_weight": 0.48, "viscera_weight": 0.26, "shell_weight": 0.36,
        "class": "positive"}


def _rules(record: dict[str, object], cls: str = "positive") -> set[str]:
    return {f.rule for f in check_record(record, cls, SCHEMA)}


def test_plausible_record_passes() -> None:
    assert _rules(GOOD) == set()
    row = {"record_json": json.dumps(GOOD), "requested_class": "positive"}
    out = label_row(row, SCHEMA)
    assert out["agent_valid"] == "true" and out["agent_failure_type"] == "NONE"


def test_guide_counterexample_is_caught() -> None:
    bad = GOOD | {"sex": "X", "length": 0.30, "diameter": 0.45, "whole_weight": 0.20,
                  "shell_weight": 0.31}
    assert {"S4", "A1", "A3", "A4"} <= _rules(bad)


def test_target_missing_and_range() -> None:
    assert "S3" in _rules(GOOD, "negative")
    assert "S1" in _rules({k: v for k, v in GOOD.items() if k != "height"})
    too_long: dict[str, object] = {**GOOD, "length": 0.9, "diameter": 0.7}
    assert "S7" in _rules(too_long)
