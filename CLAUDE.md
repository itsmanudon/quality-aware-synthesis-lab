# CLAUDE.md

Guidance for AI assistants working in this repository.

## What this project is

**RC-QASyn** (package `rcqasyn`, repo `quality-aware-synthesis-lab`) is a research
codebase for *risk-calibrated, quality-aware synthetic tabular dataset construction*.
It studies how to make factual, logical, distributional, privacy, fairness, and
downstream-utility problems in LLM-generated records **visible and traceable**, instead
of collapsing them into one aggregate quality score.

This is a **research foundation, not a product and not a results claim**. The README,
`docs/research-plan.md`, and `docs/milestones.md` are deliberately worded to avoid
asserting novelty or performance. Preserve that tone in code comments, docstrings, and
docs you write.

Current implemented scope: all six engineering phases (the M1 harness, M2
evidence, M4/M5 descriptive fusion and admission, M7 construction and M6/M9 bounded
repair and utility), the Empirical v2 study and two exploratory addenda. See
`docs/REPOSITORY_GUIDE.md` for the map. Still out of scope: calibrated validity
probabilities, risk-aware control, RAG/factual verification, privacy/fairness
validators and human-label experiments. Do not implement those unless asked. The
sections below on M0/M1 describe the original harness and remain accurate for it.

Exploratory work goes in a new declared version under `addendum/` (outside the
protected historical paths `data/`, `configs/`, `artifacts/reports/`, `artifacts/runs/`,
`test-results/` and `prompts/`), never as a rerun of a declared version.

## Environment and setup

Python is pinned to **`>=3.12,<3.13`** (`pyproject.toml`). The system default here is
3.11; use `python3.12` explicitly.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

**Always work inside the activated venv.** `pyright` resolves imports from the active
interpreter, and a globally installed `ruff` may be a different version with different
default rules — both produce spurious errors when run outside `.venv`.

## Commands

```bash
# tests (158 cases after Phase 1; testpaths = tests/; collect to verify current count)
pytest -q
pytest tests/m1/test_harness.py -q          # one file

# lint + typecheck (both must be clean)
ruff check .
pyright

# audit trail: re-runs the three commands above and appends one record to
# test-results/history.jsonl (tracked; see test-results/README.md)
python scripts/record_test_run.py

# CLI (also available as `python -m rcqasyn`)
rcqasyn --help
rcqasyn doctor                               # config/papers/artifacts/git state
rcqasyn papers index                         # deterministic literature/paper_inventory.csv
rcqasyn datasets list
rcqasyn datasets inspect <dataset_id>        # schema/fingerprint/split, no records printed
rcqasyn datasets prepare <id> --seed 42      # manifests under data/manifests/<id>/
rcqasyn datasets record-acquisition <id> --source-url <url>
rcqasyn baselines replay --config configs/experiments/replay.yaml   # offline, no network
rcqasyn baselines run --config configs/experiments/pilot_p1/Ecoli4.yaml
rcqasyn baselines trtr <id> --seed 42        # real-train/real-test reference pilot
rcqasyn baselines compare <run_dir>...       # cross-dataset comparison JSON
rcqasyn baselines diagnose <run_dir>...      # read-only copying / TRAIN-support diagnostics

python experiments/m1_5_p1_reports.py        # M1.5 P1 report roll-up (needs completed runs)
```

`doctor` and `papers index` accept `--root` / `--config`; all `datasets`/`baselines`
commands accept `--root` for a temporary project root (used heavily by tests).

**The offline replay is the canonical smoke test** — it exercises the real generation →
validation → judge → metrics architecture with stored fixture responses and never makes
a network call. Run it after touching the runner.

## Repository layout

