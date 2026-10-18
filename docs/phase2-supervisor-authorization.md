# Phase-2 supervisor authorization after R1

Status: READY FOR INDEPENDENT RE-VERIFICATION; no supervisor approval is implied.
Production authentication is deliberately unavailable in this build. There is no
protected Windows enrollment authority or independently installed approval provider.
A supervisor policy file, public key, environment variable or Python object cannot
enable official approval. No real enrollment, credentials or labels were created.

## Two execution environments

The autonomous environment may prepare source-bound packets, propose labels after
Gate A, save untrusted reviewer submissions, export a complete unsigned ledger and
run explicitly synthetic diagnostics. It cannot select supervisor authority,
authenticate real human labels or run official B2/B3 human-label analysis.

The supervisor approval environment must be independently controlled: a separate
account or machine, with trusted installed code, protected policy integrity, a
protected signing credential and an independently retained accepted history tip.
The autonomous account must have no write, launch-configuration or credential access
there. Another folder, read-only-looking Python object, confirmation flag or path
outside Git does not provide this isolation under the same unrestricted OS account.

The supplied Windows setup has no authority integration that can establish that
boundary. Therefore `authenticate_review`, `import_supervisor_approval`, production
`analyze`, and the production approval CLI fail closed. No fallback scans for policy
files, cached fixture keys, environment variables or first-use enrollment exist.
Enabling real approval requires a separately reviewed deployment integration that
resolves one enrolled supervisor anchor and expected tip outside agent control.
That integration is not implemented or claimed here. Gate A may assess these
fail-closed contracts without enrolling or approving anything.

## R1: authority selection, not signature mathematics

Previously the caller selected `trust_config`. An agent could sign with its own key
and select a matching external policy. Ed25519 verification succeeded but did not
establish independently authorized supervisor authority.

The production Python APIs retain obsolete trust arguments only to reject them
explicitly, before opening policy files or reserving outputs. Their absence also
refuses because protected enrollment is unavailable. `load_supervisor_trust` is a
rejecting compatibility entry point. The CLI no longer accepts a trust-policy
positional argument or `--trust-config`. Ordinary commands cannot enroll trust.

A future protected provider must load a fixed enrolled policy and independently
pinned key ID from its protected deployment, never a per-call reviewer path. Key
rotation is a separate supervisor enrollment operation. Incoming CSV/JSON, signed
packages, receipts and caller-controlled environment must not choose either policy
or pin. Existing local authenticated reports are evidence, not current authority.
The current consumer rejects them rather than trusting their status.

## Review states and complete signed ledger

An AGENT proposal remains immutable `PENDING_HUMAN_APPROVAL` with blank human fields.
Reviewer decisions are `SUBMITTED` (possibly pending a final label) or `UNRESOLVED`.
Imported `APPROVED` is rejected, including known-agent aliases after normalization.
Saving/exporting a decision leaves it `SUBMITTED_UNVERIFIED`.

After Gate A, the supervisor can inspect all 120 payloads, source-backed definitions,
ambiguities and proposals. Submit acceptance/corrections with reviewer reference,
provenance and rationale for changed labels. Save partial decisions and resume using
`review-export --history`. Original proposals and correction events stay intact.
Incomplete or latest unresolved review cannot produce a complete approval ledger.

```text
phase2 review-export CHECKPOINT EXPORT --history HISTORY --source-root SOURCE
phase2 review GATE_A_JSON DECISIONS_CSV_OR_JSON CHECKPOINT HISTORY --source-root SOURCE
phase2 approval-export GATE_A_JSON CHECKPOINT HISTORY REVIEWER UNSIGNED_EXPORT --source-root SOURCE
```

The unsigned ledger's `APPROVED` values request the operation; they grant no authority.
The retained Ed25519 format binds the Phase-1 freeze, population, exact cohort,
ordered crosswalks, protocol, Gate-A record, complete proposal set, occurrence IDs,
payload/proposal hashes, final labels, reviewer/status/provenance/correction fields
and ordered history/tip. Canonical bytes are the ASCII domain
`RC-QASyn/supervisor-approval-ledger/v1`, NUL, then UTF-8 JSON with sorted keys,
compact separators, ensure_ascii=true and allow_nan=false. Duplicate JSON keys and
contract-normalized signed-value changes are refused. Maintained `cryptography`
Ed25519 primitives implement signing/verification; no custom algorithm is used.

## Offline enrollment and signing

