# Exploratory addenda

**Exploratory, declared after the main study.** Nothing here enters the canonical
Empirical v2 tables, protocol-v1, run-v2/report-v3 or the approved manuscript. Each
addendum was declared in a settings file committed before any score was computed and
was executed once. Tests are exploratory, without multiplicity adjustment or
significance claims.

| Version | Settings | Results | What it asks |
| --- | --- | --- | --- |
| [v1](v1/README.md) | [addendum-v1.json](v1/addendum-v1.json) | [summary](v1/report/summary.md), [results.csv](v1/report/results.csv) | Six further KEEL datasets under the fresh-split design; a minority quota set to the TRAIN class ratio; an equal-budget B2 comparison |
| v2 | [addendum-v2.json](v2/addendum-v2.json), [brief](v2/brief.md) | [summary](v2/report/summary.md), [results.csv](v2/report/results.csv), [paper tables](v2/report/tables) | Quality-coverage against re-implemented CLLM-style and discriminator-realism curators and four imbalanced-learn oversamplers, on the same splits and pools |

Code: `src/rcqasyn/empirical/addendum.py` (v1) and `addendum_v2.py` (v2), run by
`scripts/run_exploratory_addendum.py` / `_v2.py` and summarized by
`scripts/report_exploratory_addendum.py` / `_v2.py`. Reproduction steps, including the
frozen SOURCE worktree and `scripts/restore_source_bytes.py`, are in the
[v1 README](v1/README.md); v2 uses the same steps with its own scripts.

Raw KEEL files and the large per-split evidence (generation, predictions, replication)
are local and ignored by git. The IEEE draft (`paper/rcqasyn-ieee`) reports both
addenda in a separate subsection.
