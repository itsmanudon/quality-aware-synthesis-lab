# Dataset registry and leakage policy

Dataset YAML files under `configs/datasets/` are the source of truth for dataset
identity, accepted local path, target/features/types, missing policy, source URL, and
split metadata. The registry includes `page-blocks0`, `Ecoli4`, and `Abalone19` using
the verified KEEL source pages from the research manifest. Raw declarations, labels,
statistics, and minority labels are recorded only after the official files are placed.
It also includes `dev-small`, a tracked, non-sensitive fixture that is explicitly not
KEEL data.

No mirror or guessed downloader is used. Place the exact verified KEEL file at the path
shown by `rcqasyn datasets inspect <id>`; missing-data messages include accepted
filenames and do not guess URLs, statistics, or transformations. After placement,
`rcqasyn datasets record-acquisition <id>` writes an ignored
`data/manifests/<id>/source.json` containing the exact source URL, downloaded archive
filename, UTC timestamp, archive size/SHA-256, and extracted `.dat` size/SHA-256.
KEEL `.dat` parsing reads `@relation`, `@attribute`,
`@inputs`, `@outputs`, and `@data` metadata and preserves missing values as null.
`datasets inspect` reconciles those authoritative declarations with the checked-in
spec before preparation.

The M1.1 official acquisitions are:

| Dataset | Canonical archive | Rows | Features (numeric/categorical) | Classes (negative/positive) | IR | Missing |
| --- | --- | ---: | ---: | --- | ---: | ---: |
| page-blocks0 | `https://sci2s.ugr.es/keel/dataset/data/imbalanced/page-blocks0.zip` | 5472 | 10/0 | 4913/559 | 8.79 | 0 |
| Ecoli4 | `https://sci2s.ugr.es/keel/dataset/data/imbalanced/ecoli4.zip` | 336 | 7/0 | 316/20 | 15.80 | 0 |
| Abalone19 | `https://sci2s.ugr.es/keel/dataset/data/imbalanced/abalone19.zip` | 4174 | 7/1 | 4142/32 | 129.44 | 0 |

The page-blocks0 source declares the feature spelling `Lenght`; the registry keeps
that authoritative spelling rather than silently renaming the raw column.

`rcqasyn datasets prepare <id> --seed 42` writes a dataset fingerprint, deterministic
stratified split manifest, a TRAIN-only profile, a compact dataset report, and explicit
leakage assertions under `data/manifests/<id>/`. Existing manifests refuse accidental
overwrite; identical content is a read-only no-op and changed content fails. TRAIN
statistics/domains/examples exclude REAL TEST. The full profile retains TEST-inclusive
lineage fingerprints for auditing; only the bounded TRAIN projection is allowed
upstream in fresh execution. Legacy full-profile fresh contexts fail before provider
contact. Classifier preprocessing fits its training population only. No CV/model
selection or calibration path exists in M1. Sentinel TEST values must not appear
in TRAIN summaries/examples or approved provider contexts. `rcqasyn baselines trtr <id> --seed 42`
writes the real-train/real-test pilot report for logistic regression and random forest.

Observed numeric ranges are descriptive support, not hard constraints. The B2 observed
range validator emits a WARN verdict by default and only rejects if its configured
severity is selected. This distinction prevents a small sample's observed support from
being silently treated as a domain rule.

The existing hash-ordered stratified split is unchanged. `stratify=false` is
explicitly unsupported. See [Phase 1](phase1-stabilization.md).
