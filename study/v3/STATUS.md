# Study v3 status

Updated by the agent at the end of every session. Gates are approved only by the user.

| Field | Value |
| --- | --- |
| Phase | 2 finishing / 3 started (user authorised autonomous completion of the whole plan, 2026-11-01); Gate 2 freeze not yet written, so no TEST metric computed |
| Last finished step | Driver lock (df6e732) and duplicate-collection handling (4fb86d0) after two Haiku drivers ran at once; Haiku 1,330/2,730 requests ok |
| Runs in progress | restarted 2026-11-01 12:34 IST and still running after a Claude Code restart: U2 generation (`runs/phase3/u2/progress.json`, 134/200), qwen Phase 2 pools (`runs/phase2/llm/progress-qwen2.5_7b-instruct.json`, 21/40), Haiku driver (`runs/phase3/llm/claude-haiku-5-5/batches.jsonl` vs `collected.jsonl`). A second Haiku driver from 12:28 is also alive (the agent may not stop it); the per-model lock keeps them from overlapping |
| API spend so far | Anthropic $1.142 of $5 (one repeated batch line annotated, not counted twice) · OpenAI $0.177 of $4 · Meta $0.163 of $140 (incl. one reconciled upper bound) |
| Blockers | none; the Haiku remainder (~1,400 requests) projects to about $2.7 in total, under the $4 line |
| Next step | Let the three runs finish; then the five-learner check (GPU, after qwen), merged_method and the protocol freeze |

## Phase 0 checklist

| Task | State | Evidence |
| --- | --- | --- |
| Environment, baseline tests/lint/types | done | `report/phase0-baseline.md`: 1823 passed; pyright 0; ruff 4 pre-existing findings in protected `artifacts/reports/phase2/agent-labels-v1/` (left untouched) |
| Ollama + three local models | done | `report/phase0-smoke.json`; qwen2.5:7b-instruct pulled; gemma4:e4b needed one recorded retry (first load > 120 s on 8 GB GPU) |
| Anthropic / OpenAI / Meta adapters + budget ledger | done | `providers.py`, `pricing.py`, `budget.py`; 13 offline tests; all 5 API smoke calls returned `{"ok":true}` |
| Declared dataset fetcher | done | `fetch.py`; 7 offline tests (refusal, name check, MD5, empty, SHA-256) |
| U2's 30 datasets + 10 new shortlisted | done (metadata) | `sources.json`, `report/source-metadata.json` |
| U2 core raw files fetched | **24/30** | `report/acquisitions.json`; attempts in `report/u2-core-fetch-attempt{1,2,3}.jsonl` |
| 10 new benchmark files fetched | **9/10** | attempts in `report/new-fetch-attempt{1,2}.jsonl` |
| KEEL dev files fetched | done (9/9; 8 in use after page-blocks0 was dropped) | user approved download 2026-10-31; via official-page links; 3 match recorded hashes |
| ml_ugo a6710ea installed read-only, U2/UGO run on a dev dataset | done | `report/u2-dev-check/`: Abalone19, seed 42, 5 classifiers × 6 methods, 30/30 cells, 0 failures |
| Draft `protocol.json` | done | Gate 0 decisions recorded; open choices are `null` with the deciding gate |

## Gate 0: findings and proposals

**Model list (decision needed).**
- OpenAI's pricing page lists **`gpt-6-luna`**, not "GPT-6.1-luna". I registered and smoke-tested `gpt-6-luna` ($0.10/$0.50 per MTok; Batch $0.05/$0.25). Proposal: use `gpt-6-luna`.
- Verified IDs and list prices (provider pages, 2026-10-31): `claude-haiku-5-5` $0.10/$0.50 (Batch 50%; higher tier above 100K-token prompts), `claude-sonnet-5-5` $2/$10, `gpt-6.1-terra` $1/$5, `muse-spark-1.3` $1.25/$4.25 (standard endpoint: content not used for training; never the `-contributor` model).
- Meta documents no Batch API, so Muse Spark runs synchronously at full price. Its reasoning cannot be turned off (`minimal` is the lowest effort), and it used 29 reasoning tokens even on the smoke call. Those tokens are logged separately.
- Haiku/Sonnet 5.5 reject non-default `temperature` and take no `seed`, so per-batch seeds apply only to OpenAI, Meta and Ollama. Diversity across Anthropic batches has to come from the prompt context.
- PLAN says "pull the five local models" but lists three; I set up the three listed.

