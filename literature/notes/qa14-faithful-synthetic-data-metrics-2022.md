# Literature note

- Source PDF: `literature/papers/qa14-faithful-synthetic-data-metrics-2022.pdf`
- Verified bibliography: Ahmed M. Alaa, Boris van Breugel, Evgeny Saveliev, and Mihaela van der Schaar. “How Faithful is your Synthetic Data? Sample-level Metrics for Evaluating and Auditing Generative Models.” Proceedings of the 39th International Conference on Machine Learning, PMLR 162, 2022. Primary: https://proceedings.mlr.press/v162/alaa22a.html (PDF: https://proceedings.mlr.press/v162/alaa22a/alaa22a.pdf).
- Central idea: α-Precision, β-Recall, and Authenticity separate fidelity, diversity, and generalization/copying, and can support sample-level auditing. The authors motivate multidimensional reporting because likelihood/divergence alone can hide distinct failure modes (abstract and pp. 1–3).
- Datasets / metrics: experiments include SIVEP-GRIPE tabular data, MNIST, and AmsterdamUMCdb; tabular experiments compare coverage and the proposed integrated α-precision, β-recall, and authenticity (pp. 10–12).
- Limitations: the method estimates supports with learned models and tuning (including k-NN/support parameters); it is not a lightweight intrinsic metric for this milestone, and the paper's neural support approach does not directly define mixed-type tabular semantics (pp. 9–12, appendix).
- Pipeline stage: dataset-level fidelity/diversity/authenticity audit.
- M1 relevance: report separate, transparent numeric KS/Wasserstein, categorical TVD/JSD, correlations, diversity, exact duplicates, and utility; represent empty/degenerate cases as null/status. Defer α/β metrics and embeddings while preserving the conceptual separation.
- Useful pages / figures: Fig. 1 (p. 1) three qualities; metric definitions pp. 2–5; tabular results Table 3 (pp. 10–11); outlier/mode-resolution toy studies Figs. 7–8 (pp. 12–13).
- Baseline implication: duplicate rate and diversity must not be conflated with fidelity; a single judge score cannot substitute for intrinsic metrics. No scientific claim should be inferred from the small replay fixture.
- What this changes in our repo: `metrics` returns named components with statuses and class-conditional views where meaningful, while α/β/authenticity remain documented future work.
