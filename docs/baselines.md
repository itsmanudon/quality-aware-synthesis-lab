# Paired baselines

The runner resolves every explicit or TRAIN-proportional quota into deterministic
class-specific batches (each call has one requested class and count), generates/replays
one raw pool, and forks the same candidate IDs into all
three baselines. B1 is intentionally weak: every parseable candidate is accepted with
no quality filter. B2 runs Schema, categorical-domain, missing-value, target-condition,
and observed-range validators. It rejects only configured severities (HIGH/CRITICAL by
default); observed ranges are WARN diagnostics by default. B2 performs no learned score,
fusion, repair, revalidation, or regeneration. B3 calls exactly one LLM judge per
parseable candidate, parses a narrow structural/cross-field/profile rubric, and accepts
only a static configured score threshold and PASS/WARN verdict. B3 has no calibration,
ensemble, rule+judge evidence fusion, or factual-verification claim; self-confidence
is explicitly uncalibrated. Malformed judge output is traced and rejected by default.

Each run writes `artifacts/runs/<run_id>/manifest.json`, `resolved_config.yaml`,
`generation_plan.json`,
`dataset/{profile.json,split_manifest.json}`, `provider_calls.jsonl`,
`generation_failures.jsonl`, `candidates_raw.jsonl`, per-baseline candidates/metrics/
classifier metrics, B2 evidence/decisions, B3 judge results/failures/decisions, and
`comparison.json`. Comparison output reports counts, acceptance rates, duplicate rates,
intrinsic fidelity/diversity/utility, tokens, calls, latency, nullable cost, and failure
aggregation. It makes no significance claim.

Intrinsic metrics include numeric KS/Wasserstein, categorical TVD/JSD, correlation error,
exact duplicates, entropy, variance ratios, and class-conditional views. TRTR and TSTR
use mixed-type sklearn pipelines fit only on their respective training data and score
the untouched REAL TEST split with F1, average precision, MCC, balanced accuracy, and
AUROC where defined. Empty or degenerate values are reported as null with a status.
Alpha/beta precision/recall, embeddings, privacy/fairness validation, calibration,
RAG, and adaptive controllers are future work.

`configs/experiments/dev_page_blocks0_b1_b3.yaml`, `dev_ecoli4_b1_b3.yaml`, and
`dev_abalone19_b1_b3.yaml` are editable OpenAI-compatible examples. They use a loopback
base URL and require a locally configured model/key; they do not make calls until the
user supplies a local provider and places the corresponding KEEL file.
