# Study v3 status

Updated by the agent at the end of every session. Gates are approved only by the user.

| Field | Value |
| --- | --- |
| Phase | 0 · Setup — stopped at **Gate 0** (two tasks incomplete, see Blockers) |
| Last finished step | Draft `protocol.json` committed (`aa07559`) |
| Runs in progress | none (two background jobs were stopped by Claude Code for low system memory; not restarted) |
| API spend so far | Anthropic $0.000153 of $5 · OpenAI $0.000067 of $4 · Meta $0.000212 of $140 (`budget.jsonl`, 9 lines) |
| Blockers | U2 venv install and U2 core fetch need a restart (user go-ahead); 6 KEEL dev files need hand placement |
| Next step | User decisions below; then restart the two jobs, run the U2/UGO dev check, close Gate 0 |

## Phase 0 checklist

| Task | State | Evidence |
| --- | --- | --- |
| Environment, baseline tests/lint/types | done | `report/phase0-baseline.md`: 1823 passed; pyright 0; ruff 4 pre-existing findings in protected `artifacts/reports/phase2/agent-labels-v1/` (left untouched) |
| Ollama + three local models | done | `report/phase0-smoke.json`; qwen2.5:7b-instruct pulled; gemma4:e4b needed one recorded retry (first load > 120 s on 8 GB GPU) |
| Anthropic / OpenAI / Meta adapters + budget ledger | done | `providers.py`, `pricing.py`, `budget.py`; 13 offline tests; all 5 API smoke calls returned `{"ok":true}` |
| Declared dataset fetcher | done | `fetch.py`; 7 offline tests (refusal, name check, MD5, empty, SHA-256) |
| U2's 30 datasets + 10 new shortlisted | done (metadata) | `sources.json`, `report/source-metadata.json` |
| U2 core raw files fetched | **incomplete** | job stopped (low memory) after 27/30 files; no acquisition records written, so treated as not acquired |
| ml_ugo a6710ea installed read-only, U2/UGO run on a dev dataset | **incomplete** | checkout pinned and clean in gitignored `vendor/`; isolated venv only has torch; `u2_bridge.py` written but not yet run |
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

## Decisions requested at Gate 0

1. Use `gpt-6-luna` in place of "GPT-6.1-luna"?
2. Approve the 10 new datasets (and the GiveMeSomeCredit licence), or swap in reserves?
3. Drop page-blocks0 from dev?
4. Place the six KEEL dev files by hand?
5. Restart the two stopped jobs (U2 venv install, U2 core fetch), so the U2/UGO dev check can run?
6. Keep the API caps as declared?

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
