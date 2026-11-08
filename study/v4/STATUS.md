# Study v4 status

Updated by the agent at the end of every session. Gates are approved only by the user.

| Field | Value |
| --- | --- |
| Phase | 1 (audit, inner TRAIN only) |
| Last finished step | audit.py written and trial-checked (oml43, oml1053); full run launched 2026-11-09 with 5 workers outside Claude Code |
| Runs in progress | Part A audit: `study/v4/runs/phase1/units` (200 units planned), logs `study/v4/runs/phase1/worker-*.log`; resume with `study/v4/run_phase1.ps1` |
| API spend so far | $0 (no new calls; all LLM pools reused from Study v3) |
| Blockers | none |
| Next step | When 200 units are done: Phase 1 report (per generator, per dataset, by dataset properties); then Gate 1 with the Part B details |

## Gates

| Gate | Status | Approved by | Date | Commit / SHA-256 |
| --- | --- | --- | --- | --- |
| 0 | scope approved (directions 1 and 2); size limit and Part B design pending Gate 1 | user | 2026-11-09 | |
| 1 | open | | | |
| 2 | open | | | |
| 3 | open | | | |
| 4 | open | | | |

## Session log
- 2026-11-09: interim AGENT labels for the v3 blinded sample (`study/v3/report/phase2/label-sample/agent/`, rules in `study/v3/agent_labels.py`): 9 of 105 flagged invalid (Abalone19 5, abalone9-18 2, vehicle0 2). An automated judge, never human validation; no human_* column filled; rules not to be tuned. Human labelling deferred until results are good (user).

- 2026-11-09: Study v4 opened after Study v3 closed (negative result). Human labelling of
  the v3 blinded sample handed to the user (`study/v3/report/phase2/label-sample/blind/`).
