# M1.1 real pilot configurations

These files are deliberately bounded P0 runs. Each requests one shared raw pool
of 40 records (20 per authoritative class), in batches of five, with two
deterministic TRAIN-only reference examples per class, and then forks that pool
into B1/B2/B3. The generator and judge are configured as the same
OpenAI-compatible deployment shape across datasets. The loopback values are
placeholders: the runner stops at its provider gate until the user supplies a
reachable endpoint, model names, and `RCQASYN_API_KEY`.

Run one dataset at a time, after acquisition and preparation:

```bash
rcqasyn baselines run --config configs/experiments/pilot/page-blocks0.yaml
```

The default B2 policy is deterministic HIGH/CRITICAL rejection with observed
ranges retained as diagnostics, and B3 uses one static threshold of `0.7`.
