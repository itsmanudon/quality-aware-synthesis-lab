# Study v4: paused checkpoint (2026-11-09) and how to resume

Paused at the user's request with nothing running. Read `PLAN.md`, then `STATUS.md`, then this.

## Where it stopped

- **Phase 1 (Part A audit) is complete**: 200/200 units plus a 200/200 precision check;
  report in `report/phase1/summary.md` (commit `68a320c`).
- **Gate 1 is open.** The user has not answered the three Part B decisions yet:
  1. size limit: Part B only on datasets with outer TRAIN <= 50,000 rows (37 of 40; kick,
     GiveMeSomeCredit and creditcard excluded), declared before any result;
  2. method set: (A) 16 methods (real-k reference; for each of 6 generators random-k and
     gate + quality-coverage-k; a discriminator-realism filter on the 3 LLM pools), about
     1-1.5 days; or (B) about 29 methods, about 2 days;
  3. learners: logistic regression, random forest, XGBoost (MLP and SVM dropped).
- Next after the answers: write Part B (`study/v4/partb.py`), run it on VALIDATION only,
  then freeze `study/v4/protocol.json` (SHA-256 in STATUS) before any TEST metric.
- Human labels stay deferred. The v3 blinded sample has interim AGENT labels only
  (`study/v3/report/phase2/label-sample/agent/`); never copy them into a human column.

## Resume on this Windows laptop

Everything is in place. Start Claude Code in the repo, say "resume Study v4 at Gate 1",
and answer the three decisions. Long runs are launched outside Claude Code (as in
`run_phase1.ps1`) so low-memory reaping cannot stop them. Keep Docker/WSL and Ollama off
while they run.

## Resume on the MacBook Pro (M4 Pro, 48 GB)

Worth it only if the Mac will be free for 1-2 days; this workload is CPU-bound (scikit-learn,
XGBoost) and needs no GPU. **Run all of Part B (VALIDATION and TEST) on one machine**: random
forest and XGBoost can differ in the last decimals across platforms, so mixing machines
inside one stage is not allowed.

1. Code: `git clone` the repo and `git checkout study-v3` (Study v4 lives on this branch).
2. Main environment (Python 3.12): `uv venv --python 3.12 .venv && uv pip install -e '.[dev]'`.
3. Gitignored data to copy from the Windows laptop (by external drive or a private cloud
   folder; never a public link):
   - `study/v3/runs/` (about 0.9 GB): benchmark root, LLM pools, U2 units, curated units.
     Needed by Part B.
   - `study/v4/runs/` (about 2 MB): Phase 1 audit units (only for re-running the report).
   - `.env` stays on the machine that has it; no API call is planned in Study v4.
4. U2 environment: clone ml_ugo and pin commit `a6710ea760497e91d48c77abda0178b67e250adc` into
   `study/v3/vendor/ml_ugo`; create `study/v3/vendor/.venv-u2` with torch, pandas 3,
   scikit-learn 1.6, xgboost, liac-arff, openml (Part B only needs it if it reuses
   `u3_eval.py`).
5. Windows-only paths to adapt: `.venv/Scripts/python.exe` -> `.venv/bin/python` in
   `study/v3/eval_worker.sh`, `study/v3/curate_worker.sh`; the `.ps1` launchers become a
   `nohup ... &` shell loop. `study/v3/claims.py` already handles macOS.
6. Check before any run: `pytest -q study/v3/tests`, `ruff check study/`, and verify that
   `study/v4/report/phase0/inputs.json` SHA-256s match the copied `study/v3/runs/` files.
