# Study v3 status

Updated by the agent at the end of every session. Gates are approved only by the user.

| Field | Value |
| --- | --- |
| Phase | 0 · Setup — stopped at **Gate 0** (8 of 30 U2 core files unavailable, see Blockers) |
| Last finished step | U2/UGO full check on dev Abalone19 (30/30 cells); KEEL dev files fetched; U2 core fetch + one retry |
| Runs in progress | none |
| API spend so far | Anthropic $0.000153 of $5 · OpenAI $0.000067 of $4 · Meta $0.000212 of $140 (`budget.jsonl`, 9 lines) |
| Blockers | 8 U2 core datasets unavailable after the one allowed retry (OpenML 503/412 rate limiting); a second, slower retry needs approval |
| Next step | User decisions below (1, 2, 3, 6, 7); then close Gate 0 |

## Phase 0 checklist

| Task | State | Evidence |
| --- | --- | --- |
| Environment, baseline tests/lint/types | done | `report/phase0-baseline.md`: 1823 passed; pyright 0; ruff 4 pre-existing findings in protected `artifacts/reports/phase2/agent-labels-v1/` (left untouched) |
| Ollama + three local models | done | `report/phase0-smoke.json`; qwen2.5:7b-instruct pulled; gemma4:e4b needed one recorded retry (first load > 120 s on 8 GB GPU) |
| Anthropic / OpenAI / Meta adapters + budget ledger | done | `providers.py`, `pricing.py`, `budget.py`; 13 offline tests; all 5 API smoke calls returned `{"ok":true}` |
| Declared dataset fetcher | done | `fetch.py`; 7 offline tests (refusal, name check, MD5, empty, SHA-256) |
| U2's 30 datasets + 10 new shortlisted | done (metadata) | `sources.json`, `report/source-metadata.json` |
| U2 core raw files fetched | **22/30** | `report/acquisitions.json`; attempts in `report/u2-core-fetch-attempt{1,2}.jsonl`; 8 unavailable (below) |
| KEEL dev files fetched | done (9/9) | user approved download 2026-10-31; via official-page links; 3 match recorded hashes |
| ml_ugo a6710ea installed read-only, U2/UGO run on a dev dataset | done | `report/u2-dev-check/`: Abalone19, seed 42, 5 classifiers × 6 methods, 30/30 cells, 0 failures |
| Draft `protocol.json` | done | Gate 0 draft; open choices are `null` with the deciding gate |

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
4. ~~Place the six KEEL dev files by hand?~~ — user approved downloading; done (9/9).
5. ~~Restart the two stopped jobs~~ — approved and done (see Session 2 findings).
6. Keep the API caps as declared?
7. Allow a second retry of the 8 unavailable U2 core datasets with slower pacing (e.g. 10 s between requests), outside the one-retry rule? Without it, U2 comparability covers 22/30 datasets.

## Gates

| Gate | Status | Approved by | Date | Protocol SHA-256 / commit |
| --- | --- | --- | --- | --- |
| 0 | awaiting user | | | |
| 1 | open | | | |
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
