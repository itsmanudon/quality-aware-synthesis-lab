# Phase 1: M1 evaluation stabilization

This change stabilizes execution boundaries and evidence. It introduces no new
dataset, threshold, classifier, metric formula, split algorithm, control admission
rule, generation quota, or review sampling design. There is no CV, model selection,
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
descriptors, effective classifier constructor parameters, configured result families,
preprocessing and existing metric semantics. The estimator descriptor captures
`get_params(deep=False)` from the same constructor factory used for execution,
including LR C/tolerance and RF criterion/depth/features/bootstrap defaults. The
constructors and their scientific settings are unchanged.

New executions use resolved control descriptors: B2 binds declared schema and the
resolved missing policy, TRAIN domains and ranges; B3 binds provider/model and recorded
response source where applicable, prompt bytes, and the bounded TRAIN context hash.
The old `control_policies(config)` descriptor hashes remain a compatibility API;
they do not claim complete binding of resolved execution behavior.

Canonical identity uses `json.dumps(value, sort_keys=True, separators=(",", ":"),
allow_nan=False)` with the default ASCII escaping, UTF-8 encoding, then SHA-256.

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
`FINALIZED.json` uses `m1-seal-v1` and is written last with file hashes. Writers,
JSONL appends, directory reservations, and seals use reentrant OS locks in TEMP.
Locks cover checks, staging, installation, and cleanup; sealing holds the same locks
over a quiescent inventory and seal installation. A writer finishes before sealing,
or fails after the seal without installing. Competing seals have one winner.
Object type is inspected before staging-name exclusion. Only real ordinary
`.rcqasyn-stage-` files are excluded; ordinary staging directories are traversed
and their contents checked. Symbolic links and reparse-point aliases are rejected
regardless of filename before target traversal: file, directory and dangling
symlinks, Windows junctions, and entries carrying Windows reparse-point attributes.
This conservative policy also rejects aliases pointing
inside the bundle and aliases in the bundle root ancestry. Seal verification applies
the same policy, including the seal marker itself.
A seal protects the whole bundle from package writers, including new files and
append/overwrite requests.

Configured experiment `artifact_root` destinations retain their logical absolute
paths, including relative paths anchored to the supplied project root, until guarded
reservation. Input configuration and fixture paths keep their existing read-only
resolution behavior. API and baseline run/replay CLI execution checks protected output
ancestry before constructing providers, then reservation rechecks under the storage
lock. A successful reservation may be canonicalized for active execution writes;
configuration loading never resolves output aliases ahead of authorization.

Explicit derived-output paths retain their caller-supplied logical ancestry through
shared guarded directory reservation. Review/disagreement exports, copying/support
diagnostics, and human-review CLI outputs pass that ancestry to the guard rather
than replacing it with the final resolved endpoint. The guard checks logical,
intermediate alias-target, and physical ancestry before creating the destination.

Protected-write refusals are namespace-side-effect-free: public adapters do not
pre-create parents. Directory reservation and file writers create parents only
after authorization while holding the ownership locks. Refused P1 samples,
JSON/YAML/JSONL/CSV/text writes, and derived reservations leave existing directories,
file bytes/mtimes, and seals unchanged. This guarantee concerns protection refusals;
a later failure in an authorized execution can leave its permitted active output.

The ancestor locks conservatively serialize helpers sharing a filesystem root.
Cooperating processes must use the same TEMP lock namespace. Equivalent normal and
extended Windows path spellings share normalized lock and ownership identities.
Windows thread/process
races and real symlink/junction cases are exercised. Other reparse tags use the
attribute guard but lack dedicated runtime fixtures. The POSIX `flock` path is
implemented but has not been runtime-tested on this Windows verification host.

