"""Contract tests for the standalone M1.5 P1 report roll-up."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType


def _load_report_script() -> ModuleType:
    path = Path("experiments/m1_5_p1_reports.py")
    spec = importlib.util.spec_from_file_location("m1_5_p1_reports", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_disagreement_summary_uses_stable_plural_filename(tmp_path: Path) -> None:
    """Catch regressions to the obsolete singular artifact name."""

    reports = _load_report_script()
    reports.OUT = tmp_path

    reports.write_disagreement_summary({"rows": 3})

    output = tmp_path / "p1_b2_b3_disagreements_summary.json"
    assert json.loads(output.read_text(encoding="utf-8")) == {"rows": 3}
    assert not (tmp_path / "p1_b2_b3_disagreement_summary.json").exists()
