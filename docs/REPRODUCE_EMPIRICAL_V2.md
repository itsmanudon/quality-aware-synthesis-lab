# Inspect and reproduce RC-QASyn Empirical v2

Run commands from the repository root in PowerShell. This guide follows the
[pre-scoring protocol](empirical-v2/protocol.md) and the
[historical handoff](empirical-v2/handoff.md), with the merged release's source-root
contract made explicit. It does not require or invoke paid LLM generation.

## 1. Inspect the committed evidence first

No Python environment or raw datasets are needed for these read-only commands:

```powershell
Get-Content artifacts/reports/empirical-v2/report-v3/report.md
Get-Content artifacts/reports/empirical-v2/run-v2/manifest.json
Get-Content -Raw artifacts/reports/empirical-v2/run-v2/results.json | ConvertFrom-Json |
    Group-Object status | Select-Object Name, Count
```

Expected: **894 rows**, with **678 `ok`** and **216 `unavailable`**. Read the
[PDF](../paper/rcqasyn-empirical-v2/main.pdf),
[split summary](../artifacts/reports/empirical-v2/run-v2/split-summary.json),
[endpoint intervals](../artifacts/reports/empirical-v2/run-v2/bootstrap.json) and
[paired differences](../artifacts/reports/empirical-v2/run-v2/paired-differences.json).
The [repository guide](REPOSITORY_GUIDE.md) maps predictions, resample indices,
confusions, construction identities and exclusions. Reading these files reproduces
inspection of the evidence; executing the study additionally needs the inputs below.

## 2. Python and dependencies

The project targets Python `>=3.12,<3.13`; the recorded run used **3.12.11**.
[pyproject.toml](../pyproject.toml) declares runtime packages, `dev` tools and
`research` plotting dependencies. The empirical additions are pinned in
[requirements.txt](../configs/empirical/requirements.txt):
`imbalanced-learn==0.14.2`, `sklearn-compat==0.1.6`.

For a fresh environment:

```powershell
py -3.12 -m venv .venv
& .venv/Scripts/python.exe -m pip install -e '.[dev,research]' -r configs/empirical/requirements.txt
$projectRoot = (Get-Location).Path
$python = Join-Path $projectRoot '.venv/Scripts/python.exe'
$env:PYTHONPATH = Join-Path $projectRoot 'src'
& $python --version
& $python scripts/run_empirical_study.py --help
& $python scripts/report_empirical_study.py --help
```

For an existing validated environment, retain its installed versions. The recorded
[dependency snapshot](../artifacts/reports/empirical-v2/verification-v1/dependencies.txt)
is the reference for exact replay; installing current allowed dependency ranges does
not guarantee identical numerical bytes across environments.

## 3. Restore exact external raw inputs

Raw `.dat` files are ignored and are not supplied by a normal clone. Obtain the
official KEEL archives identified in [dataset documentation](datasets.md) and the
three acquisition manifests below. Preserve extracted bytes, source column spellings
and labels; do not normalize newlines, round values, regenerate splits or overwrite
committed manifests.

| Dataset | Path relative to each SOURCE root | Bytes | Extracted SHA-256 |
| --- | --- | ---: | --- |
| [Abalone19 manifest](../data/manifests/Abalone19/source.json) | `data/raw/abalone19/abalone19.dat` | 252804 | `6aa5b1ffd05eb4c8c74bb07e6bab248cdb4fc327f5f62bb77339097e92bc76fa` |
| [Ecoli4 manifest](../data/manifests/Ecoli4/source.json) | `data/raw/ecoli4/ecoli4.dat` | 17838 | `1890c32ba2550cfe106d0524ebf6a42c2b50730f6521bd4f22eb58e7bda86bcb` |
| [page-blocks0 manifest](../data/manifests/page-blocks0/source.json) | `data/raw/page-blocks0/page-blocks0.dat` | 331362 | `c46bf830740d44bf8d4042b1679424857bcfd770568d2c250f92a91a12d425b2` |

The manifests also record archive URLs, sizes and SHA-256 values. Verify each local
file with `Get-FileHash -Algorithm SHA256 <path>` and compare both hash and byte count
before execution. `rcqasyn datasets inspect <id>` reads the registry and declarations;
acquisition/preparation commands write manifests and are unnecessary for this replay.

## 4. Frozen SOURCE versus the executable checkout

The [study runner](../src/rcqasyn/empirical/study.py) requires SOURCE Git HEAD to equal
**`244a9bfd490a03a35c4be5cb3b83354e425795fc`**. SOURCE supplies the frozen original
datasets and historical provenance; the current checkout supplies the empirical code.
Current merged `main` cannot be substituted for the study's frozen SOURCE argument.

Choose a new local destination outside the repository's protected inventory paths:

```powershell
# Continue in the current checkout with $projectRoot and $python from section 2.
$reproductionRoot = Join-Path (Split-Path $projectRoot -Parent) 'rcqasyn-local-reproduction-v1'
if (Test-Path $reproductionRoot) { throw 'Choose a fresh reproduction directory' }
New-Item -ItemType Directory -Path $reproductionRoot | Out-Null
$frozenSource = Join-Path $reproductionRoot 'source'
git worktree add --detach $frozenSource 244a9bfd490a03a35c4be5cb3b83354e425795fc
if ($LASTEXITCODE -ne 0) { throw 'Frozen SOURCE checkout failed' }
git -C $frozenSource rev-parse HEAD
```

