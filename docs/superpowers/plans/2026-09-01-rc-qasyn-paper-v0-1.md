# RC-QASyn PAPER v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an evidence-grounded, modular LaTeX PAPER v0.1 for RC-QASyn without presenting development diagnostics or proposed M2+ components as completed final results.

**Architecture:** Keep `paper/main.tex` as a thin document shell and place prose, figures, tables, and manuscript-control notes in focused files. Build every scientific statement from committed artifacts, current implementation, verified literature, or an explicit future-work marker, with a claim ledger and evidence map providing traceability.

**Tech Stack:** LaTeX `article`, BibTeX, TikZ, `booktabs`, `tabularx`, `amsmath`, `hyperref`, `cleveref`, Markdown control notes, PowerShell and `rg` for static validation.

**Spec:** `docs/superpowers/specs/2026-09-01-rc-qasyn-paper-v0-1-design.md`

## Global Constraints

- Use `Anonymous Author(s)` and the working title **Risk-Calibrated Quality-Aware Synthetic Dataset Construction**.
- Keep the abstract explicitly provisional and exclude P1 numbers from it.
- Preserve the evidence hierarchy: artifacts/manifests, source/config, docs, verified notes, primary publication records.
- Never silently reconcile source discrepancies.
- Keep record quality, risk, uncertainty, and dataset marginal contribution distinct.
- Treat M2+ validators, fusion, control, repair, regeneration, and dataset optimization as proposed and unimplemented.
- Do not rerun experiments, alter scientific artifacts, commit, or push.
- Use original prose; do not copy sentences from literature notes or papers.
- Use exact pilot values only when supported by committed artifacts and label them development diagnostics.
- Compilation may be documented but not claimed because no LaTeX executable is installed on this machine.

## File map

- `paper/main.tex`: neutral document shell, packages, metadata, section includes, bibliography.
- `paper/latexmkrc`: reproducible `latexmk -pdf` configuration.
- `paper/README.md`: build instructions, draft status, ownership, and Git workflow.
- `paper/references.bib`: only bibliography entries verified against primary publication records.
- `paper/sections/00_abstract.tex`: provisional non-results abstract.
- `paper/sections/01_introduction.tex`: motivation, gap, research questions, cautious intended contributions.
- `paper/sections/02_related_work.tex`: thematic synthesis and research gap.
- `paper/sections/03_problem_formulation.tex`: notation, scoped evidence, actions, validity/contribution distinction.
- `paper/sections/04_method.tex`: intended framework, status boundaries, record/dataset evidence separation.
- `paper/sections/05_experimental_setup.tex`: implemented datasets, protocol, baselines, metrics, diagnostics, audit, reproducibility.
- `paper/sections/06_results.tex`: pilot observations and future-results structure.
- `paper/sections/07_discussion.tex`: bounded interpretation and unresolved questions.
- `paper/sections/08_ablations.tex`: concrete future ablation designs without values.
- `paper/sections/09_limitations.tex`: living limitations grounded in current state.
- `paper/sections/10_conclusion.tex`: conservative provisional conclusion.
- `paper/sections/11_declarations.tex`: anonymous draft declarations and contribution placeholders.
- `paper/figures/framework_pipeline.tex`: TikZ pipeline distinguishing implemented, diagnostic, and proposed stages.
- `paper/tables/development_datasets.tex`: exact development-dataset characteristics and splits.
- `paper/tables/planned_benchmark.tex`: explicitly planned benchmark roles.
- `paper/tables/pilot_diagnostics.tex`: exact P1 copying, redundancy, and disagreement diagnostics.
- `paper/tables/future_results.tex`: empty human, baseline, calibration, repair, utility, cost, and coverage result shells.
- `paper/notes/claim_ledger.md`: required claim/status/evidence/citation ledger.
- `paper/notes/evidence_map.md`: manuscript-to-repository source map and discrepancies.
- `paper/notes/citation_todo.md`: unresolved citation and metadata work.
- `paper/notes/writing_status.md`: section editing completion and scientific readiness.

---

### Task 1: Create the neutral modular LaTeX shell

