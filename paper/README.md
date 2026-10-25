# RC-QASyn manuscripts

## Canonical: Empirical v2

The current professor-review manuscript is **RC-QASyn Empirical v2**:

- [PDF: 13 A4 pages](rcqasyn-empirical-v2/main.pdf).
- [Editable LaTeX](rcqasyn-empirical-v2/main.tex),
  [sections](rcqasyn-empirical-v2/sections), [tables](rcqasyn-empirical-v2/tables)
  and [editable architecture figure](rcqasyn-empirical-v2/figures/architecture.tex).
- [Bibliography](rcqasyn-empirical-v2/references.bib) and
  [verified-reference notes](rcqasyn-empirical-v2/notes/references-verified.json).
- [Table provenance](rcqasyn-empirical-v2/notes/table-evidence.json),
  [claim ledger](rcqasyn-empirical-v2/notes/claim-ledger.json) and
  [compilation/visual-inspection record](rcqasyn-empirical-v2/notes/compilation.json).

Numerical sources are [run-v2](../artifacts/reports/empirical-v2/run-v2/manifest.json)
and [report-v3](../artifacts/reports/empirical-v2/report-v3/report.md), under the
[pre-scoring protocol](../docs/empirical-v2/protocol.md). The manuscript reports mixed
utility effects and conditional uncertainty. Human-label experiments and validity
calibration are outside its active scope. Final author/institutional declarations and
academic acceptance remain human decisions.

## Build the existing manuscript

LaTeX is separate from the Python dependencies. The recorded release compiled with
Tectonic; this environment provides **Tectonic 0.17.0+20260731** through
`CODEX_TECTONIC_PATH`. The command below uses its verified `--outdir` option to keep
build outputs outside the canonical paper. Run from the repository root in PowerShell:

```powershell
$paperSource = (Resolve-Path paper/rcqasyn-empirical-v2).Path
$paperBuild = Join-Path ([System.IO.Path]::GetTempPath()) ('rcqasyn-paper-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $paperBuild | Out-Null
$tectonic = if ($env:CODEX_TECTONIC_PATH) { $env:CODEX_TECTONIC_PATH } else { 'tectonic' }
Push-Location $paperSource
try {
    & $tectonic --untrusted --keep-logs --outdir $paperBuild main.tex
    if ($LASTEXITCODE -ne 0) { throw 'Tectonic build failed' }
} finally { Pop-Location }
Write-Output (Join-Path $paperBuild 'main.pdf')
```

On a fresh machine, install Tectonic separately and put it on PATH; its first build
may fetch TeX resources. With a populated cache, add `--only-cached` and, if needed,
set `TECTONIC_CACHE_DIR` to that existing cache. The release inspection found no
overfull boxes or unresolved references/citations; benign inputenc and underfull
bibliography warnings are recorded. PDF timestamps need not replay byte-for-byte.

To regenerate numerical tables/figures from saved results, use the
[reproduction guide](../docs/REPRODUCE_EMPIRICAL_V2.md). The reporter writes into its
`--paper` destination, so the guide uses a separate copy of the manuscript.

## Preserved earlier versions

| Version | Location | Role |
| --- | --- | --- |
| Empirical v2 | [Current source and PDF](rcqasyn-empirical-v2) | Canonical professor-review revision; external baselines, repeated splits and uncertainty |
| Six-phase draft | [Earlier source](rcqasyn-final-draft/main.tex), [PDF](rcqasyn-final-draft/main.pdf) | Earlier engineering closeout manuscript based on Phase-6 evidence |
| PAPER v0.1 | [Historical source](main.tex), [sections](sections), [notes](notes) | Original proposal/development draft; statements about unimplemented M2+ or pending annotation describe that period |

Earlier tables, figures, references, pitch notes and evidence ledgers remain in place.
Use each version's own evidence map when interpreting its claims. Historical human
review artifacts do not become approved labels through this documentation update.
For current code and evidence navigation, see the [repository guide](../docs/REPOSITORY_GUIDE.md).
