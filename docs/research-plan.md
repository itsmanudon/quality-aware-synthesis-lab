# Research plan

RC-QASyn is a proposed research program, not a claim of results. The primary proposed
contributions are: (1) calibrated heterogeneous evidence fusion; (2) risk-calibrated
control; (3) dependency-aware localized repair; and (4) marginal coverage optimization.
Failure memory and cost-aware routing remain optional extensions until the core works.

Planned development datasets are `page-blocks0`, `Ecoli4`, and `Abalone19`. The core
planned set and intended roles are hypotheses for experiment design, not claims about
results or dataset statistics:

| Dataset | Planned role |
| --- | --- |
| Default Credit Card | mild imbalance/control |
| HTRU2 | real-world moderate imbalance |
| Ecoli4 | small-data scarcity |
| Musk | high dimensionality |
| Mammography | severe imbalance |
| Bank Marketing | mixed categorical/numerical |
| Abalone19 | extreme imbalance |

APS and Satimage-2 are optional planned datasets. No dataset is downloaded or evaluated
in M0.1.

## Planned baselines (future work; not implemented in M0.1)

- **B1 Raw LLM generation:** Generate → Dataset.
- **B2 Rule filtering:** Generate → Deterministic rules → Accept/Reject.
- **B3 Single LLM Judge:** Generate → LLM critic → Static threshold.
- **B4 Multi-layer validation + complete regeneration:** Generate → Validate → Full
  regeneration on failure.
- **B5 Proposed system:** Generate → Heterogeneous validators → Calibrated evidence
  fusion → Risk-aware action selection → Localized repair → Dataset-level optimization.

Comparisons will be defined with fixed splits, cost accounting, and uncertainty intervals
before results are reported.