**Files:**
- Create: `paper/main.tex`
- Create: `paper/latexmkrc`
- Create: `paper/README.md`
- Create: `paper/sections/00_abstract.tex`
- Create: `paper/sections/01_introduction.tex`
- Create: `paper/sections/02_related_work.tex`
- Create: `paper/sections/03_problem_formulation.tex`
- Create: `paper/sections/04_method.tex`
- Create: `paper/sections/05_experimental_setup.tex`
- Create: `paper/sections/06_results.tex`
- Create: `paper/sections/07_discussion.tex`
- Create: `paper/sections/08_ablations.tex`
- Create: `paper/sections/09_limitations.tex`
- Create: `paper/sections/10_conclusion.tex`
- Create: `paper/sections/11_declarations.tex`
- Create: `paper/figures/framework_pipeline.tex`
- Create: `paper/tables/development_datasets.tex`
- Create: `paper/tables/planned_benchmark.tex`
- Create: `paper/tables/pilot_diagnostics.tex`
- Create: `paper/tables/future_results.tex`
- Create: `paper/notes/claim_ledger.md`
- Create: `paper/notes/evidence_map.md`
- Create: `paper/notes/citation_todo.md`
- Create: `paper/notes/writing_status.md`

**Interfaces:**
- Consumes: approved design specification.
- Produces: stable section, figure, table, and notes paths used by every later task.

- [ ] **Step 1: Create the document shell**

  Use `article` at 11pt with `geometry`, `microtype`, `booktabs`, `tabularx`, `array`, `amsmath`, `amssymb`, `mathtools`, `graphicx`, `xcolor`, `tikz`, `hyperref`, `cleveref`, and `natbib`. Define lightweight draft-status commands and include all section files in numeric order. Use `\bibliographystyle{plainnat}` and `\bibliography{references}`.

- [ ] **Step 2: Create focused empty files with explicit manuscript-safe markers**

  Put a one-line LaTeX comment in each future content file that identifies its intended role. Do not insert numeric stand-ins. Create Markdown table headers for the four control notes.

- [ ] **Step 3: Document build and collaboration**

  In `paper/README.md`, document `latexmk -pdf main.tex`, `latexmk -C`, the absent local toolchain, section ownership, anonymous draft status, and branches `paper/introduction`, `paper/related-work`, and `paper/methodology`. State that authors should edit section files rather than `main.tex`.

- [ ] **Step 4: Verify the scaffold**

  Run from the repository root:

  ```powershell
  rg --files paper | Sort-Object
  rg -n "\\input|\\bibliography" paper/main.tex
  git diff --check
  ```

  Expected: all mapped files exist, all eleven sections are included once, and `git diff --check` emits no output.

- [ ] **Step 5: Review checkpoint**

  Inspect `git diff --stat` and keep the scaffold uncommitted.

### Task 2: Verify and encode the initial bibliography

**Files:**
- Create: `paper/references.bib`
- Modify: `paper/notes/citation_todo.md`

**Interfaces:**
- Consumes: verified repository notes and primary publication records.
- Produces: stable BibTeX keys used by Introduction and Related Work.

- [ ] **Step 1: Verify repository-supported references against primary records**

  Check official ACL Anthology, NeurIPS, ICLR, PMLR, ACM, OpenReview, or arXiv records for: the LLM synthetic-data survey, AGORA-Bench, EPIC, constrained tabular generation, alpha-precision/beta-recall/authenticity, and MT-Bench/Chatbot Arena.

- [ ] **Step 2: Verify core thematic references**

  Verify exact metadata and support before use for CTGAN, GReaT, REaLTabFormer, TabDDPM, TabSyn, Self-Refine, CRITIC, Chain-of-Verification, and modern calibration or risk-control work. If a primary record cannot be verified, exclude the citation and record the intended statement in `citation_todo.md`.

- [ ] **Step 3: Write BibTeX without invented fields**

  Include verified author order, title, year, publication status, venue, pages, DOI, arXiv identifier, and URL only where the primary record supports them. Use stable keys such as `xu2019ctgan`, `borisov2023great`, `solatorio2023realtabformer`, `kotelnikov2023tabddpm`, `zhang2024tabsyn`, `alaa2022faithful`, and `zheng2023judging`.

