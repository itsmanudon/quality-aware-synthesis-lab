# Dataset registry and leakage policy

Dataset YAML files under `configs/datasets/` are the source of truth for dataset
identity, accepted local path, target/features/types, missing policy, source URL, and
split metadata. The registry includes `page-blocks0`, `Ecoli4`, and `Abalone19` using
the verified KEEL source pages from the research manifest. Expected schemas are
validated against a placed file; label semantics, statistics, and minority labels are
not asserted until then. It also includes `dev-small`, a tracked, non-sensitive fixture
that is explicitly not KEEL data.

No downloader is implemented. Place the exact verified KEEL file at the path shown by
`rcqasyn datasets inspect <id>`; missing-data messages include accepted filenames and
do not guess URLs, statistics, or transformations. KEEL `.dat` parsing reads declared
`@attribute` and `@data` metadata and preserves missing values as null according to the
specification.

`rcqasyn datasets prepare <id> --seed 42` writes a dataset fingerprint, deterministic
stratified split manifest, and a profile under `data/manifests/<id>/`. Existing
manifests refuse accidental overwrite. The test split is never used for profile
statistics, examples, prompt text, filters, judges, model selection, or preprocessing
fit. Profiles are built from TRAIN only and include explicit train indices and hashes;
sentinel test-only values/categories must therefore not appear in prompts or profiles.

Observed numeric ranges are descriptive support, not hard constraints. The B2 observed
range validator emits a WARN verdict by default and only rejects if its configured
severity is selected. This distinction prevents a small sample's observed support from
being silently treated as a domain rule.