Existing foreign M1 run directories and supported unversioned/v1 `completed` legacy
bundles are immutable even without a new seal. Existing standalone history in
`artifacts/reports`, `artifacts/manifests`, `artifacts/derived`, `data/manifests`, and
`test-results` (the repository append-only test history) and compatibility
`test-history` paths cannot be overwritten or appended through public helpers. New files
may be created in an unsealed namespace; sealing protects the entire bundle.
Ownership snapshots preexisting files, so claiming an existing directory cannot
authorize replacing its history. Files created by the current active owner can
legitimately transition. Guards retain caller-supplied logical ancestry, resolved
physical ancestry and each intermediate alias target. Resolution expands one hop
at a time, including relative targets and mixed symlink/junction chains; cycles
or unreadable aliases fail closed. Path-component checks reject alias traversal
into or out of protected history, including new destination files; ownership claims and
`overwrite=True` cannot exempt an aliased historical destination. Clearly
nonhistorical temporary aliases remain usable. Active ownership permits transitions
only on real paths created by the current execution.
JSONL append copies existing bytes into a new staged file, appends and flushes the
batch, then atomically replaces the destination entry under the same writer lock.
Appending through an outside hardlink therefore detaches that entry without
changing the protected original or other hardlinks. A failed batch leaves the
installed file unchanged. This copies the existing stream on each append and may
cost more than in-place append for large streams; it does not prohibit hardlinks.
Dataset preparation and TRTR/comparison manifests may reuse byte-equivalent logical
content without writing; changed content fails instead of refreshing old reports.
Acquisition, CSV, YAML, JSONL and human-audit writers refuse replacements of
protected historical outputs. The public paper inventory API and
`papers index --output` use the same guarded atomic writer, including alias-hop
checks and seal exclusion. Regenerating an ordinary nonhistorical inventory or
updating a new active-owned inventory remains supported. Atomic replacement
detaches an outside hardlink instead of mutating its protected source file.
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
judge or evidence joins. Expected transport failures propagate `DurableCallFailure`
with the exact persisted attempt ID; callers never reconstruct failed durable IDs.
A fresh smoke consumes `generation-0`, so the first actual batch is `generation-1`.
Returned responses supply the authoritative ID used by traces and parser failures.
Raw evidence also records the configured provider identity, scientific fingerprint,
actual recorded-response mode, and purpose (`generation_smoke`, `generation`, or
`judge`). These are local evidence fields and never become upstream provider
arguments. The existing trace stream retains smoke and generation evidence.

New review selections hash review seed, stratum, scientific fingerprint, and stable
candidate ID; execution UUIDs and output paths are excluded. Caps, categories, roles,
tertiles, default seed, and eligible population retain their existing design. Legacy
new selections retain their recorded run identity. If a legacy bundle contains a
recorded `p1_human_review.csv`, it is consumed as recorded. Aggregate exports can be
supplied with `recorded_sample=`; the P1 roll-up reuses its existing historical export.
Source membership is checked, and recorded ordering/human cells/bytes are preserved.
Historical seed and strata are not inferred from a CSV that does not record them.
Role summary trace files are written later; after a crash, the durable call files are the recovery evidence.

A terminal `finalized` execution is a persisted bundle, not necessarily a successful
or fully evaluable experiment. `m1-outcome-v1` separates lifecycle, component states,
utility evaluability and success. Generation/parse/judge failures, missing metrics,
classifier failures and nonfinite metric values prevent full success. Per-metric
availability preserves missing/nonfinite/exception reasons without altering numbers.
The nested contract validates required configured columns, TRAIN classes,
populations and classifiers, every supported nested status, explicit unavailable
reasons, and component/accounting consistency. Missing required results or invalid
accounting fail finalization; declared nested failures and explained unavailable
results can produce a finalized diagnostic bundle with `success=false`. Low finite
metric values do not constitute failure. Outcome reasons are ordered canonically
for reader roundtrips.

Requested and returned generation counts are reported separately; overproduction is
recorded without truncation or regeneration. Requested-denominator ratios may exceed
one under the existing overproduction or batch-per-parser-event accounting formulas;
validation checks those formulas rather than imposing a new cap.

Unexpected exceptions propagate and attempt to persist a failed manifest/fallback
marker. If storage itself fails, the missing final seal prevents new readers from
accepting the directory as finalized. Such directories must not be resumed by
overwriting their files.