- [ ] **Step 4: Validate citation-key uniqueness**

  Run:

  ```powershell
  rg -n '^@' paper/references.bib
  $keys = Select-String -Path paper/references.bib -Pattern '^@\w+\{([^,]+),' | ForEach-Object { $_.Matches[0].Groups[1].Value }
  $keys | Group-Object | Where-Object Count -gt 1
  ```

  Expected: bibliography entries are listed and the duplicate-key command emits no output.

- [ ] **Step 5: Review checkpoint**

  Confirm that each bibliography entry has a primary verification source recorded in `citation_todo.md` or the eventual evidence map. Keep changes uncommitted.

### Task 3: Draft the provisional abstract, Introduction, and Related Work

**Files:**
- Modify: `paper/sections/00_abstract.tex`
- Modify: `paper/sections/01_introduction.tex`
- Modify: `paper/sections/02_related_work.tex`
- Modify: `paper/notes/citation_todo.md`

**Interfaces:**
- Consumes: citation keys from Task 2 and status vocabulary from the design.
- Produces: the manuscript's motivation, research questions, contribution framing, and literature-derived gap.

- [ ] **Step 1: Draft the provisional abstract**

  State the problem, proposed sequential-construction perspective, heterogeneous scoped evidence, and evaluation design. Add `% TODO[RESULTS]: replace after final benchmark and completed human evaluation`. Do not include P1 numbers or imply M2+ evaluation.

- [ ] **Step 2: Draft the Introduction**

  Write a cohesive seven-part argument: uses of synthetic data; multi-level failure modes; limits of single/aggregate evaluation; record validity versus marginal dataset value; sequential construction; RQ1--RQ5 with RQ3--RQ5 marked future-dependent; and intended contributions with explicit implementation/evaluation boundaries.

- [ ] **Step 3: Draft thematic Related Work**

  Create subsections for tabular generation, LLM synthetic data, quality evaluation, LLM critics, uncertainty/calibration/risk, iterative refinement/repair, and the research gap. Synthesize across papers rather than writing one paragraph per paper. Use citation comments where the bibliography remains incomplete.

- [ ] **Step 4: Check claim language and citations**

  Run:

  ```powershell
  rg -n -i "revolutionary|groundbreaking|unprecedented|state-of-the-art|significantly better|no previous work" paper/sections/00_abstract.tex paper/sections/01_introduction.tex paper/sections/02_related_work.tex
  rg -o '\\cite[tp]?\{[^}]+\}' paper/sections/00_abstract.tex paper/sections/01_introduction.tex paper/sections/02_related_work.tex
  ```

  Expected: the overclaim scan emits no output; every emitted citation command refers to a key in `references.bib`.

- [ ] **Step 5: Review checkpoint**

  Read the three files consecutively to ensure the abstract does not outrun the Introduction and the gap does not claim exhaustive novelty. Keep changes uncommitted.

### Task 4: Draft the mathematical formulation and proposed framework

**Files:**
- Modify: `paper/sections/03_problem_formulation.tex`
- Modify: `paper/sections/04_method.tex`
- Modify: `paper/figures/framework_pipeline.tex`

**Interfaces:**
- Consumes: repository contracts for evidence dimensions, verdicts, severity, and actions.
- Produces: notation and conceptual interfaces used by methodology, results, and discussion.

- [ ] **Step 1: Define generation and evolving-dataset notation**

  Define `D_{\mathrm{train}}`, specification `S`, condition `c`, generator `G`, TRAIN-derived context `C_{\mathrm{train}}`, candidate `x_t`, and evolving accepted dataset `D_{\mathrm{syn}}^{(t)}` before using them.

- [ ] **Step 2: Separate four analytical objects**

  Define record quality `Q_R(x_t)`, record risk `R_R(x_t)`, evaluator uncertainty `U_R(x_t)`, and dataset marginal contribution `\Delta_D(x_t\mid D_{\mathrm{syn}}^{(t)})` without collapsing them into a weighted scalar. State mathematically that record validity does not imply positive marginal contribution.