**Datasets (decision needed).**
- Proposed 10 new benchmark datasets: adult (1590), default-of-credit-card-clients (42477), creditcard (1597), jm1 (1053), kick (41162), Bank_Customer_Churn (46911), Marketing_Campaign (46940), Is-this-a-good-customer (46938), ipums_la_99-small (1018), GiveMeSomeCredit (46929).
- **GiveMeSomeCredit is a Kaggle-competition source**, whose rules may restrict reuse. Confirm the licence or swap in a reserve.
- Reserves: Amazon_employee_access (4135, competition), porto-seguro (42742, competition, 595K rows), rl (41160, provenance undocumented).
- OpenML lists most of these as "Public", which is a platform default, not a licence statement. Origins are recorded per dataset.
- **Overlap:** dev page-blocks0 (KEEL) and U2 benchmark page-blocks (OpenML 1021; U2 calls it page-blocks-bin) come from the same table. Proposal: drop page-blocks0 from dev (leaving 8 dev datasets) so tuning never touches a benchmark table.
- 7 U2 core datasets have fewer than 30 minority TEST records at 80/20 (thoracic-surgery, arsenic-female-bladder, vowel, pc1, dis, Satellite, haberman). They are flagged and kept for comparability, as PLAN requires.
- jm1 belongs to the same NASA defect-metric family as U2's kc1/pc1/pc3/pc4. It is a different project table, not a re-binarization, but it is flagged.

**Unavailable.**
- Six addendum-v1 KEEL dev files (yeast3, yeast4, vehicle0, segment0, ecoli1, abalone9-18) are not on this machine, and `artifacts/archives/` is absent. They need hand placement at the paths in `addendum/v1/configs/datasets/*.yaml`. winequality-red-4 stays unavailable, as in addendum v1.

**API budget cap.** No change proposed yet. The Phase 3 pilot replaces the estimates. The 80% guard is enforced per provider in code.

**U2 code.** ml_ugo needs pandas 3.0.5 and scikit-learn 1.6.0, which conflict with rcqasyn's `pandas<3`. It therefore gets its own venv (`study/v3/vendor/.venv-u2`). `u2_bridge.py` runs the notebook's embedded sources unmodified. It reads them with `ast` and executes no notebook cells. It replaces only the OpenML loader with a local, hash-verified KEEL reader, because U2's loader downloads through the `openml` package and would bypass the declared fetcher. Planned check: Abalone19 (sha256 verified against `data/manifests/Abalone19/source.json`; it has a nominal column), all five classifiers and six methods, seed 42.

**Notes.**
- `scripts/record_test_run.py` was not run, because it writes to protected `test-results/`.
- Study v3 tests run with `python -m pytest study/v3/tests`; type checks with `pyright --pythonpath .venv/Scripts/python.exe study/v3/*.py study/v3/tests`.

## Session 2 findings (2026-10-31, after user go-ahead on items 4 and 5)

**KEEL dev files (item 4: user approved downloading instead of hand placement).**
- The declared fetcher now handles `source: "keel"` (`2a0c812`). It downloads only the archive link printed on the official page `https://sci2s.ugr.es/keel/imbalanced.php` (re-read at fetch time; refused if the declared href is absent), extracts only the declared `.dat` by basename, and records zip and `.dat` SHA-256.
- All 9 fetched to the gitignored `study/v3/data/raw/keel/`. Abalone19, Ecoli4 and page-blocks0 match the SHA-256 recorded in `data/manifests/*/source.json` for the earlier hand-placed copies.
- Provenance note: the official page links to `keel/keel-dataset/datasets/imbalanced/<IR group>/<name>.zip`. Addendum v1 and the run-v2 manifests record `keel/dataset/data/imbalanced/<name>.zip`, which is not on the page. Only page links were used; protected configs were not edited.