## Readers and frozen controls

New readers require finalized v2 state, supported seal/specification/result schemas,
a valid seal, and consistent run/execution, scientific, dataset/source, and split
identities. New executions record `dataset/evaluation_population.json` using the
exact normalization serialization whose SHA-256 is the dataset fingerprint.
This snapshot is local evaluation provenance, never a TRAIN profile or upstream
provider/judge input. Readers validate the approved seed derivation and class-wise
hash-order membership against it, including unique/disjoint/full partitions,
singleton TRAIN support, subset fingerprints and recorded counts. Split
fingerprints retain the approved serialization; split generation is unchanged.
Complete resolved control descriptors are reconstructed from recorded configuration,
dataset schema, TRAIN profile, provider identities, prompt snapshots and recorded
estimator parameters. Required result families are derived from the schema and
TRAIN labels; classifier requirements come from configuration. Mutually agreeing
result declarations cannot remove a required feature or alter a control policy.
Configured result families/classifiers are bound to the scientific specification;
the source identity graph is validated against recorded configuration and manifest
truth. Root/split seeds, plan counts/quotas/provider settings and prompt bytes must
agree. Durable calls bind execution, configured provider and actual requests;
their purpose must agree with request role, provider and trace/consumer lineage.
Summary attempts, returned responses, provider failures and parse failure events
are reconciled with durable evidence. Every baseline comparison row is required
exactly once, with generation/judge/smoke counts and population counts consistent
with its sources. Smoke nulls in replay retain their existing representation;
required accounting fields cannot be silently removed.
candidates must match the recorded generation response and call. Every control
decision must refer to the ordered raw pool, and its accepted subset must match
exactly. Judge results/failures and B2 evidence must join the corresponding candidates
and calls. Explicit nested result identities, including control identity, must agree
with their source even when comparison copies agree with each other. Recognized
execution/dataset/scientific/split/control fields are checked recursively in
comparison metadata as well as baseline results.

New v2 bundles require the normalized population snapshot, `m1-artifact-bindings-v1`
and `execution_binding.json`; each
baseline requires `m1-result-binding-v1` in `result_binding.json`. Bindings record
source/result file hashes, execution/dataset/scientific/control identities, and the
accepted population identity. Comparison carries binding fingerprints outside the
unchanged baseline metric dictionaries. `dataset/profile_source.json` preserves
the original profile serialization for existing plan lineage, and `prompts/` stores
execution-local template snapshots without editing historical prompts.

Readers validate these bindings and reparse recorded responses with the frozen
parser; they do not recompute research metrics or rerun control admission. Pure
replay request validation uses the recorded placeholder and does not render an
unsafe legacy template. Required new-format bindings cannot be silently omitted.
Pre-binding experimental v2 output is not accepted as finalized new-format input;
there is no in-place upgrade. Readers enforce the nested result contract.
Experimental v2 bundles produced before the population binding was required fail
the current new-format requirements; they are not silently upgraded or credited
with split-validation guarantees. Supported unversioned/v1 historical bundles
remain under the explicit legacy compatibility contract.
Utility evaluability is derived from required finite metrics and classifier status, rather than trusting an aggregate
flag. Missing diagnostics/admission/judge accounting fails schema validation.

Known unversioned/v1 legacy bundles with recorded `completed` status remain readable
without migration. Available manifest/source/result identity declarations are checked;
fields that never existed are not fabricated or required. Compatibility metadata
explicitly states that the old success/schema/seal and complete cross-artifact
identity were not verified by the new contract.
Missing manifests, running/failed state and unknown versions are rejected. Legacy dictionaries used directly by pure analysis
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
- Remediation: nested contracts, authoritative failure joins, scientific review
  identity, writer/seal exclusion, legacy/public writer coverage, resolved behavior
  fingerprints, and cross-artifact identity validation have regression coverage.
- Ruling: role-local durable ordinals are qualified by execution directory; review
  selection uses scientific identity rather than the execution directory identity.
