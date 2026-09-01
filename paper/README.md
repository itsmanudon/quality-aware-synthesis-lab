# RC-QASyn manuscript

This directory contains PAPER v0.1 of **Risk-Calibrated Quality-Aware
Synthetic Dataset Construction**. It is an anonymous, neutral-template draft:
development diagnostics are not final results, human annotation is in progress,
and the proposed M2+ components have not been implemented.

## Build

Use a conventional LaTeX installation with `latexmk`, `pdflatex`, and BibTeX:

```text
cd paper
latexmk -pdf main.tex
```

Clean generated files with:

```text
latexmk -C
```

LaTeX is intentionally not a Python package dependency. The Legion used to
initialize this draft did not have a LaTeX toolchain, so collaborators should
compile after pulling and report actionable warnings rather than suppressing
them.

## File ownership

Keep `main.tex` limited to document setup and section inclusion. Most edits
belong in `sections/`; reusable table and figure sources belong in `tables/`
and `figures/`. The files under `notes/` are manuscript-control records and do
not appear in the compiled paper. In particular,
`notes/future_experiment_tables.tex` preserves detailed experiment-planning
shells that are intentionally excluded from the professor draft.

`PITCH_TLDR.md` is the team briefing for a professor meeting, and
`PITCH_ONE_PAGE.md` is its one-page companion. They summarize the manuscript
but are not evidence sources; update artifact-backed numbers in the manuscript
and evidence map first.

Suggested ownership for concurrent drafting:

- Author A: Introduction, Problem Formulation, and Proposed Framework.
- Author B: Related Work and BibTeX verification.
- Author C: Experimental Methodology, datasets, metrics, and reproducibility.
- Professor or senior author: framing, contribution claims, and final
  methodology review.

Suggested branches are `paper/introduction`, `paper/related-work`, and
`paper/methodology`. Avoid multiple authors rewriting `main.tex`; integrate
section branches with ordinary reviews and resolve scientific wording in the
section file that owns it.

## Evidence discipline

Use committed artifacts and manifests before source/configuration, current
documentation, verified literature notes, and primary papers. Record material
claims in `notes/claim_ledger.md` and their sources in
`notes/evidence_map.md`. Never convert pilot observations into final
superiority or significance claims.
