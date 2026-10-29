# Exploratory addendum v1

**Exploratory addendum, declared after the main study.** Nothing here is part of the
canonical empirical-v2 tables, protocol-v1, run-v2/report-v3 or the approved manuscript.

| Path | Contents |
| --- | --- |
| `addendum-v1.json` | All settings, committed before any score (`ce4d7fc`, then at `configs/empirical/addendum-v1.json`) |
| `configs/datasets/`, `data/manifests/` | Six new KEEL dataset configs and manifests (yeast3, yeast4, vehicle0, segment0, ecoli1, abalone9-18) |
| `data/raw/` | Local KEEL archives and `.dat` files (gitignored); winequality-red-4 archive is empty |
| `docs/datasets.md` | Byte copy required by the canonical specification builder |
| `report/` | The single execution: `summary.md`, `slide-numbers.md`, `summary.json`, `results.csv`, `manifest.json` and supporting JSON |
| `RELOCATION.json` | Byte-identity record of the move out of protected paths and the local evidence archive |

This directory is a self-contained project root. It sits outside the protected historical
paths (`data/`, `configs/`, `artifacts/reports/`, `artifacts/runs/`, `test-results/`,
`prompts/`), so a checkout of `main` can still serve as historical SOURCE.

Reproduce (Python 3.12 venv, pinned versions in `artifacts/reports/empirical-v2/verification-v1/dependencies.txt`):

```bash
git worktree add --detach <src> 244a9bfd490a03a35c4be5cb3b83354e425795fc
PYTHONPATH=src python scripts/restore_source_bytes.py --target <src> --raw-from .
PYTHONPATH=src python scripts/run_exploratory_addendum.py --source-root <src> --output <fresh dir>
PYTHONPATH=src python scripts/report_exploratory_addendum.py --run <fresh dir> --output <fresh dir> --conclusion <text>
```

`restore_source_bytes.py` writes recorded Windows-serialized bytes into the separate
worktree only when they match the recorded SHA-256. Outputs refuse to overwrite.