- [ ] **Step 3: Define heterogeneous evidence and actions**

  Represent each evidence item with scope, dimension, verdict or score, uncertainty or confidence, and provenance. Use FIELD, RECORD, SUBGROUP, and DATASET scopes. Define `ACCEPT`, `REPAIR`, `REGENERATE`, and `REJECT` as future controller actions, noting that repository contracts also reserve revalidation.

- [ ] **Step 4: Draft the framework prose and figure**

  Describe specification, generation, independent validators, evidence, calibration/fusion, risk-aware control, localized action, dataset contribution control, audit, and utility. Style implemented M1 nodes solid, M1.5 diagnostics distinctly, and proposed M2+ nodes dashed. Make the caption state that the full pipeline is an intended architecture, not a completed evaluated system.

- [ ] **Step 5: Verify notation and boundaries**

  Run:

  ```powershell
  rg -n "Q_R|R_R|U_R|Delta_D|ACCEPT|REPAIR|REGENERATE|REJECT|proposed|implemented" paper/sections/03_problem_formulation.tex paper/sections/04_method.tex paper/figures/framework_pipeline.tex
  git diff --check
  ```

  Expected: every required concept appears, proposed status is explicit, and whitespace validation passes.

- [ ] **Step 6: Review checkpoint**

  Confirm that record-level quality, risk, uncertainty, and dataset contribution remain non-interchangeable. Keep changes uncommitted.

### Task 5: Draft the implemented experimental methodology

**Files:**
- Modify: `paper/sections/05_experimental_setup.tex`
- Modify: `paper/tables/development_datasets.tex`
- Modify: `paper/tables/planned_benchmark.tex`

**Interfaces:**
- Consumes: P1 configs, run manifests, profiles, split manifests, prompt v2, source code, and human-review docs.
- Produces: exact development dataset, generation, baseline, metric, diagnostic, human-audit, and reproducibility descriptions.

- [ ] **Step 1: Write the dataset and split protocol**

  Report exact totals and full class counts: page-blocks0 5,472 rows with 4,913/559 classes and 10 numerical features; Ecoli4 336 rows with 316/20 classes and 7 numerical features; Abalone19 4,174 rows with 4,142/32 classes and 7 numerical plus 1 categorical feature. Report committed 80/20 splits: 4,377/1,095, 269/67, and 3,340/834 respectively. Label all three development/pilot datasets.

- [ ] **Step 2: Write exact P1 generation protocol**

  State `gemma4:e4b`, local OpenAI-compatible Ollama endpoint, temperature 0.7, requested count 200, quotas 100/100, batch size 5, four class-aware TRAIN references, generation prompt v2, JSON-object transport with `records`, max tokens 2,048, timeout 120 seconds, root/base seed 42, and SHA-256-derived unique per-dataset/class/batch provider seeds. State that REAL TEST statistics are excluded from generation.

- [ ] **Step 3: Define B1, B2, and B3 exactly**

  B1 accepts every parseable candidate. B2 applies schema, category-domain, missing-value, target-condition, observed-range, and existing duplicate behavior with configured severity policy. B3 uses one uncalibrated same-model judge, threshold 0.7, temperature 0, strict JSON parsing, and malformed-output rejection. State that all baselines consume the same raw pool.

- [ ] **Step 4: Define metrics and diagnostics**

  Describe KS, Wasserstein, TVD, JSD, Pearson/Spearman correlation error, duplicate rate, entropy, variance ratio, class-conditional views, TRTR, TSTR, logistic regression, random forest, F1, average precision/PR-AUC, MCC, balanced accuracy, and AUROC. Explain that copying/support measures were diagnostic and did not affect acceptance.

- [ ] **Step 5: Write the blinded human-evaluation protocol**

  State 120 unique-prioritized records, 40 per dataset, Reviewer A 120, Reviewer B deterministic 40-record overlap, blinded fields, precise human-validity definition, redundancy handling, raw agreement, Cohen's kappa, and manual adjudication. State that labels remain incomplete.