```
src/rcqasyn/
  contracts/     Pydantic v2 domain contracts (strict, extra=forbid, tz-aware)
  interfaces/    Protocol-only extension points for future milestones
  config/        base config loader (models.py/loader.py) + experiment config (experiment.py)
  datasets/      registry, KEEL/.dat + CSV loader, stratified split, TRAIN-only profile, acquisition
  generation/    prompt loading, provider adapters (replay + OpenAI-compatible), response parser
  baselines/     B2 deterministic validators, B3 single-LLM judge
  metrics/       intrinsic fidelity/diversity metrics; TRTR/TSTR utility metrics
  experiments/   runner.py (the M1 harness), analysis.py (exports/roll-ups), diagnostics.py
  storage/       atomic deterministic JSON + JSONL writers
  literature/    deterministic PDF inventory
  utils/         hashing, id generation, named seed derivation
  cli/app.py     Typer CLI (entry point `rcqasyn`)

configs/         base.yaml + datasets/ generators/ validators/ experiments/
prompts/         generation/{v1,v2}.txt, judge/v1.txt — versioned, hashed into artifacts
docs/            architecture, contracts, datasets, baselines, generation protocol,
                 experiment artifacts, human review, literature protocol, milestones, research plan
tests/           mirrors src layout; tests/m1/ covers the harness
experiments/     standalone report scripts (not importable package code)
scripts/         dev-tooling scripts (not importable package code); record_test_run.py
data/            raw/ processed/ manifests/ — contents gitignored except .gitkeep
artifacts/       run outputs — gitignored except .gitkeep
test-results/    tracked pytest/ruff/pyright audit log (history.jsonl) — NOT gitignored
literature/      papers/ (PDFs gitignored), notes/, paper_inventory.csv
AGENTS.md        commit-message rules — read before committing
RC_QASyn_Research_Implementation_Manifest.xlsx   source-of-truth research manifest
```

## Architecture

The full eventual pipeline (only the prefix is implemented):

```
Specification → Generation → Independent Validators → Evidence Fusion →
Risk-Aware Controller → Repair/Revalidate/Regenerate → Dataset Optimizer →
Audit → Downstream Utility
```

M1 implements: `Specification → Generation → Independent Validators →
Baseline Decisions → Audit Metrics → Downstream Utility`.

`experiments/runner.py::run_experiment` is the spine. Read it first when changing
anything about runs. Its order is load-bearing:

1. Resolve dataset spec → load → deterministic stratified split → TRAIN-only profile.
2. Load versioned generation + judge prompts (hashes recorded).
3. Build `GenerationPlan` (resolve class quotas: `preserve_reference` proportional, or
   `explicit`).
4. **Provider gate** (`_require_real_provider`) for non-replay runs: refuses to make any
   call until a real base URL, model, and populated API-key env var are configured.
   Loopback host + placeholder model is treated as unconfigured.
5. Construct both providers **before** reserving the run directory.
6. Write `manifest.json`, `resolved_config.yaml`, split/profile, `generation_plan.json`.
7. **Seed plan** (`_generation_seed_plan`): derive the per-batch provider seed for every
   `(dataset_id, requested_class, batch_index)` tuple and assert no collisions — raises
   *before* any provider call.
8. **Provider smoke call** (non-replay): one bounded call that must return `{"ok":true}`;
   failure marks the run failed and aborts before pilot generation.
9. Durably persist each raw provider response before parsing; build and then persist
   **one** parsed candidate pool.
10. Fork the *same* pool into B1, B2, B3 (strictly paired — never regenerate per branch).
11. Metrics, `comparison.json`, `human_review.csv`, `b2_b3_disagreements.csv`,
    `machine_failure_report.json`, manifest finalization.

### The three baselines (deliberately weak; keep them that way)

| | Policy |
| --- | --- |
| **B1** | Accept every parseable candidate. No quality filter at all. |
| **B2** | Independent deterministic validators (schema, categorical-domain, missing, target-condition, observed-range). Rejects configured severities (default HIGH/CRITICAL) or exact ordered duplicates. No learned score, no fusion, no repair, no regeneration. |
| **B3** | Exactly one LLM judge call per parseable candidate, static score threshold, PASS/WARN accept. No calibration, no ensemble, no rule+judge fusion, no factual-verification claim. Malformed output is traced and rejected. |

B1/B2/B3 are the research control conditions. **Do not "improve" them.** Making B2 or B3
smarter destroys the comparison the project exists to make.

## Non-negotiable invariants

