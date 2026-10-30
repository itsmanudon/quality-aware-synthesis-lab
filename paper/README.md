# RC-QASyn manuscript

The single maintained manuscript is the IEEE conference version in
[`rcqasyn-ieee`](rcqasyn-ieee): [PDF, 18 pages](rcqasyn-ieee/main.pdf) and
[LaTeX](rcqasyn-ieee/main.tex). It contains:

- the four authors and their affiliation, with Priyanka Bhatt marked as reviewer and
  supervisor;
- the Empirical v2 study and, in a separate subsection, the two exploratory addenda
  ([sections/04b-addendum.tex](rcqasyn-ieee/sections/04b-addendum.tex), with
  [generated tables](rcqasyn-ieee/tables/addendum) copied from
  [addendum/v2/report/tables](../addendum/v2/report/tables));
- seven multi-panel figures drawn from saved evidence by
  [`scripts/build_ieee_figures.py`](../scripts/build_ieee_figures.py) (read-only; run
  it from the repository root inside the venv to redraw them);
- the institute's declarations, last in the paper
  ([sections/07-declarations.tex](rcqasyn-ieee/sections/07-declarations.tex)).

Numerical sources are [run-v2](../artifacts/reports/empirical-v2/run-v2/manifest.json),
[report-v3](../artifacts/reports/empirical-v2/report-v3/report.md) with its
[cell ledger](../artifacts/reports/empirical-v2/report-v3/table-evidence.json), and the
addendum reports, under the [pre-scoring protocol](../docs/empirical-v2/protocol.md).
Academic acceptance remains a human decision.

## Build

Use any TeX distribution that provides `IEEEtran`, for example from the repository
root:

```bash
cd paper/rcqasyn-ieee
pdflatex main && bibtex main && pdflatex main && pdflatex main
```

Build in a copy if you do not want to replace the committed `main.pdf` and
`main.bbl`. For Overleaf, upload the folder's files (without `main.pdf`), set the
compiler to pdfLaTeX and the main document to `main.tex`. Overleaf edits do not
return to this repository on their own.

## Earlier manuscripts

The Empirical v2 manuscript, the six-phase draft and the v0.1 draft were removed from
the working tree on 2026-10-31. They remain in git history; the last commit that
contains them is `18d8d6b`, for example
`git worktree add ../rcqasyn-old-papers 18d8d6b`.
