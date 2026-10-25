# RC-QASyn: Risk-Calibrated Quality-Aware Synthetic Dataset Construction

RC-QASyn is a research prototype for constructing tabular synthetic datasets from
traceable evidence, explicit admission decisions, bounded repairs and coverage-aware
selection. All six engineering phases and **Empirical v2 are complete**.

**Start here:** [canonical manuscript PDF](paper/rcqasyn-empirical-v2/main.pdf)
([editable LaTeX](paper/rcqasyn-empirical-v2/main.tex)),
[empirical report](artifacts/reports/empirical-v2/report-v3/report.md),
[reproduction guide](docs/REPRODUCE_EMPIRICAL_V2.md),
[repository map](docs/REPOSITORY_GUIDE.md).

## Motivation and contributions

A record can satisfy a schema yet provide weak coverage, repeat existing records or
reduce downstream utility. RC-QASyn keeps structural compliance, statistical concern,
uncertainty and dataset contribution distinct so that construction decisions can be
audited. Its contribution is empirical integration with explicit limits:

1. **Source-bound evidence:** preserved candidate occurrences, dataset specifications
   and TRAIN-only heterogeneous evidence retain their provenance. See the
   [Phase-2 workflow](docs/phase2-research-workflow.md) and
   [Phase-3 evidence methods](docs/phase3-m2-methods.md).
2. **Explicit admission and construction:** descriptive fusion and provisional
   admission feed four matched-budget selectors, with coverage and redundancy
   reported separately. See [fusion/admission](docs/phase4-m4-m5-methods.md) and
   [construction](docs/phase5-m7-coverage-methods.md).
3. **Bounded repair with lineage:** eligible integer defects can be repaired and
   revalidated without inventing missing labels or features; parent records remain
   preserved. See [repair and utility methods](docs/phase6-m6-m9-methods.md).
4. **Reproducible comparative evidence:** external training baselines, five fresh
   offline splits per dataset, saved predictions and paired bootstrap intervals expose
   mixed and negative results. See the [pre-scoring protocol](docs/empirical-v2/protocol.md)
   and [canonical run manifest](artifacts/reports/empirical-v2/run-v2/manifest.json).

## Six-phase architecture

| Phase | Implemented role |
| --- | --- |
| 1: generation/evaluation | One persisted candidate pool; B1 accepts parseable candidates, B2 deterministic rules, B3 one judge; split and utility contracts |
| 2: provenance/specification | Occurrence crosswalks, source declarations, dataset specifications and review provenance |
| 3: heterogeneous evidence (M2) | Structural, local and global statistical evidence with availability and limitations |
| 4: fusion/admission (M4/M5) | Descriptive dependent fusion, explicit refusal of unsupported calibration and provisional admission policies |
| 5: construction (M7) | Source order, farthest first, coverage greedy and quality-coverage selection using TRAIN geometry |
| 6: repair/utility (M6/M9) | Bounded repair, revalidation, parent exclusivity, matched-budget construction and downstream evaluation |

Empirical v2 extends the evaluation across these phases. Fusion scores are
uncalibrated descriptive indices; a provisional pass does not establish semantic validity.

## Datasets and experimental scope

| KEEL dataset | Source rows | Historical candidate occurrences | Features |
| --- | ---: | ---: | --- |
| Abalone19 | 4,174 | 200 | 7 numerical, 1 categorical |
| Ecoli4 | 336 | 201 | 7 numerical |
| page-blocks0 | 5,472 | 200 | 10 numerical |

Source declarations and acquisition details are in [dataset documentation](docs/datasets.md)
and [source manifests](data/manifests). The historical study uses the original splits
and generated candidates. The fresh study uses five stratified 80/20 splits per dataset
with TRAIN-only SMOTENC, SMOTE or RandomOverSampler pools as declared in the protocol.
It is an **offline curation study**, not a repetition of the original LLM generation campaign.

## Key results

