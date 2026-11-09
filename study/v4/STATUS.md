# Study v4 status

Updated by the agent at the end of every session. Gates are approved only by the user.

| Field | Value |
| --- | --- |
| Phase | 1 complete; at **Gate 1** (findings + Part B decisions for the user) |
| Last finished step | Audit 200/200 and precision check 200/200 (`report/phase1/summary.md`): LLM pools valid but separable from real minority (discriminator AUC 0.98, unchanged after equal rounding), 12-16% coverage; gate admits 80-84% |
| Runs in progress | none |
| API spend so far | $0 (no new calls; all LLM pools reused from Study v3) |
| Blockers | none |
| Next step | PAUSED 2026-11-09 at Gate 1 (user). Resume per `study/v4/RESUME.md`: answer the 3 Part B decisions, then Phase 2 on VALIDATION |

## Gates

| Gate | Status | Approved by | Date | Commit / SHA-256 |
| --- | --- | --- | --- | --- |
| 0 | scope approved (directions 1 and 2); size limit and Part B design pending Gate 1 | user | 2026-11-09 | |
| 1 | open | | | |
| 2 | open | | | |
| 3 | open | | | |
| 4 | open | | | |

## Session log
- 2026-11-09: paused at Gate 1 at the user's request; nothing running. Checkpoint and resume steps (this laptop or the MacBook Pro) in `RESUME.md`.

- 2026-11-09: compute decision (user): everything runs on the local laptop (solar powered), no cloud spend. Deferred v3 kick/creditcard units, if ever run, also run locally, after parallelising U2's alpha/tau grid within a split (results-identical, fixed seeds).
- 2026-11-09: interim AGENT labels for the v3 blinded sample (`study/v3/report/phase2/label-sample/agent/`, rules in `study/v3/agent_labels.py`): 9 of 105 flagged invalid (Abalone19 5, abalone9-18 2, vehicle0 2). An automated judge, never human validation; no human_* column filled; rules not to be tuned. Human labelling deferred until results are good (user).

- 2026-11-09: Study v4 opened after Study v3 closed (negative result). Human labelling of
  the v3 blinded sample handed to the user (`study/v3/report/phase2/label-sample/blind/`).
