# Contract philosophy

Quality asks whether a specified property is satisfied. Risk asks about the expected
consequence of accepting a candidate or dataset under uncertainty. Uncertainty records
how much confidence or disagreement surrounds an assessment. Dataset contribution is a
marginal question about coverage, redundancy, and utility. These are separate typed
fields and must not be collapsed into one score.

Every candidate, evidence item, assessment, decision, and run carries explicit IDs and
versions. The intended lifecycle chain is:

`run → request → candidate(version) → evidence(validator/version) → assessment → decision → artifact`

Provenance is additive: a record can cite a paper, dataset, user reference, or other
source without assuming a web URL. Evidence is immutable after creation. JSON contracts
are strict, timezone-aware, and round-trip serializable.

## Illustrative future lifecycle trace

The following is an illustrative trace shape, not an M0.1 aggregate runtime or result:

```json
{
  "dataset": {"dataset_id": "credit-control", "version": "1"},
  "generator": {"generator_id": "future-generator", "version": "1"},
  "model": {"model_id": "future-model", "version": "1"},
  "prompt": {"prompt_version": "prompt-1"},
  "seed": 42,
  "validators": [{"validator_id": "rules", "version": "1"}],
  "evidence": [{"evidence_id": "e-1", "dimension": "schema_validity"}],
  "assessment": {"assessment_id": "a-1", "quality_scores": {}, "risk_scores": {}},
  "action": {"decision_id": "d-1", "action": "repair"},
  "repair": {"parent_record_id": "record-1", "new_record_version": 2},
  "final_status": "accepted",
  "token_usage": {"input": 0, "output": 0},
  "latency_ms": 0,
  "cost_usd": 0.0
}
```

Future implementations must preserve these trace concepts without hiding parentage,
validator evidence, action, token usage, latency, or cost.