- [ ] **Step 6: Disclose reproducibility caveats**

  Explain the P0-v2 same-class repeated-seed confound and the corrected derivation from root seed, dataset, requested class, and batch index. State that P1 uses the corrected protocol, P0-v2 diversity is not generator-quality evidence, run manifests are dirty-state captures, and Ecoli4 produced 201 parseable candidates against 200 requested.

- [ ] **Step 7: Verify exact values against sources**

  Re-read `configs/experiments/pilot_p1/*.yaml`, P1 `manifest.json`, `dataset/profile.json`, `dataset/split_manifest.json`, `prompts/generation/v2.txt`, and `docs/human-review.md`; compare every number in the two tables and methodology prose.

- [ ] **Step 8: Review checkpoint**

  Confirm no REAL TEST statistic is described as generation context and no local Ollama detail is framed as a contribution. Keep changes uncommitted.

### Task 6: Draft pilot Results and all forward-looking sections

**Files:**
- Modify: `paper/sections/06_results.tex`
- Modify: `paper/sections/07_discussion.tex`
- Modify: `paper/sections/08_ablations.tex`
- Modify: `paper/sections/09_limitations.tex`
- Modify: `paper/sections/10_conclusion.tex`
- Modify: `paper/sections/11_declarations.tex`
- Modify: `paper/tables/pilot_diagnostics.tex`
- Modify: `paper/tables/future_results.tex`

**Interfaces:**
- Consumes: exact P1 reports listed in the design and methodology terminology from Task 5.
- Produces: bounded development observations, living interpretation, explicit future evaluations, and conservative closure.

- [ ] **Step 1: Write Results 6.1 and the pilot table**

  Report pool sizes 200/201/200 for Abalone19/Ecoli4/page-blocks0; duplicate rates 28.5%, 10.45%, and 9.5%; reference-match rates 24.5%, 10.95%, and 1.0%; zero exact non-reference TRAIN matches; and B2-reject/B3-accept disagreements 62, 26, and 25. Label all values development diagnostics and note overlapping defect categories where relevant.

- [ ] **Step 2: Structure incomplete result subsections**

  Add Human Ground-Truth Audit, Final Benchmark, and Ablations subsections with `--` table cells and explicit comments naming the required future evidence. Do not use zero as a placeholder.

- [ ] **Step 3: Create future result tables**

  Provide shells for human critic benchmark; B1/B2/B3/B5 comparison; record- and dataset-level ablations; calibration; repair; full regeneration versus localized repair cost; final TSTR; quality-cost; and coverage/diversity. Every caption must say planned or pending.

- [ ] **Step 4: Draft bounded Discussion**

  Discuss syntax versus quality, record validity versus dataset value, same-model self-judging, reference anchoring, redundancy with scale, quality-cost trade-offs, and the motivation for heterogeneous evidence. Mark conclusions that require human or final benchmark evidence.

- [ ] **Step 5: Draft the living Limitations**

  Include development-only datasets, small incomplete human audit, specialist-domain judgment, same generator/judge model, local-model generalizability, unstable extreme-imbalance utility, limited generated sample size, unimplemented privacy/fairness, representation-dependent diagnostic distances, dirty-state run provenance, the Ecoli4 count anomaly, and pending repeated splits/final benchmark.

- [ ] **Step 6: Draft conservative Conclusion and Declarations**

  Summarize the problem and proposed separation without performance claims. Keep funding, conflicts, data/code availability, ethics, and CRediT-style author contributions as anonymous draft fields awaiting author review.

- [ ] **Step 7: Run language safeguards**

  ```powershell
  rg -n -i "state-of-the-art|statistically significant|significantly better|privacy leakage|final results" paper/sections/06_results.tex paper/sections/07_discussion.tex paper/sections/10_conclusion.tex
  rg -n "201|28\.5|10\.45|9\.5|24\.5|10\.95|62|26|25" paper/sections/06_results.tex paper/tables/pilot_diagnostics.tex
  ```

  Expected: prohibited claims are absent except explicit negations; all planned exact pilot values are present.

