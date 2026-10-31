# Phase 0 baseline: environment, tests, lint, types

Recorded 2026-10-31 on branch `study-v3` at `90b9b3d` (clean checkout before any Study v3
code), Windows 11, Python 3.12.11 (uv-managed venv), `uv pip install -e '.[dev,research]'`.

| Check | Command | Result |
| --- | --- | --- |
| Tests | `python -m pytest -q` (testpaths = `tests/`) | 1823 passed, 14 warnings, 0 failed (415 s) |
| Types | `pyright` (include = `src`) | 0 errors, 0 warnings |
| Lint | `ruff check .` (ruff 0.16.5) | 4 errors, all pre-existing in a protected path |

Baseline failure set (ruff), unchanged by Study v3 and not edited because
`artifacts/reports/` is a protected historical path:

- `artifacts/reports/phase2/agent-labels-v1/blinded-answers/annotation-procedure.py`: I001, F401 (`digest`)
- `artifacts/reports/phase2/agent-labels-v1/verification/verify-package.py`: I001, F401 (`verify_envelope`)

Notes:

- CLAUDE.md quotes "158 cases after Phase 1"; the suite now collects 1823 (later phases added tests).
- `scripts/record_test_run.py` was not run: it appends to `test-results/history.jsonl`, a protected
  path. Study v3 records its checks here and in commit footers instead.
- Study v3 tests live in `study/v3/tests/` (outside `testpaths`); run them with
  `python -m pytest study/v3/tests` and type-check with
  `pyright --pythonpath .venv/Scripts/python.exe study/v3` (without `--pythonpath`, pyright
  did not resolve the venv's `anthropic`/`openai` packages for files outside `src`).