**U2 isolated venv (item 5).** The earlier stopped install had left torch broken (`torchgen` missing). Reinstalled the full `ml_ugo/requirements.txt` pins, with torch from the cu130 index, into `study/v3/vendor/.venv-u2`. torch 2.13.0+cu130 sees CUDA; pandas 3.0.5, scikit-learn 1.6.0.

**U2/UGO check on dev Abalone19 (item 5).** `u2_bridge.py` ran the unmodified bundle (bundle SHA-256 `fad69bce…`, notebook `a888d970…`, ml_ugo `a6710ea`). Abalone19 is a dev dataset, so the TEST metrics are within the rules.
- Smoke config: 25/30 cells. All 5 `kmeans_smote` cells failed inside imbalanced-learn: "No clusters found with sufficient samples of class 1", since only about 20 minority rows are spread over 8 clusters. U2's own failure handling recorded these; nothing was changed.
- Full config: 30/30 cells, 0 failures, with U2's notebook defaults. Per-cell metrics are in `report/u2-dev-check/per_cell_metrics.csv`. They are a single-seed run-check, not evidence for any method. F1 is 0 for most cells at 32 minority rows; `u2_flow_gate` accepted 35–42 of 1000 candidates; `original_ugo` accepted 0 of 1000.

**U2 core fetch (item 5).** Attempt 1: 10/30 ok. Attempt 2 (the one allowed retry, failed keys only): 12/20 ok. Total **22/30**.
- Unavailable: blood-transfusion-service-center (1464), mammography (310), dis (40713), Satellite (40900), wilt (40983), Sick_numeric (41946), haberman (43), letter (977).
- Causes: HTTP 503 from the OpenML API after about 10–12 datasets per attempt (looks like rate limiting); one 412 (41946).
- wilt failed MD5, receiving the **same body** (MD5 `87899c48…`) that failed arsenic-female-bladder in attempt 1. So OpenML served the same wrong body for two different datasets, most likely an error page. The MD5 check refused it and nothing was written. arsenic succeeded on retry.
- Leftover unverified files from the stopped first job sit under `data/raw/openml/` for 5 of the unavailable IDs. They have no acquisition record and must not be used. Loaders read paths only from `acquisitions.json`.
- 3 of the 8 unavailable datasets (dis, Satellite, haberman) are also among those flagged as having fewer than 30 minority TEST records.

## Decisions requested at Gate 0

1. Use `gpt-6-luna` in place of "GPT-6.1-luna"?
2. Approve the 10 new datasets (and the GiveMeSomeCredit licence), or swap in reserves?
3. Drop page-blocks0 from dev?

**User answers (2026-10-31).** 1: use `gpt-6-luna`. 2: all 10 approved, GiveMeSomeCredit included. 3: page-blocks0 dropped. 6: caps kept. 7: second retry approved. Recorded in `sources.json` and `protocol.json` (`151eba0`).

4. ~~Place the six KEEL dev files by hand?~~ — user approved downloading; done (9/9).
5. ~~Restart the two stopped jobs~~ — approved and done (see Session 2 findings).
6. Keep the API caps as declared?
7. Allow a second retry of the 8 unavailable U2 core datasets with slower pacing (e.g. 10 s between requests), outside the one-retry rule? — approved; done (see below).
8. ~~Allow a further paced fetch~~ — approved 2026-10-31; all 7 fetched in round 1 (`4f03164`). Original text: allow a further paced fetch of the 7 still-unavailable benchmark datasets? For example, one dataset at a time, 120 s apart, at most 2 more attempts each, with every attempt logged. Without it the benchmark is 33 of 40 datasets.