- [ ] **Step 8: Review checkpoint**

  Confirm no human label, M2 result, final benchmark value, significance result, or ablation outcome has been invented. Keep changes uncommitted.

### Task 7: Complete the claim ledger, evidence map, and writing status

**Files:**
- Modify: `paper/notes/claim_ledger.md`
- Modify: `paper/notes/evidence_map.md`
- Modify: `paper/notes/citation_todo.md`
- Modify: `paper/notes/writing_status.md`

**Interfaces:**
- Consumes: every manuscript claim and table from Tasks 3--6.
- Produces: auditable manuscript control state and final handoff counts.

- [ ] **Step 1: Populate the claim ledger**

  Use columns Claim, Section, Status, Evidence, Citation, Final-evaluation required?, and Notes. Include claims covering implemented transport/seeding/splits/baselines/diagnostics/audit infrastructure, development observations, literature-supported framing, proposed RC-QASyn components, and pending human/final results.

- [ ] **Step 2: Populate the evidence map**

  Map every numeric table and material implementation statement to exact artifact, config, manifest, source, documentation, literature record, or future experiment. Add a discrepancy register for Ecoli4 201/200, dirty run manifests, undefined pilot TSTR entries, and the workbook inspection gap.

- [ ] **Step 3: Finish citation and writing status notes**

  List unverified literature themes and excluded placeholder notes. Give rough editorial completion percentages by section while distinguishing editing progress from scientific completion.

- [ ] **Step 4: Count claim statuses**

  Run:

  ```powershell
  rg -o "VERIFIED_IMPLEMENTATION|DEVELOPMENT_OBSERVATION|LITERATURE_SUPPORTED|PROPOSED|FINAL_RESULT_PENDING" paper/notes/claim_ledger.md | Group-Object | Sort-Object Name
  ```

  Expected: each status used by the manuscript has a non-zero count and can be reported in the final handoff.

- [ ] **Step 5: Review checkpoint**

  Trace every pilot number in the manuscript back through `evidence_map.md`. Keep changes uncommitted.

### Task 8: Perform static manuscript validation and final diff review

**Files:**
- Verify: all files under `paper/`
- Verify: `docs/superpowers/specs/2026-09-01-rc-qasyn-paper-v0-1-design.md`
- Verify: `docs/superpowers/plans/2026-09-01-rc-qasyn-paper-v0-1.md`

**Interfaces:**
- Consumes: complete manuscript tree.
- Produces: evidence-backed validation and final handoff without a commit.

- [ ] **Step 1: Confirm toolchain status**

  Run:

  ```powershell
  Get-Command latexmk,pdflatex,bibtex,biber -ErrorAction SilentlyContinue
  ```

  Expected on this machine: no command output. Record compilation as unavailable.

- [ ] **Step 2: Validate included files and bibliography keys statically**

  Enumerate every `\input{...}` and confirm the target `.tex` file exists. Extract citation keys from section files and confirm each appears exactly once as an entry key in `references.bib`.

- [ ] **Step 3: Scan manuscript safety markers**

  Run searches for prohibited overclaim language, unresolved references, fake numeric zeros in future tables, accidental final-result wording, and inconsistent terminology. Inspect every match rather than suppressing warnings.

- [ ] **Step 4: Run repository-level diff checks**

  ```powershell
  git diff --check
  git status --short
  git diff --stat
  git diff -- paper docs/superpowers/specs/2026-09-01-rc-qasyn-paper-v0-1-design.md docs/superpowers/plans/2026-09-01-rc-qasyn-paper-v0-1.md
  ```

  Expected: no whitespace errors; only the approved specification, plan, and manuscript files are new or modified; no artifact or source-code changes.

- [ ] **Step 5: Prepare the requested handoff**

  Report manuscript files, rough editing percentages, verified references, citation gaps, claim counts, every cited P1 artifact, unfinished scientific areas, compile command/status, Git status, and exactly one recommended next writing task.

- [ ] **Step 6: Final review checkpoint**

  Leave all changes uncommitted and do not push.
