# Reproducibility and artifact policy

This repository treats reproducibility metadata and compact scientific outputs as
source material. A collaborator should be able to understand an experiment and resume
the project from Git without silently regenerating evidence on another machine.

## Environment and experiment locations

- Use CPython 3.12; the package requires `>=3.12,<3.13`.
- Create an isolated environment and install development dependencies with
  `python -m pip install -e '.[dev]'`.
- Local Ollama-compatible providers use `http://127.0.0.1:11434/v1` by convention.
- P1 used `gemma4:e4b` for generation and judging. The shared-model limitation is
  recorded in each run manifest.
- Experiment configurations live in `configs/experiments/`; P0-v3 and P1 use
  `pilot_v3/` and `pilot_p1/` respectively.
- Versioned prompts live in `prompts/`; P1 generation uses `prompts/generation/v2.txt`.
- Dataset registry entries live in `configs/datasets/`. Acquisition records, archive
  hashes, dataset fingerprints, schema reports, and split metadata live in
  `data/manifests/` and in each committed run's `dataset/` directory.

Historical resolved configurations may contain the source machine's absolute artifact
path. Keep that path as provenance; on another machine, use the repository-relative
config and artifact locations rather than editing the historical record.

## What Git tracks

Commit source code, tests, configurations, prompt versions, documentation, literature
notes, dataset schemas and acquisition manifests, deterministic split fingerprints,
seed plans, experiment manifests, compact diagnostics, aggregate JSON/CSV/Markdown
reports, small fixtures, and non-sensitive human-review materials.

`artifacts/reports/` and `artifacts/manifests/` are intentionally trackable. Completed
reviewer CSVs, adjudicated CSVs, agreement results, and human-audit reports should be
committed when small and non-sensitive. Annotator private notes must not be placed
outside the intended `human_notes` column.

The six completed P0-v3 and P1 Legion runs dated 2026-08-29 are explicit exceptions to
the default run-directory ignore. Together they are small enough for normal Git and are
the original source artifacts behind the M1.5 reports. Their raw provider traces are
tracked because they are part of these bounded, expensive, scientifically important
runs; future run directories remain ignored unless deliberately reviewed and allowed.

## What stays local

Keep raw downloaded datasets, large generated pools, partial or failed runs without
scientific value, provider scratch output, archives, model weights, Ollama storage,
caches, virtual environments, build output, transient logs, and secrets out of Git.
`.env` files are ignored; a committed example file must contain placeholders only.

Do not commit a large artifact merely because another machine needs it. Store it in an
approved shared drive, object store, or other project archive and commit a small
manifest containing its run ID, dataset, experiment version, external relative path,
file count, byte count, creation timestamp, model, prompt version, root seed, record
counts, and SHA-256 checksum. Record per-file checksums when the directory is not packed
as one archive.

## Transfer and verify a large artifact

Create an archive in the ignored `artifacts/archives/` directory:

```text
tar -czf artifacts/archives/<run-id>.tar.gz artifacts/runs/<run-id>
```

On PowerShell, record and verify SHA-256 with:

```powershell
Get-FileHash -Algorithm SHA256 artifacts/archives/<run-id>.tar.gz
(Get-FileHash -Algorithm SHA256 artifacts/archives/<run-id>.tar.gz).Hash.ToLower()
```

On macOS or Linux, use:

```bash
shasum -a 256 artifacts/archives/<run-id>.tar.gz
```

Compare the complete lowercase hexadecimal value with the tracked manifest before
extracting. Transfer the archive outside Git, place it under `artifacts/archives/`, then
restore it from the repository root:

```text
tar -xzf artifacts/archives/<run-id>.tar.gz
```

Never overwrite an existing run directory. Verify source identities and checksums,
then restore or derive into a new directory.

## Resume on another laptop

1. Clone the repository, or run `git pull --ff-only origin main` in an existing clone.
2. Create a Python 3.12 virtual environment and install `.[dev]`.
3. Run `rcqasyn doctor`.
4. Restore each raw dataset from its recorded source or a trusted local copy. Verify the
   archive and extracted file against `data/manifests/<dataset>/` before use.
5. Pull the committed P0-v3/P1 reports and run directories directly from Git. For a
   future external run, download its archive, compare SHA-256 with the tracked manifest,
   and extract it at the documented repository-relative path.
6. Confirm the intended config, prompt version, root seed, dataset fingerprint, and run
   manifest before continuing analysis or annotation.
7. Run the relevant tests or report command before producing new derived artifacts.

Do not rerun an expensive experiment merely because artifacts are missing on another
machine. Transfer the original artifacts if available; a rerun is a new experimental
replicate.

## Phase 1 execution guarantees

Scientific-specification fingerprints exclude execution IDs and output paths. Unique
execution IDs reserve separate bundles. Seeds, environment and dirty Git state are
recorded, but provider determinism is not guaranteed. Missing seeds are explicit.
Finalized and foreign run bundles are immutable to package writers; active owned
manifest/evidence transitions are permitted until sealing. OS locks exclude active
writes from seal inventory/installation; existing standalone reports and dataset
history resist public overwrite/append flags. Supported legacy completed bundles
remain read-only and report their validation limitations. Derived analysis writes
separately and validates source bindings. See [Phase 1](phase1-stabilization.md) for
status contracts, durable call recovery, guards and legacy compatibility.

Writer protection checks each alias hop, including intermediate historical namespaces.
Staging names do not exempt symlinks or junctions. JSONL append installs a durable
copy, so appending through an outside hardlink does not mutate its protected source.
Normal and extended Windows path spellings use the same lock identities; cooperating
processes still require a common TEMP namespace, and ancestor locking is conservative.
POSIX locks have not been runtime-tested on this Windows host.

New bundles also bind a local normalized population snapshot to the dataset hash.
Readers validate approved split membership, complete resolved controls, schema-derived
result requirements, durable-call accounting and explicit nested source identities.
The snapshot never enters provider or judge contexts. Validation compares provenance
and recorded results; it does not recompute metrics or rerun admission. Older v2
experimental output without the required snapshot is rejected rather than upgraded.