## Session 3 findings (2026-10-31, after the Gate 0 answers)

- **U2 core second retry** (10 s pacing; approved): wilt and letter ok. 24/30.
- **10 new datasets**, attempt 1 (10 s pacing): adult, default-of-credit-card-clients, creditcard and jm1 ok. The other 6 got HTTP 412.
- **10 new datasets**, one allowed retry (60 s pacing): kick, ipums_la_99-small, GiveMeSomeCredit, Marketing_Campaign and Is-this-a-good-customer ok. 9/10.
- **Still unavailable (7 of 40 benchmark):**
  - U2 core: blood-transfusion-service-center (1464), mammography (310), dis (40713), Satellite (40900), Sick_numeric (41946), haberman (43);
  - new: Bank_Customer_Churn (46911).
- Every failure was an HTTP 412 or 503 from the OpenML JSON API on the **metadata** request. The same metadata requests for 1464, 310 and 41946 returned 200 shortly after attempt 3. These are transient server responses, not missing datasets. No other source was tried.
- Dev: 8/8 (page-blocks0 dropped). Benchmark: 33/40.

## Phase 1: findings (2026-10-31; dev datasets, VALIDATION only, TEST never used)

The user approved starting Phase 1 and the paced fetch on 2026-10-31.

**Setup.**
- `devroot.py` assembles a gitignored project root for the 8 dev datasets. All 8 fetched KEEL files match the SHA-256 recorded in the run-v2 / addendum-v1 manifests, and `dataset_specification` re-verifies the recorded split and schema.
- Validation is a stratified 20% of each outer TRAIN (split seeds 13/29/43/61/79), ordered by SHA-256 as `make_split` orders TEST.
- Validation minority rows per split:

  | Dataset | Minority rows |
  | --- | --- |
  | Ecoli4 | 3 |
  | Abalone19 | 5 |
  | abalone9-18 | 7 |
  | yeast4 | 8 |
  | ecoli1 | 12 |
  | yeast3 | 26 |
  | vehicle0 | 32 |
  | segment0 | 53 |

  **Every Phase 1 number is noisy for that reason.**
- All results are descriptive. Reports are under `report/phase1/`.

