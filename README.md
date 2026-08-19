# RC-QASyn: Risk-Calibrated Quality-Aware Synthetic Dataset Construction

## Research problem

Synthetic records can satisfy a narrow schema while still carrying factual, logical,
privacy, fairness, distributional, or downstream-utility problems. RC-QASyn studies how
to make those different properties visible and traceable when constructing a dataset.

## Core thesis / hypothesis

The working hypothesis is that independent, heterogeneous evidence with calibration and
explicit risk-aware actions can support more reliable synthetic-data decisions than a
single aggregate quality score. This is a proposed research direction, not a result or
novelty claim.

## Current scope

Milestone 0.1 provides typed contracts, protocol interfaces, configuration, storage,
literature inventory, reproducibility metadata, tests, and a small CLI. It contains no
real ML/LLM pipeline, API calls, RAG, generation, evidence-fusion implementation,
repair, learned controller, dataset download, web/API/server, or fake validator.

## Separation from imbalance-synthesis-lab

RC-QASyn is an independent package and has no runtime dependency on
`imbalance-synthesis-lab`. Any future comparison is an explicitly documented experiment,
not an implicit code or data dependency.

## Eventual architecture

`Specification → Generation → Independent Validators → Evidence Fusion → Risk-Aware
Controller → Repair/Revalidate/Regenerate → Dataset Optimizer → Audit → Downstream Utility`

The stages are future extension points behind the contracts; M0.1 does not implement
them.

## Module philosophy

Contracts are strict, typed, serializable, versioned, and provenance-aware. Interfaces
are Protocols only, while test doubles remain in tests. Storage is deterministic and
atomic. Random IDs, content IDs, and named cryptographic seed derivation are distinct
reproducibility concepts.

## Quality vs risk vs uncertainty

Quality asks whether a specified property is satisfied. Risk asks about the consequence
of accepting a candidate or dataset. Uncertainty records confidence, disagreement, or
missing evidence. Dataset contribution asks about marginal coverage, redundancy, and
utility. These concepts remain separate fields and are not silently collapsed.

## Installation

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

The package targets Python `>=3.12,<3.13` and uses a standard setuptools src layout.

## CLI

```bash
rcqasyn --help
rcqasyn doctor
rcqasyn papers index
python -m rcqasyn --help
```

`doctor` and `papers index` accept `--root` and `--config` for temporary project roots.
The index is deterministic and records filename, relative POSIX path, SHA-256, and size.

## Structure

- `src/rcqasyn/contracts`: Pydantic v2 domain contracts.
- `src/rcqasyn/interfaces`: Protocol-only extension points.
- `src/rcqasyn/config`, `storage`, `literature`, `utils`, and `cli`: foundation services.
- `configs/base.yaml` and `configs/{datasets,generators,validators,experiments}`:
  typed baseline configuration and future configuration notes.
- `literature/papers`, `literature/notes`, and `literature/paper_inventory.csv`: local
  research memory and deterministic inventory; supplied PDFs are locally preserved and
  ignored by Git by default for licensing/repository-size reasons.
- `docs`: architecture, contracts, research plan, literature protocol, milestones, and
  future artifact conventions.

## Milestone status

M0.1 is the foundation milestone. It establishes infrastructure and research contracts
only; planned M1–M9 work and baselines are documented but not implemented.

## Reproducibility

Reproducibility depends on a Python 3.12 environment, resolved YAML configuration, root
seed, Git state, content hashes, and versioned run/artifact records. Future runs must
retain their manifest, resolved configuration, lifecycle events, and schema versions.
No claim about dataset quality or research performance is made by this foundation.
