"""Run the standard verification commands and append one audit record.

Runs ``pytest`` (via a temporary JUnit XML report), ``ruff check .``, and
``pyright`` exactly as documented in CLAUDE.md, then appends one deterministic
JSON line to ``test-results/history.jsonl`` recording pass/fail counts, tool
exit codes, and the git/Python state the run happened under. This is a repo
audit trail, not a research artifact: no test names, tracebacks, or source
text are recorded, only counts and status.

Usage:
    python scripts/record_test_run.py

Must be run with the project venv active (see CLAUDE.md "Environment and
setup") so pytest/ruff/pyright resolve to the pinned dev dependencies.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = ROOT / "test-results" / "history.jsonl"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=False)


def _git(*args: str) -> str | None:
    result = _run(["git", *args])
    return result.stdout.strip() if result.returncode == 0 else None


def _pytest_summary() -> dict[str, object]:
    with tempfile.TemporaryDirectory() as tmp:
        junit_path = Path(tmp) / "junit.xml"
        result = _run([sys.executable, "-m", "pytest", "-q", f"--junit-xml={junit_path}"])
        summary: dict[str, object] = {"exit_code": result.returncode}
        if not junit_path.is_file():
            summary["status"] = "no_report"
            return summary
        root = ET.parse(junit_path).getroot()
        suite = root if root.tag == "testsuite" else root.find("testsuite")
        if suite is None:
            summary["status"] = "unparsed_report"
            return summary
        tests = int(suite.get("tests", 0))
        failures = int(suite.get("failures", 0))
        errors = int(suite.get("errors", 0))
        skipped = int(suite.get("skipped", 0))
        summary.update({
            "status": "ok",
            "collected": tests,
            "passed": tests - failures - errors - skipped,
            "failed": failures,
            "errors": errors,
            "skipped": skipped,
            "duration_seconds": float(suite.get("time", 0.0)),
        })
        return summary


_PYRIGHT_SUMMARY_RE = re.compile(
    r"(\d+) errors?, (\d+) warnings?, (\d+) informations?"
)


def _ruff_status() -> dict[str, object]:
    result = _run([sys.executable, "-m", "ruff", "check", "."])
    return {"exit_code": result.returncode, "status": "ok" if result.returncode == 0 else "errors"}


def _pyright_status() -> dict[str, object]:
    result = _run([sys.executable, "-m", "pyright"])
    match = _PYRIGHT_SUMMARY_RE.search(result.stdout) or _PYRIGHT_SUMMARY_RE.search(result.stderr)
    if match is None:
        return {"exit_code": result.returncode, "status": "unparsed"}
    errors, warnings, informations = (int(value) for value in match.groups())
    return {
        "exit_code": result.returncode,
        "status": "ok" if errors == 0 else "errors",
        "errors": errors,
        "warnings": warnings,
        "informations": informations,
    }


def main() -> int:
    pytest_summary = _pytest_summary()
    ruff_summary = _ruff_status()
    pyright_summary = _pyright_status()
    record = {
        "schema_version": "test-results-v1",
        "recorded_at": datetime.now(UTC).isoformat(),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "python_version": sys.version.split()[0],
        "pytest": pytest_summary,
        "ruff": ruff_summary,
        "pyright": pyright_summary,
    }
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_PATH.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        stream.write("\n")
    ok = pytest_summary.get("status") == "ok" and pytest_summary.get("failed") == 0 and pytest_summary.get("errors") == 0
    ok = ok and ruff_summary.get("exit_code") == 0 and pyright_summary.get("errors", 1) == 0
    print(f"Appended record to {HISTORY_PATH.relative_to(ROOT)}")
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
