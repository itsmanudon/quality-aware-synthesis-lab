# RC-QASyn empirical revision - supervisor handoff

> Historical pre-merge handoff. Empirical v2 was subsequently merged, pushed and
> engineering-frozen at `359b004f7a0f8b3702c3729607786e09de0ac263`, with 1,824
> passing tests / 14 warnings. See [current release status](../REPOSITORY_GUIDE.md)
> and the [current reproduction guide](../REPRODUCE_EMPIRICAL_V2.md) for frozen SOURCE
> setup and separate report/paper output paths. Original handoff text is retained below.

**RC-QASyn EMPIRICAL REVISION COMPLETE - UPDATED MANUSCRIPT READY FOR SUPERVISOR REVIEW**

Branch: `research/empirical-evidence-v2`.
Worktree: `D:/Github Repos/quality-aware-synthesis-lab-empirical`.
Frozen main: `244a9bfd490a03a35c4be5cb3b83354e425795fc` (unchanged and clean).
The exact final delivery SHA accompanies this handoff in the chat; `git rev-parse
HEAD` identifies it without embedding a self-referential commit ID in this file.
No push or merge has been performed.

## Completed evidence and deliverables

| Deliverable | Location |
| --- | --- |
| Pre-scoring protocol | `docs/empirical-v2/protocol.md`; commit `91619f1` |
| Machine matrix and pinned additions | `configs/empirical/protocol-v1.json`, `requirements.txt` |
| Canonical evidence | `artifacts/reports/empirical-v2/run-v2/manifest.json` |
| Historical and fresh-split utility | `run-v2/results.json`, `results.csv` |
| Exact populations, class counts, overlap | `run-v2/populations.json` |
| Fresh generated payloads, fit identities, evidence | `run-v2/generation/`, `replication/` |
| Predictions with row/class/score identity | `run-v2/predictions/*.json.gz` |
| Five-split mean and sample SD; both models | `run-v2/split-summary.json` |
| Bootstrap estimates, bounds, counts | `run-v2/bootstrap.json` |
| Primary paired method-difference intervals | `run-v2/paired-differences.json` |
| Exact stratified paired resamples | `run-v2/bootstrap-*.npy.gz` |
| Consolidated ablation matrix | `report-v3/consolidated-ablations.csv` and JSON |
| Random-selection mean/SD | `report-v3/random-selection-summary.json` |
| Selected-set structural compliance | `report-v3/selection-structural-compliance.csv` |
| Split-wise paired comparisons | `report-v3/split-paired-differences.json` |
| All successful confusion counts and Wilson recall | `report-v3/confusions.csv` |
| External baselines | `run-v2/results.csv`; manuscript Table 3 |
| Unavailable method/type comparisons | `run-v2/unavailable.json`; utility reasons also in results |
| Readable evidence summary | `report-v3/report.md` |
| Revised PDF | `paper/rcqasyn-empirical-v2/main.pdf` (13 A4 pages) |
| Editable LaTeX and tables | `paper/rcqasyn-empirical-v2/main.tex`, `sections/`, `tables/` |
| Editable architecture | `paper/rcqasyn-empirical-v2/figures/architecture.tex` |
| Statistical figures | `figures/coverage.{pdf,png}`, `figures/repeated-f1.{pdf,png}` |
| Bibliography / source-access notes | `references.bib`, `notes/references-verified.json` |
| Cell provenance and claims | `notes/table-evidence.json`, `notes/claim-ledger.json` |
| PDF verification | `notes/compilation.json`; `verification-v1/latex-engine.txt` |
| Regression/static/dependency evidence | `verification-v1/` |
| Historical-byte snapshot / final recheck | `verification-v1/historical-integrity*.json` |
| Exact replay comparison | `verification-v1/replay.json` |

Paths beginning `run-v2`, `report-v3` or `verification-v1` above are under
`artifacts/reports/empirical-v2/`. Figure and notes paths are within the new paper.
Earlier report versions remain recorded. The development run and full replay
stay local and ignored; their status and the retained metadata correction are
documented in `run-status.md`. No historical Phase-1--6 artifact was overwritten.

## Results and scientific interpretation

- The 601 historical occurrences contain 75 structural rejects (12.48%), including
  64/200 page-blocks0 records (32%). All 54 repair-eligible records become
  structurally complete; 21 remain ineligible. No labels/features are fabricated.
- All 138 frozen utility rows reproduce within 1e-12, including their 24 unavailable
  cases. All 159 new constructions reach their declared budgets.
- The expanded matrix has 894 utility rows: 678 successful and 216 unavailable;
  no model-execution failures. Eighteen further method/type incompatibilities
  are recorded separately, not dropped.
- Fifteen legitimate fresh split-specific runs (five per dataset) regenerate
  candidates and refit evidence from TRAIN only. They are offline curation
  experiments, with overlapping holdouts, not independent LLM replications.
- There are 216 endpoint intervals and 168 paired-difference intervals from
  2,000 stratified TEST resamples. Saved confusion counts preserve every denominator.
- Coverage/redundancy improve over source order in several historical comparisons,
  but stronger admission can reduce available coverage. Utility is mixed.
- Page-blocks0 logistic pure-TSTR F1 falls from .4464 to .3421 with repair-pool
  expansion; paired conditional 95% difference interval [-.1350,-.0739]. AP rises
  slightly, with difference interval [-.0071,.0493]. This is repair plus reselection.
- Fresh-split Ecoli4 logistic F1: real .8476 +/- .1186, curated augmentation
  .7581 +/- .1659. Page-blocks0: real .7284 +/- .0256, curated .7383 +/- .0283,
  admitted random .7409 +/- .0270. These do not support uniform superiority.
