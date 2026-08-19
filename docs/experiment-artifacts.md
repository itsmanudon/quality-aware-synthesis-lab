# Experiment artifacts

Future runs use `artifacts/runs/<run_id>/` with exactly these files:

- `manifest.json`
- `resolved_config.yaml`
- `candidates.jsonl`
- `evidence.jsonl`
- `assessments.jsonl`
- `decisions.jsonl`
- `events.jsonl`
- `metrics.json`

Every artifact records a schema version and belongs to a run manifest that records
configuration, seed, environment, and Git state.

Schema changes require an explicit migration and version bump. No hidden mutable state,
implicit prompts, or unrecorded repair decisions are permitted. M0.1 provides only the
storage primitives and contracts; it creates no runs automatically.
