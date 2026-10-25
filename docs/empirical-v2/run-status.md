# Run versions

- run-v1: retained development execution. Prediction/metric rows replay all 138
  historical rows, but bootstrap output used a colliding metadata key that replaced
  compared method names with the interval method. Not a manuscript source.
- run-v2: canonical study after separating interval_method from compared method.
- replay-v1: fresh deterministic replay of the canonical implementation.

No experimental configuration or observed score was selected in response to results.
The protocol commit predates all runs. Output versions are never overwritten.
