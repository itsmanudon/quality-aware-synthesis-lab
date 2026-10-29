# RC-QASyn repository guide

Empirical v2 is the canonical research revision. Start with the
[paper PDF](../paper/rcqasyn-empirical-v2/main.pdf),
[readable report](../artifacts/reports/empirical-v2/report-v3/report.md) and
[reproduction guide](REPRODUCE_EMPIRICAL_V2.md). All six engineering phases are
implemented; the M labels below describe components, not six additional phases.

## Implementation and methods

| Area | Code | Methods / configuration |
| --- | --- | --- |
| Phase 1: generation/evaluation and B1/B2/B3 | [generation](../src/rcqasyn/generation), [experiment runner](../src/rcqasyn/experiments/runner.py), [rule/judge baselines](../src/rcqasyn/baselines), [utility metrics](../src/rcqasyn/metrics/utility.py) | [Baseline definitions](baselines.md), [stabilization](phase1-stabilization.md), [experiment configs](../configs/experiments) |
| Phase 2: provenance and dataset specifications | [provenance](../src/rcqasyn/phase2/provenance.py), [specifications](../src/rcqasyn/phase2/specifications.py), [workflow/source protection](../src/rcqasyn/phase2/workflow.py) | [Research workflow](phase2-research-workflow.md), [preserved preparation](../artifacts/reports/phase2/gate-a-v3) |
| Phase 3: M2 heterogeneous evidence | [validators](../src/rcqasyn/phase3/validators.py), [registry](../src/rcqasyn/phase3/registry.py), [workflow](../src/rcqasyn/phase3/workflow.py) | [Methods](phase3-m2-methods.md), [five-config study](../configs/phase3/m2-offline-v1.json) |
| Phase 4: M4/M5 fusion and admission | [fusion](../src/rcqasyn/phase4/fusion.py), [calibration eligibility/refusal](../src/rcqasyn/phase4/calibration.py), [shadow workflow](../src/rcqasyn/phase4/workflow.py) | [Methods](phase4-m4-m5-methods.md), [six-policy configuration](../configs/phase4/m4-m5-shadow-v1.json) |
| Phase 5: M7 construction | [TRAIN geometry](../src/rcqasyn/phase5/geometry.py), [selection](../src/rcqasyn/phase5/selection.py), [workflow](../src/rcqasyn/phase5/workflow.py) | [Methods](phase5-m7-coverage-methods.md), [study configuration](../configs/phase5/m7-study-v1.json) |
| Phase 6: M6 repair / M9 utility | [repair](../src/rcqasyn/phase6/repair.py), [study](../src/rcqasyn/phase6/study.py), [utility](../src/rcqasyn/phase6/utility.py) | [Methods](phase6-m6-m9-methods.md), [study configuration](../configs/phase6/m6-m9-study-v1.json) |
| Empirical v2: external baselines, fresh splits, uncertainty | [study](../src/rcqasyn/empirical/study.py), [offline generation](../src/rcqasyn/empirical/generation.py), [evaluation](../src/rcqasyn/empirical/evaluation.py) | [Protocol](empirical-v2/protocol.md), [machine matrix](../configs/empirical/protocol-v1.json), [pinned additions](../configs/empirical/requirements.txt) |
| Exploratory addenda v1/v2 (declared after the main study) | [addendum v1](../src/rcqasyn/empirical/addendum.py), [addendum v2](../src/rcqasyn/empirical/addendum_v2.py), [runners and reporters](../scripts), [source-byte restore](../scripts/restore_source_bytes.py) | [Index](../addendum/README.md), [v1 settings](../addendum/v1/addendum-v1.json), [v2 settings](../addendum/v2/addendum-v2.json) |

Shared [contracts](../src/rcqasyn/contracts), [interfaces](../src/rcqasyn/interfaces),
[storage](../src/rcqasyn/storage), [dataset services](../src/rcqasyn/datasets) and
[CLI](../src/rcqasyn/cli) support the phases. M4 implements descriptive fusion and
calibration refusal, not calibrated semantic-validity probabilities. M6 implements
the documented bounded integer repair, not every repair/regeneration idea in early plans.

## Data, candidate streams and provenance

- [Dataset registry YAML](../configs/datasets) specifies exact local paths and source
  declarations; [dataset documentation](datasets.md) explains acquisition and leakage rules.
- Acquisition hashes and original split identities are in
  [Abalone19](../data/manifests/Abalone19), [Ecoli4](../data/manifests/Ecoli4) and
  [page-blocks0](../data/manifests/page-blocks0). Raw `.dat` files are ignored local inputs.
- Original campaign bundles are under [artifacts/runs](../artifacts/runs). The historical
  601-occurrence study uses the three `m1-p1-real-*-gemma4-e4b-20260829` bundles:
  [Abalone19 raw candidates](../artifacts/runs/m1-p1-real-Abalone19-gemma4-e4b-20260829/candidates_raw.jsonl),
  [Ecoli4 raw candidates](../artifacts/runs/m1-p1-real-Ecoli4-gemma4-e4b-20260829/candidates_raw.jsonl),
  [page-blocks0 raw candidates](../artifacts/runs/m1-p1-real-page-blocks0-gemma4-e4b-20260829/candidates_raw.jsonl).
  The earlier `m1-p0-real-v3-*` bundles remain separate controls. Do not conflate versions.
- [Human-review documentation](human-review.md) and [Phase-2 proposals](../artifacts/reports/phase2/agent-labels-v1)
  preserve historical review provenance. They are not approved semantic-validity labels.
