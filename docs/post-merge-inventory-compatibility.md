# Historical SOURCE inventory after the six-phase merge

The immutable Phase-2 `gate-a-v3` inventory records 284 original paths and raw SHA-256 hashes. It is not regenerated. Its scan previously excluded Phase-2 derivatives only, so merging Phases 3–6 added 1,154 files to the SOURCE scan without changing any expected historical bytes.

The correction keeps two contracts separate:

1. `validate_historical_inventory` validates the original envelope and count/path consistency, verifies every original relative path and recorded raw hash, and requires exact remaining historical membership. Deletions, replacement bytes, corrupt hashes and unexpected additions in original namespaces still fail.
2. Only explicitly registered later research versions are recognized separately. `historical_outputs.py` records seal-catalog fingerprints for 28 named output locations containing 223 sealed bundles, and canonical JSON fingerprints for four exact research-plan paths.

The pins were extracted from immutable approved Git commit `3c01625763a278e11ba27076a1e55f1574c0ae27`, not from rehashed original evidence. Each catalog binds all relative `FINALIZED.json` names and their raw SHA-256 hashes. Every recognized bundle still passes the unchanged `verify_seal` reader. Only files covered by those seals, plus the seals themselves, leave the original SOURCE scan.

Unmanifested files remain visible and rejected. Extra, replaced or changed seals fail the pinned catalog. No new phase directory or version is implicitly authorized. Original paths are independently hash-checked before the strict remaining-membership comparison, so registration cannot hide an expected historical file.

Frozen SOURCE-only checkouts remain valid when these optional later locations are absent. When present, registered outputs and configurations must validate. Existing Phase-2 derivative namespace handling is unchanged. Canonical SOURCE identities remain relative to the supplied source root; no machine-specific absolute path or runtime Git dependency is introduced.

The baseline is never broadened to 1,438 files. No original checksum is recomputed for acceptance. Artifact ownership and seal writers are unchanged. Registration is source-consistency metadata, not cryptographic authentication or a human-approval mechanism. Future output versions require intentional registration and their existing provenance/read/audit contracts; arbitrary new sealed directories do not bypass membership checks.

Regression tests use disposable TEMP fixtures for deletion, replacement and tampering. They cover original-only and authorized Phase-3–6 cases; missing, modified and replaced originals; corrupt inventory hashes, envelopes and counts; legitimate new reports; unregistered and unmanifested additions; tampered manifests, seals and exports; changed configuration identity; and relocated canonical SOURCE roots. The actual merged-main preparation and repair/replay smoke cover the original 284 paths and registered research artifacts.

This patch changes inventory compatibility only. B1/B2/B3, datasets, splits, seeds, metrics, M2, M4/M5, M7, M6/M9, REAL TEST boundaries, scientific artifacts and manuscript remain unchanged. Engineering freeze requires successful post-fix full verification and a normal verified push. Scientific acceptance, all 120 human labels, domain semantics, validity calibration and author declarations remain pending.