Restore the three verified raw files under `$frozenSource` using the table above.
Keep its tracked files clean (`git -C $frozenSource status --porcelain`). The study
validates source identities and preparation; never bypass a mismatch or weaken
inventory protections. Do not put new runs under `artifacts/reports`, `artifacts/runs`,
`data`, `configs`, `prompts` or `test-results`: unknown additions there can invalidate
the historical source inventory.

## 5. Optional full offline study into a fresh destination

This fits models and regenerates offline candidate pools; it is unnecessary for
reading the existing results. It does not repeat the original LLM campaign.

```powershell
$newRun = Join-Path $reproductionRoot 'run-v1'
& $python scripts/run_empirical_study.py --source-root $frozenSource --output $newRun
if ($LASTEXITCODE -ne 0) { throw 'Empirical study failed' }
Get-Content (Join-Path $newRun 'manifest.json')
```

The destination must not already exist. Expected outputs include `results.json/.csv`,
`constructions.json`, `populations.json`, `split-summary.json`, `historical-replay.json`,
`unavailable.json`, `generation/`, `replication/`, compressed `predictions/`,
`bootstrap.json`, `paired-differences.json` and `bootstrap-*.npy.gz`.
The canonical manifest records all 138 historical rows matching, 15 fresh split
populations, 894 utility rows and 609 hashed output files. Compare substantive output
hashes/fingerprints with [run-v2](../artifacts/reports/empirical-v2/run-v2/manifest.json);
runtime and revision-bearing manifest fields can differ. Keep a failed or partial
destination for diagnosis and choose another fresh destination for a retry.

## 6. Render saved results and build a separate paper copy

The [reporter](../scripts/report_empirical_study.py) reads saved evidence and never
fits a model, but **writes generated tables, figures and notes into `--paper`**.
Use a separate paper copy and fresh report directory. This example reads the canonical
run; set `$reportInput = $newRun` to inspect an optional new execution instead.

```powershell
$reportInput = Join-Path $projectRoot 'artifacts/reports/empirical-v2/run-v2'
$newReport = Join-Path $reproductionRoot 'report-v1'
$paperCopy = Join-Path $reproductionRoot 'paper-copy'
if ((Test-Path $newReport) -or (Test-Path $paperCopy)) { throw 'Choose fresh report/paper paths' }
Copy-Item -LiteralPath (Join-Path $projectRoot 'paper/rcqasyn-empirical-v2') -Destination $paperCopy -Recurse
& $python scripts/report_empirical_study.py --run $reportInput --output $newReport --paper $paperCopy
if ($LASTEXITCODE -ne 0) { throw 'Report rendering failed' }
```

Expected: `report.md`, consolidated ablations, selection compliance, random-selection
summary, paired split differences, confusions and a report manifest; the copied paper
receives generated tables/figures and their cell-evidence ledger. The supplied
manuscript's prose is preserved. Tectonic builds the copy without Python dependencies:

```powershell
$tectonic = if ($env:CODEX_TECTONIC_PATH) { $env:CODEX_TECTONIC_PATH } else { 'tectonic' }
Push-Location $paperCopy
try {
    & $tectonic --untrusted --keep-logs main.tex
    if ($LASTEXITCODE -ne 0) { throw 'Tectonic build failed' }
} finally { Pop-Location }
```

The release used installed Tectonic; see the [paper build guide](../paper/README.md)
for cache behavior and a separate output-directory build. Original paper versions,
canonical run-v2 and report-v3 must remain unchanged.

## 7. Focused and full tests

Tests use `P2_SOURCE_ROOT`, which is separate from the study's `--source-root` contract.
The merged release supports the **current checkout** as test SOURCE through exact
approved-output registrations. Restore the same three raw files under `$projectRoot`
for source-derived tests, and leave protected paths free of unregistered outputs.

```powershell
$env:P2_SOURCE_ROOT = $projectRoot
$env:PYTHONPATH = Join-Path $projectRoot 'src'
& $python -m pytest tests/empirical -q
& $python -m pytest tests/phase2/test_historical_inventory.py tests/phase2/test_empirical_release_inventory.py tests/phase6/test_results.py::test_actual_source_derived_audit_without_model_fit -q
# Full suite: run when executable code or scientific inputs change.
& $python -m pytest -q
& $python -m ruff check src tests scripts
& $python -m pyright --pythonpath $python
git diff --check
```

At engineering freeze `359b004f7a0f8b3702c3729607786e09de0ac263`: full suite
**1,824 passed / 14 warnings**, focused empirical **20 passed**, source/replay smoke
**33 passed**, Ruff/Pyright/diff passed. This docs-only reconciliation reuses that
full-suite evidence. The preserved [verification archive](../artifacts/reports/empirical-v2/verification-v1)
predates nine compatibility tests and records 1,815; see the
[release-status explanation](REPOSITORY_GUIDE.md).

## Interpretation limits

Historical TEST reuse, feature-value overlap and small positive counts limit inference.
Five fresh holdouts per dataset overlap and are not independent LLM replications.
Offline pools contain only minority records, making pure TSTR unavailable for that
track. Page-blocks0 replication uses RandomOverSampler and adds no novel support.
Bootstrap intervals are conditional on observed TEST strata and fitted models;
between-split sample SD measures different variation. Utility effects are mixed.
No human-label experiment, semantic-validity calibration or publication acceptance
is established by replay. Final academic declarations and acceptance remain pending.