- [Artifact policy](reproducibility-and-artifacts.md),
  [historical catalog pins](../src/rcqasyn/phase2/historical_outputs.py) and
  [empirical output pins](../src/rcqasyn/phase2/empirical_outputs.py) explain preservation.
  A new directory name alone does not authorize additions to the frozen inventory.

## Canonical evidence

| Question | Current saved source |
| --- | --- |
| What ran, with which protocol, dependencies and hashes? | [run-v2 manifest](../artifacts/reports/empirical-v2/run-v2/manifest.json) |
| Every utility comparison, including unavailable rows | [results.csv](../artifacts/reports/empirical-v2/run-v2/results.csv), [results.json](../artifacts/reports/empirical-v2/run-v2/results.json) |
| Exact populations, overlap and generated pools | [populations](../artifacts/reports/empirical-v2/run-v2/populations.json), [generation](../artifacts/reports/empirical-v2/run-v2/generation), [replication](../artifacts/reports/empirical-v2/run-v2/replication) |
| Selected identities and five-split summary | [constructions](../artifacts/reports/empirical-v2/run-v2/constructions.json), [split summary](../artifacts/reports/empirical-v2/run-v2/split-summary.json) |
| Per-example predictions and uncertainty | [compressed predictions](../artifacts/reports/empirical-v2/run-v2/predictions), [endpoint intervals](../artifacts/reports/empirical-v2/run-v2/bootstrap.json), [paired differences](../artifacts/reports/empirical-v2/run-v2/paired-differences.json) |
| Exact paired resample indices | `bootstrap-Abalone19.npy.gz`, `bootstrap-Ecoli4.npy.gz`, `bootstrap-page-blocks0.npy.gz` inside [run-v2](../artifacts/reports/empirical-v2/run-v2) |
| Readable summary and consolidated ablations | [report-v3](../artifacts/reports/empirical-v2/report-v3/report.md), [ablation matrix](../artifacts/reports/empirical-v2/report-v3/consolidated-ablations.csv) |
| Structural compliance and test denominators | [selection compliance](../artifacts/reports/empirical-v2/report-v3/selection-structural-compliance.csv), [confusions/Wilson recall](../artifacts/reports/empirical-v2/report-v3/confusions.csv) |
| Unavailable method/type comparisons | [explicit ledger](../artifacts/reports/empirical-v2/run-v2/unavailable.json), plus reason fields in all utility rows |

The [exploratory addenda](../addendum/README.md) have their own saved results under
`addendum/v1/report` and `addendum/v2/report`. They are exploratory, declared after
the main study and never merged into the canonical tables above. They sit outside the
protected historical paths, so they do not change the frozen inventory.

The manuscript has its own [cell provenance](../paper/rcqasyn-empirical-v2/notes/table-evidence.json)
and [claim ledger](../paper/rcqasyn-empirical-v2/notes/claim-ledger.json).
Run-v2 is canonical; report-v3 is the current rendering. Earlier report-v1/report-v2
remain preserved. [Run-version notes](empirical-v2/run-status.md) identify development
run-v1 (a metadata defect) and the ignored local replay; neither replaces run-v2.

## Tests and engineering status

[tests](../tests) contains foundation/M1 tests and the [Phase-2](../tests/phase2),
[Phase-3](../tests/phase3), [Phase-4](../tests/phase4), [Phase-5](../tests/phase5),
[Phase-6](../tests/phase6) and [empirical](../tests/empirical) suites.
Source protection includes [historical inventory tests](../tests/phase2/test_historical_inventory.py)
and [release compatibility tests](../tests/phase2/test_empirical_release_inventory.py).
Commands are in the [reproduction guide](REPRODUCE_EMPIRICAL_V2.md).

The merged Empirical v2 engineering freeze is
`359b004f7a0f8b3702c3729607786e09de0ac263`, incorporating approved implementation
`6ca1147d1fda3469702294fc882aa5ab025a7da6` and inventory compatibility fix
`1b1836681856e6ef42ff1cd1e55c90c67060e04e`. Post-merge verification recorded:
1,824 passing tests / 14 warnings; 20 focused empirical tests; 33 source/replay smoke
tests; passing maintained-code Ruff/Pyright/diff checks; 609 matching replay output
hashes; 1,565 unchanged protected historical files; 654 verified output/config registrations.

The committed [verification-v1 archive](../artifacts/reports/empirical-v2/verification-v1)
and [pre-merge handoff](empirical-v2/handoff.md) retain their earlier 1,815-test result.
The nine compatibility tests account for the later 1,824 total. The post-merge release
logs are local delivery evidence rather than files in that sealed archive. This
documentation revision reuses the merged release's full-suite result and checks only
navigation, commands and artifact preservation.

## Manuscripts and historical documents

Use the [manuscript landing page](../paper/README.md) for the canonical Empirical v2
paper, the [IEEE conference version](../paper/rcqasyn-ieee) with the exploratory
addenda, sources, bibliography and build instructions. The
[six-phase draft](../paper/rcqasyn-final-draft) and [v0.1 source](../paper/main.tex)
remain accessible with their own evidence and references.

[Architecture](architecture.md), [milestones](milestones.md) and
[research plan](research-plan.md) preserve early design goals. Their deferred language
does not describe current M2/M4/M5/M7/M6 implementation status. The
[six-phase closeout](rcqasyn-six-phase-closeout.md) describes the period before
Empirical v2. Historical human-review plans remain archived; human-label experiments
and validity calibration are outside this paper's active scope.

All six engineering phases, Empirical v2 and the exploratory addenda are complete.
The IEEE draft carries the authors, affiliations, contributions and the institute's
declarations; venue choice, institutional review and final scientific acceptance
remain separate human decisions.