| Observation | Saved evidence |
| --- | --- |
| 601 historical occurrences; 75 structural violations; 54 eligible repairs, all structurally repaired; 21 ineligible | [Repair summary and records](artifacts/reports/phase6/core-v1/repairs/artifact.json) |
| 894 utility comparisons: 678 successful, 216 explicitly unavailable; all 138 historical utility rows replay | [Run manifest](artifacts/reports/empirical-v2/run-v2/manifest.json), [complete results](artifacts/reports/empirical-v2/run-v2/results.csv) |
| 15 fresh split populations; five per dataset, with every split retained | [Populations](artifacts/reports/empirical-v2/run-v2/populations.json), [split summary](artifacts/reports/empirical-v2/run-v2/split-summary.json) |
| 216 endpoint intervals and 168 paired-difference intervals from 2,000 stratified resamples | [Endpoint intervals](artifacts/reports/empirical-v2/run-v2/bootstrap.json), [paired differences](artifacts/reports/empirical-v2/run-v2/paired-differences.json) |
| Page-blocks0 historical logistic pure-TSTR F1 falls from 0.4464 to 0.3421 after repair-pool expansion and reselection | [Utility rows](artifacts/reports/empirical-v2/run-v2/results.csv), [paired intervals](artifacts/reports/empirical-v2/run-v2/paired-differences.json) |
| Fresh-split logistic F1, mean ± sample SD: Ecoli4 real 0.848 ± 0.119 vs curated augmentation 0.758 ± 0.166; page-blocks0 real 0.728 ± 0.026 vs curated 0.738 ± 0.028 | [Five-split report](artifacts/reports/empirical-v2/report-v3/report.md) |

Coverage and redundancy gains do not imply uniform utility gains. Classical training
baselines and candidate curation answer different questions; unavailable comparisons
and their reasons are retained in the evidence.

## Inspect results first

Reading the paper and saved results needs no raw datasets, model fitting or paid API
calls. From the repository root in PowerShell:

```powershell
Get-Content artifacts/reports/empirical-v2/report-v3/report.md
Get-Content artifacts/reports/empirical-v2/run-v2/manifest.json
Get-Content -Raw artifacts/reports/empirical-v2/run-v2/results.json | ConvertFrom-Json |
    Group-Object status | Select-Object Name, Count
```

For experiments and tests, use **Python 3.12** (`>=3.12,<3.13`), Git and the declared
dependencies. A fresh Windows environment can be installed with:

```powershell
py -3.12 -m venv .venv
& .venv/Scripts/python.exe -m pip install -e '.[dev,research]' -r configs/empirical/requirements.txt
```

Raw KEEL `.dat` files are external, ignored inputs. Restore exact files at the registry
paths and verify their SHA-256 values before execution. Do not regenerate or overwrite
the committed manifests. The [reproduction guide](docs/REPRODUCE_EMPIRICAL_V2.md)
provides source hashes, the required frozen SOURCE checkout, fresh output destinations,
report/paper build instructions and test commands. Full execution requires these local
inputs; saved-result inspection does not.

## Tests and reproducibility status

The Empirical v2 engineering freeze is
`359b004f7a0f8b3702c3729607786e09de0ac263`: **1,824 tests passed, 14 known warnings**;
20 focused empirical tests and 33 source/replay smoke tests passed. Maintained-code
Ruff, Pyright and diff checks passed. Release verification matched 609 replay output
hashes and 1,565 protected historical files. This documentation revision reuses that
full-suite evidence; executable source and scientific inputs are unchanged.

The earlier [verification archive](artifacts/reports/empirical-v2/verification-v1)
records 1,815 tests before the nine release-compatibility tests were added. Its original
logs remain preserved; the [repository guide](docs/REPOSITORY_GUIDE.md) distinguishes
that archive from the merged engineering freeze.

## Navigation and historical versions

- [Repository guide](docs/REPOSITORY_GUIDE.md): modules, configurations, tests and evidence.
- [Manuscript landing page](paper/README.md): canonical paper, sources and build instructions.
- [Earlier six-phase manuscript](paper/rcqasyn-final-draft/main.pdf) and
  [historical v0.1 source](paper/main.tex): retained earlier versions.
- [Original candidate streams](artifacts/runs), [Phase-6 report](artifacts/reports/phase6/report-v2/report.md)
  and [historical review material](docs/human-review.md): preserved provenance.

## Scientific limits and status

The system establishes neither independent semantic validity nor validity calibration.
Human-label experiments and validity calibration are outside the active paper scope.
Historical TEST reuse, value overlap, small positive counts and overlapping fresh
holdouts limit inference. Bootstrap intervals condition on fitted models and observed
TEST strata; split SD measures a different source of variation. Offline page-blocks0
replication preserves integer structure through resampling and adds no new support.

Engineering and Empirical v2 are complete. Author identities, affiliations, CRediT,
funding, conflicts, ethics/venue declarations and final scientific acceptance require
human decisions. No publication acceptance or state-of-the-art superiority is claimed.
