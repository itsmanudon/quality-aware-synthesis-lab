# Literature note

- Source PDF: `literature/papers/qa01-llm-synthetic-data-survey-2024.pdf`
- Verified bibliography: Lin Long, Rui Wang, Ruixuan Xiao, Junbo Zhao, Xiao Ding, Gang Chen, and Haobo Wang. “On LLMs-Driven Synthetic Data Generation, Curation, and Evaluation: A Survey.” Findings of ACL 2024, pp. 11065–11082, Aug. 2024. Primary: https://aclanthology.org/2024.findings-acl.658/ (PDF: https://aclanthology.org/2024.findings-acl.658.pdf).
- Central idea: the survey organizes LLM synthetic-data work into a generic generation–curation–evaluation workflow and identifies missing unified, methodical evaluation. It distinguishes faithfulness (logical/grammatical coherence and factual/label correctness) from diversity and discusses prompt/task specification, conditions, demonstrations, filtering, and direct/indirect evaluation (pp. 11065–11068, 11071–11072).
- Datasets / metrics: the paper surveys text, instruction, math, code, and annotation datasets rather than introducing one benchmark. It discusses heuristic metrics, model-assisted evaluation, human evaluation, and downstream benchmark evaluation; no single surveyed metric is treated as sufficient.
- Limitations: it mainly covers text and LLM-driven approaches, not a complete tabular treatment (p. 11073); the survey itself is a field map, not a controlled performance experiment.
- Pipeline stage: generation, curation, evaluation.
- M1 relevance: keep generation, parsing, deterministic curation, judge evaluation, and downstream evaluation as separately traceable stages. Version prompts and retain train-only demonstrations; report structural validity, distributional fidelity, diversity, and utility rather than a single quality score.
- Useful pages / figures: Fig. 1 (p. 11065) ecosystem; Fig. 2 / p. 11067 workflow taxonomy; Fig. 4 (p. 11070) curation; Fig. 5 (p. 11071) direct vs indirect evaluation; conclusion and limitations (pp. 11073–11074).
- Baseline implication: compare generators and curation policies under identical task, seed data, prompts, and evaluation splits; record parse/filter failures instead of silently repairing them.
- What this changes in our repo: M1 uses explicit generation → raw pool → B1/B2/B3 → metrics/artifacts, with versioned prompt files, train-only profile/examples, and no hidden fusion or repair.