- Ruling: refuse ambiguous multi-execution diversity pairing instead of deciding a
  new scientific pairing policy.

Verification commands: `python -B -m pytest -q -ra --tb=short -p no:cacheprovider
--basetemp <fresh-temp>`, focused Phase-1 tests, `ruff check .`, `pyright`,
and deterministic offline replay into fresh temporary output. Test counts and final
gate results are recorded in the implementation handoff; use `pytest --collect-only`
for the current count instead of relying on historical counts. No provider research
experiment or performance claim is part of this verification.


Earlier remediation at `fad5e716` reported 375 tests passed without deselection,
including all original 158 tests and 217 added regression cases. The focused Phase-1 suite passed
277 tests. Both runs reported the same 14 sklearn warnings from adversarial
TEST-label mutation. Ruff passed; Pyright reported zero errors/warnings (a tool
update advisory was recorded separately); `git diff --check` passed.

Those earlier standalone probes covered F1-F7 through public contracts,
fresh fake/recorded executions, disposable writer/seal races, and resealed adversarial
bundles. Two seed-42 executions shared a scientific fingerprint and substantive
results while reserving distinct directories. Seed 43 changed scientific and split
fingerprints. Actual 100-candidate executions selected identical review IDs/order
across execution UUIDs; changing review seed changed selection. Full success remains
reachable with a valid fixture. The legacy replay fixture remains explicitly not
fully successful/evaluable. No external provider was contacted.

The subsequent independent review identified filesystem alias/history and nested
gaps in the bindings between sources and results. Final remediation adds real Windows alias matrices,
refreshed-binding/resealed contradictions, and fresh failure-reader regressions.
The previous remediation round passed 831 full-suite tests and 733 focused Phase-1
tests, without deselection, with the same 14 adversarial TEST-label warnings. This
adds 396 filesystem and 60 reader regression cases to the prior 375-test suite.
Ruff passed, Pyright reported zero errors/warnings, and the diff check passed.
Manual probes passed 88 storage checks, 21 correctly resealed bundle checks and
118 contract/provenance/boundary checks. All six Windows thread/process races and
18 substantive differential families against the audited base passed. Protected
historical bytes remained unchanged. Prior counts above are historical results;
the final handoff records the commit identities and remaining runtime limitations.

The V1–V9 remediation adds 303 regression cases. Final verification passed 1,134
full-suite tests and 1,036 focused Phase-1 tests without deselection, with the same
14 sklearn warnings. Ruff and the diff check passed; Pyright reported zero errors
and warnings. Disposable manual probes passed 41 storage checks, 19 resealed reader
checks, and 118 prior contract/provenance/boundary checks. Fresh Windows thread and
process probes covered six reservation/write/seal races and four append/overwrite
races; normal/extended-path exclusion also has regression coverage and separate
read-only review probes. All 18 substantive differential families matched the
audited base. These are implementation verification results; the final merge gate
still requires personnel-independent verification.

A subsequent independent review found that the public literature inventory
writer still opened CSV destinations directly. Its remediation routes both the
API and CLI through the guarded atomic writer and adds 88 regression cases,
including the 24 reported alias combinations, direct historical destinations,
ownership claims, hardlinks, serialization and writer/seal exclusion. A separate
TEMP-only manual probe passed 64 checks, including real subprocess CLI calls.
Fresh verification passed 1,222 full-suite tests and 1,124 focused Phase-1 tests
without deselection, with the same 14 sklearn warnings. Ruff and the diff check
passed; Pyright reported zero errors and warnings. Protected historical inventories
remained byte-identical. Merge approval still belongs to the personnel-independent
verifier.

Protected historical inventories are hashed before remediation and again after
verification. Historical artifacts, data/history, paper/results, prompts,
configurations and recorded test results are not rewritten. All test/replay/probe
outputs are confined to fresh operating-system temporary directories. The final
handoff records the integrity comparison and commit identities; re-verification
remains the independent verifier's responsibility.
