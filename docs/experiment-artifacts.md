# Experiment artifacts

M1 runs use `artifacts/runs/<run_id>/` with these core files:

- `manifest.json`
- `resolved_config.yaml`
- `generation_plan.json`
- `dataset/profile.json` and `dataset/split_manifest.json`
- root `provider_calls.jsonl` contains successful generation-call traces; generation
  failures are in root `generation_failures.jsonl`. Successful judge-call traces live
  under `baselines/b3/provider_calls.jsonl` and judge failures under
  `baselines/b3/judge_failures.jsonl`; these role-specific files are not duplicated in
  the root file.
- `candidates_raw.jsonl`
- `baselines/{b1,b2,b3}/` candidate, decision, evidence/judge, and metric artifacts
- `comparison.json`

Every artifact records a schema version and belongs to a run manifest that records
configuration, seed, environment, and Git state.

`comparison.json` reports attempted and successful calls separately, plus role-specific
tokens, latency, and nullable costs. The aggregate token/latency/cost fields remain
unknown when either role has unknown accounting rather than treating missing usage as
zero.

Schema changes require an explicit migration and version bump. No hidden mutable state,
implicit prompts, or unrecorded decisions are permitted. The resolved configuration,
prompt hashes, provider traces, parser failures, baseline policies, and a no-test-leakage
marker are retained. Replay creates no network/API calls, and the M0.1 storage
primitives remain backward-compatible.
