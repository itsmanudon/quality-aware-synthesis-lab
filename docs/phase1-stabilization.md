# Phase 1: M1 evaluation stabilization

This change stabilizes execution boundaries and evidence. It introduces no new
dataset, threshold, classifier, metric formula, split algorithm, control admission
rule, generation quota, or review sampling policy. There is no CV, model selection,
hyperparameter search or calibration execution path in M1.

## TRAIN and REAL TEST

The existing stratified hash ordering remains unchanged. Partition validation
requires unique row identities, disjoint nonempty sets, full coverage, dataset
identity and the recorded TRAIN fingerprint. A declaration of `stratify=false`
fails explicitly; M1 does not implement a different split.

Profile summaries, domains and examples consume TRAIN. The full profile artifact
also retains whole-population and split lineage, which includes REAL TEST.
`TrainingContext` projects only TRAIN summaries/examples for generation and
admission. Controls receive REAL TRAIN and an evaluation callback; REAL TEST is
sliced only inside the final utility evaluation. TRTR fits on REAL TRAIN, TSTR on
accepted synthetic records; their existing imputation/scaling/encoding is unchanged.

Boundary `m1-train-boundary-v1` rejects fresh execution unless generation uses the
bounded v2 context and supported template fields, and the judge receives the
bounded TRAIN view. It fails before provider construction/contact or run reservation.
Legacy prompt files are unchanged. Pure `--replay` with both response providers
recorded can consume stored generation/judge responses without rendering unsafe
legacy prompts. Traces explicitly say no upstream prompt was executed; this is
recorded-response compatibility, not a fresh execution of the old protocol.
A replay with a newly executing judge remains subject to the fresh-context guard.

## Scientific specification and execution identity

`scientific_specification.json` stores `m1-scientific-spec-v1` and its SHA-256.
It binds the resolved dataset definition, normalized data fingerprint and raw source
bytes, split protocol/seed, example policy, generation configuration, response fixture
bytes where applicable, provider/model configuration, prompt hashes, B1/B2/B3 policy
descriptors, classifier parameters, preprocessing and existing metric semantics.

The runner uses already resolved inputs and checks source bytes during resolution.
Replay source identities bind to the bytes actually loaded by each provider.
Execution IDs, output locations, timestamps, elapsed time and machine paths do not
enter this scientific fingerprint. Legacy `config_hash` and generation-plan lineage
remain available and have their old meanings; they are not scientific identifiers.
An omitted run ID produces a UUID execution suffix; an explicit run ID is reserved
exclusively and cannot be reused. Two executions may share one scientific fingerprint.

Existing seed routes remain unchanged: root seed, derived split seed, hash-ordered
references, derived per-generation-batch seeds, unchanged base generation seed for
each judge call, and root seed for classifiers. An absent provider seed records
`all_seeds_unique=null`, never proof of determinism. Even a supplied provider seed
does not guarantee provider determinism. Environment metadata records Python,
package/dependency versions, platform, Git SHA and dirty state. Dirty execution is
allowed and recorded honestly.

## Active writes and immutable history

The execution owns its newly reserved directory. Its lifecycle manifest and smoke
state may transition while active; evidence streams may append. Other outputs use
exclusive atomic creation. JSON writes reject non-standard NaN/Infinity.
`FINALIZED.json` is written last and contains file hashes. A seal protects the
whole bundle from package writers, including append/overwrite requests.

Existing foreign M1 run directories are immutable even without a new seal.
Dataset preparation and TRTR/comparison manifests may reuse byte-equivalent logical
content without writing; changed content fails instead of refreshing old reports.
Acquisition, CSV, YAML, JSONL and human-audit writers refuse replacements.
Compatibility `--overwrite` arguments do not authorize replacing historical outputs.
These are executable application protections, not filesystem permissions preventing
arbitrary external editors from writing files.

Diagnostics and historical review exports create new directories under
`artifacts/derived/`, with source hashes and a final seal. They never add files to
the source run. The P1 report script creates a new derived namespace and consumes
diagnostics in memory. Source-bound diagnostics use recorded split manifests and
verify dataset/schema/fingerprints; v2 sources additionally verify raw source and
dataset definition bindings. A mismatch fails with a provenance error.

Human annotation must be performed on a separate copy of a machine review export.
Human-audit reports require completed source run manifests, preserve joined evidence
hashes, and are sealed after all outputs are written. Legacy missing duplicate
evidence remains ambiguous; it is never retrospectively inferred.

## Durable calls and lifecycle

`calls/<role>-<ordinal>.json` is durably persisted before trace construction,
parsing, admission or subsequent calls. Internal call identity is qualified by
execution ID and directory; role ordinals remain stable across deterministic reruns.
External provider IDs are retained in provenance and cannot collide in candidate,
judge or evidence joins. Existing sampling still hashes the same seed/category/record
identity; execution UUIDs do not enter those identities. Role summary trace files are
written later; after a crash, the durable call files are the recovery evidence.