- Historical SMOTE page-blocks0 augmentation leaves 46/49 generated records
  structurally noncompliant. They are deliberately unrounded numerical baselines,
  distinct from compliant curation. ROS replication preserves integers but adds
  no new support. SMOTENC handles Abalone19's declared categorical feature.

The revision supports a more convincing **empirical integration contribution**:
controlled simple comparisons, uncertainty, fresh split provenance and explicit
negative findings delimit what the system does. It does not establish a new
mathematical algorithm, state-of-the-art classification, calibrated validity or
complete semantics.

## Exploratory findings, unavailable cases and pending decisions

Historical TEST reuse, feature-value overlap and only four/six positive examples
limit inference. Bootstrap bounds condition on fitted models and observed strata;
perfect observed predictions can give [1,1] intervals. Undefined MCC replicate
counts are retained. Fresh splits overlap, and between-split SD is separate from
conditional bootstrap uncertainty.

Minority-only offline pools make pure TSTR unavailable (180 rows). Historical
source-order pools without minority support account for the remaining unavailable
utility cases. No difficult split was excluded. Plain SMOTE is incompatible with
the mixed-type dataset; distinct SMOTENC comparisons are inappropriate on the
numerical-only datasets. These exclusions have exact reasons in the result files.

New paid LLM generation was not authorized or performed. Independent repeated-split
LLM replication is therefore unavailable; the valid offline experiment answers
a narrower question. Human annotation and validity calibration are **OUT_OF_SCOPE**,
superseding older active-plan language for this paper. Historical review files
and code remain unchanged. No semantic-validity precision/recall/F1 is calculated.

`HUMAN_DECISION_PENDING`: accurate author names/affiliations/CRediT; funding,
conflicts, ethics and venue declarations; final scientific acceptance. The current
PDF preserves these needs and the AI-assistance statement. No pending scientific
choice prevented the approved experiments. This is supervisor-review readiness,
not publication or submission approval.

## Verification

- Full regression: **1,815 passed, 14 warnings**, 661.82 seconds; see
  `pytest-full-correct-source.txt` and corresponding JUnit XML.
- Focused empirical tests: 20 tests (18 statistical/provenance tests plus two
  output/source guards). Final focused output is saved separately.
- Ruff on maintained `src tests scripts`: all checks passed.
- Full Pyright with the existing Python 3.12 environment: zero errors/warnings.
- Deterministic replay: identical substantive fingerprint
  `031ab9b924dc28c2daf67c5c414fcfd84042c2e6caafa3b098db55c1ec348bbd`;
  **all 609 output-file hashes match**. Runtime/revision-bearing manifests differ.
- Canonical integrity: all 609 hashed outputs rechecked, zero mismatches.
- Historical integrity: **1,565 protected original files** match frozen main
  byte-for-byte. The original manuscript and six-phase scientific code are unchanged.
- PDF: 13 A4 pages compiled with installed Tectonic, all pages visually inspected;
  zero overfull boxes or unresolved references/citations. Benign inputenc and
  underfull bibliography warnings remain documented.

The first full test attempt used the new checkout as historical SOURCE, exposing
Windows newline conversion in an archived CSV. Original physical bytes were
restored from frozen main. A subsequent focused audit also correctly rejected
new empirical outputs as unregistered historical additions. The final run uses
the existing documented `P2_SOURCE_ROOT` option to keep frozen SOURCE separate
from new output. No assertion, seal check or inventory rule was weakened. Earlier
failed/interrupted logs remain clearly distinct from the final passing run.

## Exact reproduction commands

Run from the empirical worktree. Keep the frozen source checkout at its exact
base SHA, with the three verified local raw `.dat` files available. Dependencies
were added without upgrading existing packages; the complete environment snapshot
is in `verification-v1/dependencies.txt`.

```powershell
$env:PYTHONPATH = 'D:\Github Repos\quality-aware-synthesis-lab-empirical\src'
$env:P2_SOURCE_ROOT = 'D:\Github Repos\quality-aware-synthesis-lab'
$empiricalPython = 'D:\Github Repos\quality-aware-synthesis-lab\.venv\Scripts\python.exe'
uv pip install --python $empiricalPython --no-deps -r configs/empirical/requirements.txt
& $empiricalPython scripts/run_empirical_study.py --source-root $env:P2_SOURCE_ROOT --output artifacts/reports/empirical-v2/replay-new-v1
& $empiricalPython scripts/report_empirical_study.py --run artifacts/reports/empirical-v2/replay-new-v1 --output artifacts/reports/empirical-v2/report-new-v1 --paper paper/rcqasyn-empirical-v2
& $empiricalPython -m pytest -q
& $empiricalPython -m pytest tests/empirical -q
& $empiricalPython -m ruff check src tests scripts
& $empiricalPython -m pyright --pythonpath $empiricalPython
git diff --check
$env:TECTONIC_CACHE_DIR = 'D:\Github Repos\quality-aware-synthesis-lab-empirical\artifacts\test-tmp\tectonic-cache'
Push-Location paper/rcqasyn-empirical-v2
& $env:CODEX_TECTONIC_PATH --only-cached --untrusted --keep-logs main.tex
Pop-Location
```

Output directories refuse overwrite. A fresh workstation may first need normal
Tectonic resource fetching instead of `--only-cached`. PDF timestamps are not
claimed byte-identical; experiment payloads and prediction/bootstrap files replay
exactly on the recorded environment. Reporting rewrites only the new manuscript's
generated tables/figures, never the archived manuscript.