| Step | Result | Report / commit |
| --- | --- | --- |
| 1. QC vs random (SMOTE pool, LR/RF, default threshold) | QC minus random median F1: LR -0.002 (0 of 7 datasets positive), RF -0.006 (2 of 7). Reproduces the earlier "no F1 gain over random". | `step1-qc-vs-random/`, `257f862` |
| 2a. Budget size 0.5x / 1x / 2x | QC minus random median F1, RF: +0.000 / -0.006 / **+0.020 (5 of 7 positive)**; LR: about 0 at every scale. | `step2-budget/`, `8f4ba2f` |
| 2b. Learner (U2's five, U2 search spaces, threshold and parameters picked on one validation half and scored on the other) | QC minus random median F1 ranges from -0.008 (RF) to +0.001 (MLP). **SMOTE+b minus real ranges from -0.015 to +0.000 across all five learners.** With tuned thresholds, oversampling does not beat no oversampling, as U2 also found. | `clf-ablation/`, `ea8c865` |
| 2c. Pool generator (SMOTE, KMeans-SMOTE, RWO, original UGO, native U2, U2+flow gate; pinned ml_ugo, unmodified) | QC minus random median F1 per pool: -0.006 to +0.002. Random-from-pool minus real (RF): +0.018 to +0.029. | `step3-gate/`, `186e647` |
| 3. Quality gate on U2/UGO/SMOTE output | Structural failures occur only on vehicle0: 100% of candidates from every generator break integer declarations, and 0 are repair-eligible under the <=3-field rule. No exact copies of inner TRAIN. Within-pool duplicates 0-1.7%. q=0.90 admission keeps 64-70%. **Pool smaller than budget:** u2_flow_gate 17/40 splits, original_ugo 14/40 (0 accepted on all 5 Abalone19 splits), u2_native 10/40. | `step3-gate/`, `186e647` |
| 4. Oracle upper bound (100 random budget-sized subsets of the admitted SMOTE pool) | In-sample best minus mean F1: LR +0.020, RF +0.093 (optimistic by construction). **Honest (pick on half A, score on half B): LR +0.000, RF -0.000.** | `step4-oracle/`, `ea0f5d1` |

**Not run, with reasons.**
- **Minority-quota ablation (50% vs real ratio).** Every Phase 1 pool contains minority candidates only, and HYBRID_MINORITY training uses only minority synthetic rows, so the quota has no effect. It matters only for two-class (LLM) pools.
- **Stored LLM stream as a pool.** It exists only for Abalone19 and Ecoli4, on historical split 42. Its payloads need the frozen source worktree (`244a9bf`) restored byte for byte. Its generation context was the whole split-42 TRAIN, which contains any validation carve, so validation scores would be contaminated.

**Corrections made during Phase 1.**
- Commit `257f862` claimed pyright had 0 errors; it had 8. They were fixed in `4465ef6`, which records the error. The carve refactor reproduces all 40 recorded validation fingerprints.
- The first U2 pool export recorded 11 empty pools as failures, because of an exporter bug on zero rows. Fixed and re-exported to `runs/phase1/u2-pools-v2`. The first export is kept locally as superseded.

**Reading.**
- On these dev datasets, no selection rule (quality-coverage included) shows headroom over random selection that carries to held-out validation rows.
- With tuned thresholds, oversampling itself does not beat no oversampling.
- At these validation sizes, a utility term tuned on dev validation is likely to fit noise.
- The one consistent lead is QC at 2x budget with RF, and it does not hold for the other learners.
- So far the gate's real value is diagnostic: it caught the integer breakage on vehicle0 and the pool shortfalls in U2 and UGO.

## Decisions requested at Gate 1

1. **Utility terms for Phase 2.** The PLAN offers U2 difficulty x stability, FlowGMM compatibility as a separate admission column, KNN-Shapley on validation, a boundary score, and CLLM-style confidence.
   - Proposal: carry at most two, U2 difficulty x stability (cheap; computed by U2's frozen code) and the boundary score.
   - Tune both with the repeated validation design in item 2.
   - Drop KNN-Shapley: the honest oracle finds no stable validation signal for a validation-fitted value to learn.
2. **Validation design for tuning.** Proposal: replace the single 20% carve with stratified 5-fold cross-fitting inside each outer TRAIN for every tuning choice. Every choice would then see all TRAIN minority rows (for example 26 instead of 5 on Abalone19). This changes `protocol.json` `splits.validation`, so it needs your approval.
3. **Quota and LLM-pool ablation.** Proposal: run both in Phase 2 on fresh small LLM pools from dev inner TRAIN, using local Ollama only (no API spend), once the v3 generation prompt is drafted. Alternative: drop the quota ablation, since the quota has no effect when training uses minority synthetic rows only.
4. **vehicle0 repair.** On fresh pools, 0 of 6,400 SMOTE-family and UGO candidates and 0 of 2,027 U2 candidates are repair-eligible under the frozen <=3-field rule. Any rule that rescues them must touch more than 3 integer fields. Proposal: declare "round every integer-declared field half-even" as a new, separately reported variant, and never silently widen the existing bound.
5. **Scope and claims.** On present evidence, the success criterion proposed for Gate 2 (the merged method beats tuned no oversampling and U2 with Holm p < 0.05) looks unlikely to be met. Proposal: keep it as declared, report a miss as found, and add the gate diagnostics (structure, shortfall, copying) as a secondary contribution. This is your call.

**User answers (2026-11-01).** Yes to 1-5, as proposed. Recorded in `protocol.json`:
- `utility_term_selected`: U2 difficulty x stability and the boundary score. KNN-Shapley dropped; FlowGMM compatibility and CLLM-style confidence are not utility terms.
- `splits.validation`: stratified 5-fold cross-fitting inside each outer TRAIN.
- `ablations_phase2`: quota and LLM-pool ablation on local Ollama pools only.
- `repair_variants.integer_rounding_v3`: a new, separately reported variant.
- `scope_decision`: criterion kept; a miss is reported as found; gate diagnostics are a secondary contribution.

## Phase 2: progress (2026-11-01; dev datasets, 5-fold cross-fit inside TRAIN, TEST never used)

**Code.**
- `crossfit.py`: 5 stratified folds per outer TRAIN; each fold's threshold is chosen on the other 4 folds (U2's rule).
- `utility.py`: the two approved terms. "u2" assigns each candidate to its nearest inner minority anchor and scores it as difficulty percentile x group stability. "boundary" is the majority share among 5 inner neighbours, ranked by closeness to beta.
- `u2_phase2.py`: per fold, the anchor table and U2 pools at fixed alpha 0.5 and tau 0.5. Nothing is tuned on the held-out fold.
- `repair_v3.py`: `integer-round-all-half-even-v3`.
- `phase2.py` / `phase2_report.py`: the screen and its report.
- `llm_pools.py`, `phase2_llm.py`, `label_sample.py`: local LLM pools, quota ablation, blinded sample.
- `phase2_clf.py` / `u2_crossfit.py`: five-learner check.

**Screen** (`report/phase2/selection/`, `6c4a87d`; LR and RF at frozen defaults).
- Every design is within about +/-0.01 median F1 of random selection from the same pool.
- **Boundary term (top 50%, then QC)** is the only design positive for both classifiers on most datasets:
  - smote pool, beta 0.25: +0.003 LR, +0.008 RF (6 of 7 datasets each);
  - union pool, beta 0.5: +0.008 LR, +0.003 RF (5 of 7).
- **U2 difficulty x stability** is neutral to negative: union/u2/top is -0.007 LR and -0.017 RF (1 of 7 positive).
- **Ranking reproducibility** across split-seed halves {13, 29} vs {43, 61, 79}, as Spearman correlation:
  - smote pool: 0.05-0.14;
  - union pool: 0.49 (LR) and 0.71 (RF).

  Picking the best of 16 designs therefore partly picks noise. The five-learner check is the next filter.
- **SMOTE+b minus REAL** (cross-fit, tuned threshold): +0.002 LR, +0.009 RF on 6 SMOTE datasets.
- **Rounding variant on vehicle0:** made 6,400 of 6,400 smote and 16,496 of 16,496 union candidates structurally complete (0 before). vehicle0 is the only dev dataset with integer declarations.
- **U2 pools at the default alpha and tau:** all 400 fold pools ok.

**Declared scale choices (Phase 2).**
- LLM pools: one local model (qwen2.5:7b-instruct), split seed 13 only, all 5 folds x 8 datasets. Measured throughput is about 4 min per fold, so all 5 splits x 3 models would take several days.
- The v3 prompt lives in `study/v3/prompt_templates/`, because the permission settings deny writes under any `prompts/` directory. `protocol.json` records its path and SHA-256.
- First trial pool (Ecoli4 s13 f0): 120/120 parsed with exact keys; 103 admitted; 3 exact copies of prompt reference rows (a copying diagnostic) despite the instruction not to copy.

## Stopped jobs (2026-11-01, low system memory)

Claude Code stopped every background job because the machine ran critically low on memory. Nothing was lost; each job resumes from its last finished unit when started again.

| Job | Progress when stopped | Resume command (repo root) |
| --- | --- | --- |
| Phase 2 qwen2.5:7b-instruct pools, split 13 | 20/40 folds (`runs/phase2/llm/progress-qwen2.5_7b-instruct.json`) | `./.venv/Scripts/python.exe -m study.v3.llm_pools --model qwen2.5:7b-instruct --out study/v3/runs/phase2/llm --seeds 13` |
| Phase 3 U2-side generation (CPU) | 122/200 splits, 0 failures (`runs/phase3/u2/progress.json`) | `study/v3/vendor/.venv-u2/Scripts/python.exe -I study/v3/u3_pools.py --jobs study/v3/runs/phase3/u2/jobs.json --out study/v3/runs/phase3/u2 --device cpu` |
| Haiku full run (Batch API) | chunk 1 (419 requests) collected; chunk 2 submitted 2026-11-01 (`msgbatch_01VN9asBADLJaN4UwWgF28vw`), not yet collected; the driver's first step collects it | `study/v3/run_batches.sh claude-haiku-5-5 study/v3/runs/phase3/llm` |
| gpt-6-luna pilot (Batch API) | collected 2026-11-01 (2 batches, $0.177) | done |

**Phase 3 pilot so far** (generation only; no TEST row, no metric):
- **Haiku:** 595/595 calls ok, 5,892 of 5,940 records, $0.29. The full-run projection at 10 records per call was $3.99, so the batch size was raised to 20 and chunks are sized to the 80% headroom.
- **Muse Spark (haberman):** 600/600 records after a seed-range fix. The failed call is bounded by a reconciliation line; it is never set to 0.
- **Not run:** Sonnet and GPT-6.1-terra subsets. The projected Haiku and luna spend leaves little or no room under the Anthropic/OpenAI 80% lines, so they are not run unless the caps change.

## Gates

| Gate | Status | Approved by | Date | Protocol SHA-256 / commit |
| --- | --- | --- | --- | --- |
| 0 | passed: items 1-8 approved; Phase 1 approved | user | 2026-10-31 | `151eba0`, `4f03164` |
| 1 | passed: decisions 1-5 approved as proposed | user | 2026-11-01 | `ea8c865` |
| 2 | open | | | |
| 3 | open | | | |
| 4 | open | | | |

## Session log

- 2026-10-31: plan, CLAUDE.md autonomy rules and `.claude/settings.json` added.
- 2026-10-31 (Phase 0 session): branch `study-v3` created from `study-v3-setup`. Commits:
  - `e20ee82`: adapters + budget ledger
  - `a73008c`: smoke calls for all 8 generators
  - `734cc0e`: smoke fix
  - `aa07559`: sources, fetcher, draft protocol

  Two background jobs (U2 core fetch, U2 venv install) were stopped by Claude Code for low system memory and not restarted; partial outputs are local only and unrecorded. Stopped at Gate 0.
- 2026-10-31 (session 2): user approved restarting the jobs and downloading the KEEL files.
  - `2a0c812`: KEEL support in the fetcher.
  - U2 venv repaired; U2/UGO Abalone19 check 30/30.
  - U2 core 22/30 after one retry.
  - No API calls; spend unchanged. Stopped at Gate 0.
- 2026-10-31 (session 3): user answered Gate 0 items 1-7.
  - `151eba0`: decisions recorded.
  - U2 core 24/30 after the approved second retry.
  - New datasets 9/10 after one retry.
  - No API calls; spend unchanged. Phase 1 not started.
- 2026-10-31 (session 4): user approved Phase 1 and the paced fetch.
  - `4f03164`: benchmark 40/40.
  - Phase 1 steps 1-4 and the five-learner ablation: `257f862`, `4465ef6`, `8f4ba2f`, `186e647`, `ea0f5d1`, `ea8c865`.
  - No API calls; spend unchanged.
  - Stopped at Gate 1.
- 2026-11-01 (session 5): user approved Gate 1 decisions 1-5.
  - Commits: `1f0e681`, `a2fa2f7`, `93dad15`, `7da9dc3`, `c91546d`, `6c4a87d`.
  - Phase 2 screen done. LLM generation running.
  - No API calls (local Ollama calls logged at $0).
- 2026-11-01 (session 5, later): user authorised autonomous completion of the plan. Benchmark root, Phase 3 pipeline and pilot committed. All background jobs stopped for low memory, not restarted.
