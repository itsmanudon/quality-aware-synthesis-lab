# Test results history

`history.jsonl` is an append-only, tracked audit log of verification runs (`pytest`,
`ruff check .`, `pyright`) against this repository. Unlike `artifacts/` and `data/`, this
directory is **not** gitignored — every entry is committed so the pass/fail history
survives across sessions and machines for future audits.

Each line is one deterministic JSON record (`schema_version: "test-results-v1"`)
written by `scripts/record_test_run.py`:

```json
{
  "schema_version": "test-results-v1",
  "recorded_at": "2026-08-31T04:57:31.249944+00:00",
  "git_commit": "482a30400c11c18a9976273f95e82cdaa0d9b7ed",
  "git_branch": "claude/claude-md-docs-q6u4x2",
  "git_dirty": true,
  "python_version": "3.12.3",
  "pytest": {"status": "ok", "collected": 67, "passed": 67, "failed": 0, "errors": 0, "skipped": 0, "duration_seconds": 20.191, "exit_code": 0},
  "ruff": {"status": "ok", "exit_code": 0},
  "pyright": {"status": "ok", "errors": 0, "warnings": 0, "informations": 0, "exit_code": 0}
}
```

Only counts, statuses, and exit codes are recorded — no test names, tracebacks, diffs,
or source text. This keeps the log small, diffable, and free of anything that would go
stale or leak implementation detail as the codebase changes.

## Recording a run

```bash
source .venv/bin/activate
python scripts/record_test_run.py
```

This re-runs `pytest -q`, `ruff check .`, and `pyright` (the same three commands
documented in `CLAUDE.md`) and appends one line to `history.jsonl`. It exits non-zero if
any of the three failed, so it can gate a commit the same way running them manually
would. Run it (or the three commands plus a manual append) before committing
non-trivial changes, and note the result in the commit body per `AGENTS.md`.

`git_dirty` reflects the working tree at the moment the record was written — a `true`
value on an otherwise-passing run usually just means new/modified files were staged or
present but not yet committed (including `history.jsonl` itself, on a run's first commit).
