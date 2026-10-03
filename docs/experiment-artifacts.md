# Experiment artifacts

M1 runs use `artifacts/runs/<run_id>/` with these core files:

- `manifest.json` (v2 lifecycle and component outcome)
- `scientific_specification.json`
- `calls/<role>-<ordinal>.json` (durable response/failed-attempt evidence before parsing)
- `FINALIZED.json` (last-written bundle hash seal)
- `resolved_config.yaml`
- `generation_plan.json`
- `generation_seed_plan.json` - the deterministic unique per-batch provider seed for
  every `(dataset_id, requested_class, batch_index)` tuple, resolved and asserted
  collision-free before any provider call (M1.4 seed-confound guard).
- `dataset/profile.json` and `dataset/split_manifest.json`
- root `provider_calls.jsonl` contains successful generation-call traces; generation
  failures are in root `generation_failures.jsonl`. Successful judge-call traces live
  under `baselines/b3/provider_calls.jsonl` and judge failures under
  `baselines/b3/judge_failures.jsonl`; these role-specific files are not duplicated in
  the root file.
- `candidates_raw.jsonl`
- `baselines/{b1,b2,b3}/` candidate, decision, evidence/judge, and metric artifacts
- `comparison.json`
- `human_review.csv` and `b2_b3_disagreements.csv`

Diagnostic-only artifacts in new `artifacts/derived/<source-purpose-execution>/` directories (written by `rcqasyn baselines diagnose`; they never read,
change, or re-run a B1/B2/B3 decision):

- `copying_diagnostics.json` - per raw candidate, three independent booleans:
  `exact_synthetic_duplicate`, `exact_reference_match` (equals a TRAIN reference example
  shown in the prompt), `exact_nonreference_train_match` (equals a TRAIN row not shown).
  Copying diagnostics only; not a privacy claim.
- `support_diagnostics.jsonl` + `support_summary.json` - learning-free nearest-neighbour
  distance from each candidate to the REAL TRAIN split after TRAIN-only standardisation
  (numeric z-score; categoricals one-hot with unit weight). Exploratory only: no
  threshold, no acceptance effect, not a validity probability.

Versioned manifests/results record configuration, seed routes, environment and Git state.
CSV/JSONL rows and some scalar metadata do not each carry a schema version. A v2
finalized bundle is immutable to package writers; only its owning active execution
can transition lifecycle files or append active evidence.

`comparison.json` reports attempted and successful calls separately, plus role-specific
tokens, latency, and nullable costs. The aggregate token/latency/cost fields remain
unknown when either role has unknown accounting rather than treating missing usage as
zero.

New result contracts use explicit versions; legacy bundles remain read-only and do not require migration. No hidden mutable state,
implicit prompts, or unrecorded decisions are permitted. The resolved configuration,
prompt hashes, provider traces, parser failures, baseline policies, and a no-test-leakage
marker are retained. Replay creates no network/API calls, and the M0.1 storage
primitives remain backward-compatible.

See [Phase 1 stabilization](phase1-stabilization.md) for lifecycle versus success,
source-bound diagnostics, unsafe legacy fresh-run rejection and legacy reader compatibility.
