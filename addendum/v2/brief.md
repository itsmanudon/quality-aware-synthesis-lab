# RC-QASyn: published-method benchmark (addendum v2, brief for Claude Code)

Run this only after the `exploratory-addendum-v1` work is finished and committed. Stay on the same branch. All integrity rules from that brief still apply:
- declare settings first;
- run once;
- report every row;
- label results exploratory;
- do not edit canonical runs or protocol-v1;
- do not push without asking.

## Goal
Benchmark quality-coverage against published methods by running them inside our own pipeline: same 10 datasets, same splits, same classifiers, same metrics. Copying numbers out of other papers is not valid here, because their splits, classifiers and protocols differ.

## Step 1: declare `configs/empirical/addendum-v2.json` and commit it before any scoring
Datasets and settings:
- All 10 datasets: the 3 canonical ones plus the 7 from addendum-v1.
- Fresh-split design (Track B): split seeds 13, 29, 43, 61, 79; classifier seed 42; logistic regression and random forest.
- Same budgets b and the same 4b minority-only pools as addendum-v1. For the canonical 3, use the protocol-v1 pools rebuilt deterministically.
- Same metrics: F1, AP, balanced accuracy, MCC, AUROC.

### A. Published oversamplers, used as training comparators on real TRAIN
Use imbalanced-learn 0.14.2 (already a dependency) with `random_state=42` and `k_neighbors=5`, or `min(5, n_minority-1)` when there are too few minority rows. Methods:
- SMOTE-ENN (Batista et al. 2004)
- SMOTE-Tomek (Batista et al. 2004)
- Borderline-SMOTE (Han et al. 2005)
- ADASYN (He et al. 2008)

Run each in two settings:
- default full balancing;
- a "+b" setting that adds b minority rows, as the existing SMOTE+b does. SMOTE-ENN and SMOTE-Tomek also remove rows, so report the actual final training class counts.

For nominal features, use the SMOTENC path when the method supports it. Otherwise mark the case unavailable with its reason.

### B. Published curation principles, re-implemented as curators on the same 4b pool at budget b
Label both as "re-implementation of the principle, not the authors' code".

1. **CLLM-style learning-dynamics filter (Seedat et al., ICML 2024).**
   - Fit sklearn `GradientBoostingClassifier` (100 estimators, seed 42) on real TRAIN only.
   - Take `staged_predict_proba` at estimators 10, 20, ..., 100 as checkpoints.
   - For each candidate, compute the per-checkpoint probability p of its assigned class, then:
     - confidence = mean over checkpoints of p;
     - aleatoric uncertainty = mean over checkpoints of p(1−p).
   - Keep candidates with aleatoric uncertainty at or below the pool median.
   - Rank them by confidence, descending, and take the top b.
   - If fewer than b remain, fill from the rest by confidence and record how many were filled.
2. **Discriminator-realism filter.** This follows the realism component of RUBRIC (Yu et al. 2026) and sample-level auditing (Alaa et al., ICML 2022).
   - Fit a random forest (200 trees, seed 42) to separate the real TRAIN minority rows (label 1) from the pool (label 0), using 5-fold out-of-fold probabilities.
   - Take the b pool rows with the highest "looks real" probability.

Compare these against the existing six curators. Quality-coverage, admitted random and farthest-first are the key ones.

## Step 2: run and report
- Outputs go to `artifacts/reports/exploratory-addendum-v2/`: `manifest.json`, `results.csv` (run-v2 schema) and `summary.json`.
- Per dataset and classifier, report the mean ± SD over 5 splits of:
  - quality-coverage minus each new method, for F1 and AP;
  - win/tie/loss counts.
- Across the 10 datasets, report:
  - the average rank of every method by mean F1, and separately by AP;
  - a Friedman test plus a Wilcoxon signed-rank test of quality-coverage against each method. Label these exploratory, with no multiplicity claim.
- Sanity check against the literature. This is context only, not a comparison. Report our real-only and SMOTE AUROC for ecoli4, page-blocks0 and abalone19 beside the values in Newaz & Haq (arXiv 2208.09619): ROC-AUC for unsampled / SMOTE of 85.0 / 89.4 on ecoli4, 90.8 / 92.7 on page-blocks0 and 50.0 / 50.0 on abalone19, all under a different protocol. Say whether our baselines behave similarly.

## Step 3: tables for the paper draft (numbers only, no prose)
- Use a script, not hand-typing, to generate booktabs LaTeX tables from `results.csv`.
- Put them in `artifacts/reports/exploratory-addendum-v2/tables/`:
  - `benchmark-curators.tex`: mean F1 and AP per dataset for all curators;
  - `benchmark-oversamplers.tex`: real-only, ROS, SMOTE and the four published oversamplers;
  - `benchmark-ranks.tex`: average ranks and test results;
  - `addendum-datasets.tex`: rows, minority count, imbalance ratio, budget and TEST positives per split, for all 10 datasets.
- Captions must say "Exploratory addendum, declared after the main study".
- If the IEEE draft folder (`paper/rcqasyn-ieee`) exists, add `sections/04b-addendum.tex`.
  - It must contain only a `\subsection{Exploratory addendum}` heading, the `\input` lines for these tables, and `% AUTHORS: write the paragraph here` comments.
  - Do not write any paper prose; the authors write it themselves.
  - Add the BibTeX entries for every method cited above to `references.bib`. Use DOIs or arXiv IDs, verified against the publisher or arXiv page.
- Compile the PDF and confirm it builds.

## Report back
Tell me:
- what ran and what was unavailable, with reasons;
- the average-rank table;
- a five-sentence plain summary of whether quality-coverage beats the published methods;
- the build status.