These are enforced by tests and by design; violating them silently corrupts the research.

- **No test leakage.** Profiles, prompts, reference examples, filters, judges, model
  selection, and preprocessing fit use **TRAIN only**. Full profile artifacts retain
  TEST-inclusive lineage; fresh upstream inputs use `TrainingContext` instead. Legacy
  unsafe fresh protocols fail before provider contact. REAL TEST is supplied only to
  final utility evaluation. See `docs/phase1-stabilization.md` and the Phase-1 boundary tests.
- **Quality / risk / uncertainty / dataset-contribution stay separate typed fields.**
  Never collapse them into one score. See `docs/contracts.md`.
- **Scope is recorded with evidence.** FIELD / RECORD / SUBGROUP / DATASET measurements
  are never silently pooled or presumed comparable.
- **Determinism.** Seeds derive through `utils/seeds.py::derive_seed` (SHA-256), never
  Python's randomized `hash()`. Ordering uses SHA-256 sort keys, JSON is written with
  `sort_keys=True`. The three reproducibility concepts — random IDs, content IDs, and
  named seed derivation — are distinct; keep them distinct.
- **Per-batch provider seeds.** One static seed reused across batches caused a 75%
  duplicate artifact in P0-v2 (it was determinism, not model collapse). Generation seeds
  must come from `generation_provider_seed(root_seed, dataset_id, target_class,
  batch_index, base_seed)`. `tests/m1/test_generation_seed_confound.py` locks this in.
- **Raw before parsed.** Raw provider responses are persisted before parsing and retained
  on every candidate and failure event. Candidates are never clipped, imputed,
  category-corrected, rewritten, or regenerated by the pipeline.
- **Missing accounting is `null`, never `0`.** Token/latency/cost aggregates stay `None`
  when any role has incomplete accounting. Do not "helpfully" default them.
- **No significance claims.** `comparison.json` carries `no_significance_claim: true`.
  Reports state counts and rates, not conclusions.
- **Exact-match ≠ privacy.** `exact_train_match`, `exact_reference_match`, and
  `exact_nonreference_train_match` are *copying diagnostics*. Never describe them as a
  privacy result. TRAIN-support nearest-neighbour distances are exploratory only — no
  threshold, not a validity probability.
- **Observed numeric ranges are descriptive support, not constraints.** The observed-range
  validator emits WARN by default and only rejects if its severity is explicitly selected.
- **Secrets never reach artifacts.** Endpoints are sanitized (`_sanitized_endpoint` strips
  userinfo, query, and fragment); API keys are read from a configured env var name and
  never written.
- **No downloaders, no mirrors, no guessed URLs.** KEEL files are placed by hand at the
  path `rcqasyn datasets inspect <id>` reports; the registry records source URL and
  SHA-256 and refuses to guess.
- **The coding agent never fills a human-review column** and never infers a human
  validity label from a B2/B3 decision. See `docs/human-review.md`.
- **Historical artifacts are immutable.** Active execution-owned manifests/evidence may
  transition until `FINALIZED.json` seals the bundle. Foreign runs and existing reports
  cannot be replaced by workflow overwrite flags. `create_run_dir` reserves exclusively.
  Generic unsealed nonhistorical JSON replacement remains explicit. Schema changes require
  an explicit migration and a `schema_version` bump.

## Code conventions

- `from __future__ import annotations` at the top of modules; PEP 604/585 types
  (`X | None`, `tuple[str, ...]`), `type` aliases where used in `contracts/_base.py`.
- All domain models subclass `ContractModel` (`strict=True`, `extra="forbid"`,
  `validate_assignment=True`, `use_enum_values=True`). Timestamps must be timezone-aware.
- Prefer immutable containers on contracts (`tuple[...]` over `list[...]`).
- Enums are `StrEnum` in `contracts/enums.py`.
- Line length 100, ruff `target-version = "py312"`. Pyright `standard` mode over `src`.
- Narrow `# pyright: ...` file-level suppressions already exist on pandas/numpy/sklearn-heavy
  modules (`metrics/`, `datasets/loader.py`, `datasets/profile.py`, `datasets/split.py`,
  `experiments/runner.py`, `experiments/diagnostics.py`). Match the existing style rather
  than adding broad new suppressions.