A terminal `finalized` execution is a persisted bundle, not necessarily a successful
or fully evaluable experiment. `m1-outcome-v1` separates lifecycle, component states,
utility evaluability and success. Generation/parse/judge failures, missing metrics,
classifier failures and nonfinite metric values prevent full success. Per-metric
availability preserves missing/nonfinite/exception reasons without altering numbers.
Requested and returned generation counts are reported separately; overproduction is
recorded without truncation or regeneration.

Unexpected exceptions propagate and attempt to persist a failed manifest/fallback
marker. If storage itself fails, the missing final seal prevents new readers from
accepting the directory as finalized. Such directories must not be resumed by
overwriting their files.

## Readers and frozen controls

New readers require finalized v2 state, a valid seal, consistent specification/
execution identity, and the required result contract. Utility evaluability is derived
from required finite metrics and classifier status, rather than trusting an aggregate
flag. Missing diagnostics/admission/judge accounting fails schema validation.

Known legacy bundles with recorded `completed` status remain readable without
migration. Compatibility metadata explicitly states that the old success/schema/seal
was not verified by the new contract. Missing manifests, running/failed state and
unknown versions are rejected. Legacy dictionaries used directly by pure analysis
helpers remain distinguishable from validated source bundles.
Cross-dataset aggregation preserves separate execution entries. The one-to-one
diversity comparison refuses multiple runs for a dataset on either side rather than
silently selecting one; choosing a new pairing design remains out of scope.

Versioned B1/B2/B3 descriptors and frozen fixtures protect their current behavior.
B2 still rejects TRAIN-unseen categories and exact duplicates, including a duplicate
of an earlier rejected record. New duplicate evidence describes that existing
redundancy rule and its first occurrence; it is appended after admission is decided
and excluded from the unchanged deterministic violation metric.

Research-gated ambiguities remain unchanged: malformed target semantics,
`pr_auc` as average precision, positive-label interpretation, zero-distance contact
formula, intrinsic duplicate canonicalization, Wasserstein scaling, thresholds,
preprocessing, prompt contents, quotas and real-data/review matrix design.

## Implementation ledger and verification

Base: `2632a200c1b9f94daba9cc17009f24da808763d6`.
Implementation lives in the dedicated `phase1/m1-evaluation-stabilization` worktree.
The original checkout and all historical source directories are outside the change.

- P1.2: partition/projection/pre-contact guard tests observed failing then passing.
- P1.3: specification/execution identity, seed/environment provenance tests added.
- P1.4: atomic exclusive writes, ownership, seals, source-only derivatives and durable calls.
- P1.5: explicit lifecycle/schema/availability; injected generation, parsing, trace,
  judge, classifier, metric, evidence-write, aggregation and finalization failures.
- P1.6: frozen split/control fingerprints, ordered duplicate fixtures and B3 boundaries.
- Test isolation: dataset CLI uses copied specs and disposable raw/manifests locations.
- Independent read-only review found status, metric-reason, resolved-source and reader
  gaps; failing regression tests preceded their fixes.
- Ruling: use stable role-local call ordinals qualified by execution directory, so
  execution uniqueness cannot change existing deterministic review sampling inputs.
- Ruling: refuse ambiguous multi-execution diversity pairing instead of deciding a
  new scientific pairing policy.

Verification commands: `python -B -m pytest -q -ra --tb=short -p no:cacheprovider
--basetemp <fresh-temp>`, focused Phase-1 tests, `ruff check .`, `pyright`,
and deterministic offline replay into fresh temporary output. Test counts and final
gate results are recorded in the implementation handoff; use `pytest --collect-only`
for the current count instead of relying on historical counts. No provider research
experiment or performance claim is part of this verification.


Final verification on the implementation worktree: 158 tests passed without
deselection (14 expected sklearn warnings from adversarial TEST-label mutation);
Ruff passed and Pyright reported zero errors/warnings. The focused Phase-1 suite
contains 60 tests. An independent read-only reviewer checked the corrected result
contracts and frozen scientific behavior; that review was not a second full-suite run.

Offline verification used two executions at seed 42 and one at seed 43 in fresh
OS temporary directories. The seed-42 executions shared a scientific fingerprint,
had different execution identities/directories and matched substantive replay outputs.
Seed 43 changed both scientific and split fingerprints. The legacy replay fixture
remains explicitly not fully successful/evaluable; a separate valid offline fixture
proves that full success is reachable. No external provider was contacted.

Byte-level aggregate hashes of the original checkout and protected historical groups
in the implementation worktree matched their pre-implementation inventories.
Historical `artifacts`, `data`, `paper`, prompts, configurations and recorded test
results were not rewritten. Pytest basetemps and replay bundles were created only
under the operating system temporary directory.