Do not execute real enrollment or use a real private key from the autonomous agent.
In the independently protected supervisor environment, obtain the existing public
policy (`supervisor-trust-v1`) and confirm its raw public-key SHA-256 fingerprint
through the supervisor's independent record. Retain the exact expected history tip
outside the review-data hierarchy. Do not derive either trust decision from an
incoming ledger or agent-selected policy path.

The offline tool records that explicit pin and tip in a new public enrollment bundle:

```text
python scripts/enroll_phase2_supervisor.py --public-policy PUBLIC_POLICY_JSON --expected-key-id INDEPENDENT_KEY_SHA256 --expected-history-tip RETAINED_TIP --output ABSOLUTE_NEW_EXTERNAL_DIRECTORY --confirm-protected-environment
```

It reads public material only, validates the key against the independently supplied
pin, validates the tip shape, refuses repository destinations and uses exclusive
versioned storage. Its output is `PENDING_PROTECTED_DEPLOYMENT`, official=false,
production_approval=false. The confirmation flag is an operator assertion, not a
security control. This public record cannot activate the production consumer.
A supervisor must protect and install the enrollment in the separately reviewed
provider described above; no current CLI/API loads it as production authority.
Rotation requires a newly confirmed key fingerprint and new protected enrollment;
replacing a caller file cannot rotate authority.

After reviewing every required row and identity in the trusted context, the existing
offline signer can sign the complete ledger with an existing encrypted Ed25519 key:

```text
python scripts/sign_phase2_review.py --ledger LEDGER_JSON --private-key EXTERNAL_ENCRYPTED_KEY --output ATTESTATION_JSON --confirm-reviewed
```

The helper creates no credential, obtains the password interactively, signs canonical
content and refuses output overwrite. Never give the key/password to the agent.
Signing is separate from enrollment. No importer or analyzer invokes this helper.

Production commands remain present to give an explicit refusal until an independent
protected authority integration exists:

```text
phase2 approval-import GATE_A_JSON CHECKPOINT HISTORY ATTESTATION_JSON OUTPUT --source-root SOURCE
phase2 analyze GATE_A_JSON CHECKPOINT HISTORY OUTPUT --supervisor-attestation ATTESTATION_JSON --source-root SOURCE
```

They produce no official output, even for cryptographically valid signatures.
Future protected consumption must independently resolve the enrolled pin and expected
tip, reverify the signed complete ledger and current source/proposal/history bindings,
and authenticate every receipt it consumes. A previous APPROVED report is insufficient.

## Isolated synthetic diagnostics

There is no production CLI fixture switch. Explicit Python diagnostic APIs are
`diagnose_fixture_review`, `import_fixture_diagnostic` and `diagnose_fixture_analysis`.
Each rejects research populations. They use a disposable `FixtureTrustAnchor` with
separate expected key ID and retained history tip. Replacing only its policy file
cannot replace that pin. Tests may deliberately construct another anchor, but it
confers no production permission. Python objects are not an in-process security
boundary against code with the same privileges.

Every result is official=false, production_approval=false and marked
`UNTRUSTED_SIGNATURE_DIAGNOSTIC` or `UNTRUSTED_FIXTURE_LABELS_DIAGNOSTIC`. Saved
bundles have distinct diagnostic schemas; production attestation readers reject
them. A fixture flag, cached test anchor, fabricated receipt, arbitrary reviewer or
per-call policy cannot promote diagnostics into production approval.

| Context | Anchor source | Caller override | Official approval |
| --- | --- | --- | --- |
| Agent proposal CLI | None | None | No |
| Agent review import | None; submissions only | None | No |
| Direct production authentication | Protected enrollment unavailable | Explicitly rejected | No; fails closed |
| Supervisor enrollment workflow | Independently confirmed pin/tip in protected context | Separate enrollment only | Public pending record only in this build |
| Production B2/B3 analysis | Same unavailable protected authority | Explicitly rejected | No; fails closed |
| Synthetic diagnostic APIs | Disposable explicit test pin/tip | Diagnostic expectations only | Never; distinct untrusted schemas |

## Correction, rollback and scientific limits

Corrections preserve old events, require a newly signed current complete ledger and
change the expected tip. Diagnostics independently compare the retained tip. Deleting
an entire later history suffix cannot be detected without the externally retained
accepted tip/ledger identity; never claim signatures alone ensure freshness.

Cryptographic validity means a key signed these bytes. Trusted human authorization
additionally requires independently enrolled protected authority. Neither establishes
personal inspection, personnel independence or scientific label correctness. The
three draft specifications, nine grouped semantics gaps, selected-cohort limitations,
B1/B2/B3 behavior and later scientific approval gates remain unchanged.