- Interfaces stay Protocol-only; test doubles live in `tests/`, never in `src/`.
- Comments explain *why* (a research decision, a confound, a provider quirk), not *what*.
  The existing comments are a good model.

## Common tasks

**Add a dataset:** create `configs/datasets/<id>.yaml` (see `ecoli4.yaml`). Every feature
must be declared exactly once as categorical or numerical, and the target must not appear
in `feature_columns` — `DatasetDefinition` validates this. Then place the verified raw
file, `rcqasyn datasets record-acquisition <id>`, `rcqasyn datasets prepare <id>`.

**Add an experiment:** copy an existing `configs/experiments/**/*.yaml`. `run_id` must be
unique — a run directory that already exists is a hard error, by design. Config families:
`replay*.yaml` (offline fixture runs), `dev_*_b1_b3.yaml` (small editable examples with
`local-model` / `RCQASYN_API_KEY` placeholders that the provider gate rejects until
replaced), and the pilot generations `pilot/` (P0, prompt v1, 40 records) → `pilot_v2/`
(prompt/transport v2, `json_object`, longer timeouts) → `pilot_v3/` (same as v2 apart
from name and `run_id`; the controlled post-seed-fix repeat) → `pilot_p1/` (same as v3
with 40 → 200 records, quotas 20 → 100).

**Change a prompt:** add a new versioned file under `prompts/<kind>/` rather than editing
one in place — prompt version and SHA-256 are recorded in every plan and trace, so editing
breaks the provenance of past runs. Note `.format()` is used for rendering, so literal
braces in template text must be doubled (`{{...}}`), as in `prompts/generation/v2.txt`.

**Add a B2 validator:** subclass `_BaseValidator` in `baselines/validators.py`, wire it
into `ValidatorSuite.validate`, and be explicit about verdict *and* severity — severity is
what determines rejection, and the default reject set is HIGH/CRITICAL.

**Add analysis:** put read-only measurement in `experiments/diagnostics.py`. Diagnostics
must never read, change, or re-run a B1/B2/B3 acceptance decision.

## Git workflow

Read `AGENTS.md` before committing — it is the authority. In short: Conventional Commits
header (`<type>(<scope>): <imperative summary>`, no trailing period, no vague subjects),
a detailed body for non-trivial commits explaining what and why, and validation recorded
in the body or a `Tests:`/`Verification:` footer. Keep commit scope intentional; do not
sweep unrelated working-tree changes into a commit without explicit authorization.

Run `pytest -q`, `ruff check .`, and `pyright` (inside the venv) before committing.
For non-trivial changes, also run `python scripts/record_test_run.py` — it appends a
JSON record of that verification run to the tracked `test-results/history.jsonl` audit
log — and commit the updated `test-results/history.jsonl` alongside the change.

## Gotchas

- Running the CLI outside the venv fails with `ModuleNotFoundError: rcqasyn`.
- Re-running a config with the same `run_id` fails with `FileExistsError`. Change the
  `run_id` for a new execution; preserve the historical directory.
- `data/*` and `artifacts/*` contents are gitignored (`.gitkeep` files are tracked). Local
  run output and KEEL raw files never get committed — do not try to force them in.
- `test-results/history.jsonl` is the one exception to that pattern: it is a tracked,
  append-only pytest/ruff/pyright audit log (`test-results/README.md`), deliberately not
  gitignored. Append to it, never rewrite or truncate existing lines.
- `literature/papers/*.pdf` is gitignored for licensing and repo-size reasons; only
  `paper_inventory.csv` and the notes are tracked.
- Judge and generation provider traces live in different files: successful generation
  calls in the run root `provider_calls.jsonl`, judge calls in
  `baselines/b3/provider_calls.jsonl`. They are not duplicated.
- `pandas` is pinned `<3` deliberately (3.x dtype/copy semantics regress `pyright` on
  unchanged source). Don't lift the cap casually.
