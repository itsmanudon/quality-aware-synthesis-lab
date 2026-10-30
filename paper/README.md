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
calibration are outside its active scope. Author names and institutional
declarations are in the IEEE version below; academic acceptance remains a human decision.

## IEEE conference version

[`rcqasyn-ieee`](rcqasyn-ieee) is the IEEE conference-format version of the paper
([PDF, 18 pages](rcqasyn-ieee/main.pdf), [LaTeX](rcqasyn-ieee/main.tex)). Compared
with Empirical v2 it adds:

- the four authors and their affiliation, with Priyanka Bhatt marked as reviewer and
  supervisor;
- shorter prose and seven multi-panel figures drawn from saved evidence by
  [`scripts/build_ieee_figures.py`](../scripts/build_ieee_figures.py) (read-only; run
  it from the repository root inside the venv to redraw them); the bootstrap,
  fresh-split and most addendum tables moved to the appendix;
- a separate subsection reporting the two exploratory addenda
  ([sections/04b-addendum.tex](rcqasyn-ieee/sections/04b-addendum.tex), with
  [generated tables](rcqasyn-ieee/tables/addendum) copied from
  [addendum/v2/report/tables](../addendum/v2/report/tables));
- revised Limitations and Future work, and an abstract and conclusion that mention
  the addendum;
- the institute's declarations, last in the paper
  ([sections/07-declarations.tex](rcqasyn-ieee/sections/07-declarations.tex)).

The addendum results stay out of the canonical tables. The Empirical v2 manuscript
below is unchanged.

Build it with any TeX distribution that provides `IEEEtran`, for example from the
repository root:

```bash
cd paper/rcqasyn-ieee
pdflatex main && bibtex main && pdflatex main && pdflatex main
```

Build in a copy if you do not want to replace the committed `main.pdf` and
`main.bbl`. For Overleaf, upload a zip of the folder (without `main.pdf`), set the
compiler to pdfLaTeX and the main document to `main.tex`. Overleaf edits do not
return to this repository on their own.

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
| IEEE conference | [Source and PDF](rcqasyn-ieee) | Conference-format version of Empirical v2 with authors, the exploratory addenda and declarations |
| Empirical v2 | [Current source and PDF](rcqasyn-empirical-v2) | Canonical professor-review revision; external baselines, repeated splits and uncertainty |
| Six-phase draft | [Earlier source](rcqasyn-final-draft/main.tex), [PDF](rcqasyn-final-draft/main.pdf) | Earlier engineering closeout manuscript based on Phase-6 evidence |
| PAPER v0.1 | [Historical source](main.tex), [sections](sections), [notes](notes) | Original proposal/development draft; statements about unimplemented M2+ or pending annotation describe that period |

Earlier tables, figures, references, pitch notes and evidence ledgers remain in place.
Use each version's own evidence map when interpreting its claims. Historical human
review artifacts do not become approved labels through this documentation update.
For current code and evidence navigation, see the [repository guide](../docs/REPOSITORY_GUIDE.md).
