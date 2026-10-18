# Phase-2 supervisor authorization v1

This approval-specific contract corrects Gate-A finding F1. It does not change
the occurrence crosswalk, corrected cohort, overlap, dataset specifications,
annotation protocol or scientific controls. No real labels, supervisor keys,
trust configuration or real signatures were created by this implementation.

## Four distinct states

1. An AGENT proposal remains immutable and PENDING_HUMAN_APPROVAL.
2. A reviewer submits a decision as SUBMITTED, with a label or a pending blank,
   or as UNRESOLVED with a blank label. Events use supervisor-review-event-v2
   and SUBMITTED_UNVERIFIED. These are claims, not authenticated human approval.
3. A supervisor explicitly signs one complete approval ledger in a separate
   trusted context. Approval import verifies the signature, trusted key,
   supervisor identity and every source/proposal/history binding.
4. Official analysis independently repeats that verification. An imported
   status flag, local seal, reviewer string or label column grants no authority.

The decision importer rejects untrusted review_status=APPROVED, including the
exact F1 agent-self-approval reproduction. Use SUBMITTED for review data.
Reviewer references matching any proposal annotator version are rejected after
case/whitespace normalization. This role comparison is defense in depth, not
authentication. A different agent name or invented provenance cannot replace
the signature.

Old unsigned supervisor-review-event-v1 history remains readable evidence but
cannot authenticate labels. Do not rewrite it. Resubmit decisions into a new
approval-specific history namespace. Original proposals and all past events stay
intact.

## Canonical ledger and detached Ed25519 signature

The maintained cryptography dependency implements Ed25519; no cryptographic
primitive is implemented in this repository. The signed message is:

- the exact ASCII prefix RC-QASyn/supervisor-approval-ledger/v1 followed by a NUL;
- UTF-8 JSON of the validated supervisor-approval-ledger-v1 object, sorted keys,
  compact separators, ensure_ascii=true and allow_nan=false.

Contract-normalized string changes are rejected. Approval JSON rejects duplicate
object keys. JSON formatting changes outside values are immaterial because the
message is canonical JSON.

The ledger binds Phase-1 freeze, population kind, corrected cohort fingerprint,
ordered crosswalk fingerprints, annotation protocol version/fingerprint, exact
Gate-A approval fingerprint, complete proposal-ledger fingerprint, all reviewed
decisions, occurrence IDs, payload/proposal hashes, final labels, per-record
APPROVED requests, reviewer references, correction notes/provenance, and the
ordered correction-history fingerprints and current tip. An unsigned ledger's
APPROVED values describe the requested operation; they authorize nothing.

supervisor-signature-v1 contains the Ed25519 detached signature as 128 lowercase
hex characters and a key ID equal to SHA-256 of the raw 32-byte public key.
supervisor-attestation-v1 combines that signature with the ledger. It cannot
supply a public key, authenticated=true flag or alternate verification policy.

## Provision trust outside the agent context

There is deliberately no bundled production trust file, default key, key
generation command, environment-key fallback or signing during import/analysis.
Without a trusted configuration and signature, approval consumption fails closed.

The supervisor must create and retain an encrypted Ed25519 PKCS8 signing key
using trusted credential tooling in a separate protected context. Do not give
the private key or password to the coding/labeling agent. Export only its raw
32-byte public key, compute its SHA-256 key ID, and provision an external JSON:

~~~json
{
  "schema_version": "supervisor-trust-v1",
  "reviewer_reference": "<supervisor's explicit reference>",
  "key_id": "<SHA-256 of raw public key, 64 lowercase hex characters>",
  "public_key_hex": "<raw 32-byte public key, 64 lowercase hex characters>"
}
~~~

This configuration is an operator trust anchor, not review data. Protect its
integrity with OS permissions or a separate account/machine: autonomous agents
must not be able to replace it, select a replacement trusted credential in an
unattended privileged invocation, or access the private key. Explicitly selecting
--trust-config is a privileged supervisor/operator configuration action.
Never obtain that path or key from an incoming CSV/JSON.

The loader requires an absolute external path, rejects configuration inside
repositories or the review-data hierarchy, and verifies key-ID consistency.
These checks prevent accidental bundling; they do not prove OS ownership or
establish that a user-controlled path is trustworthy. Deployment permissions and
the operator's explicit provisioning establish that boundary.

The trusted public key is bound to one supervisor reference; all final decisions
must name that supervisor. Different reviewer-identity models require a separate
approved design. No second human identity is invented.

## Practical review and offline signing

All actual proposal generation still requires external Gate-A verification and
supervisor approval. Gate-A metadata remains a separate external review record;
the final signed ledger additionally binds its exact identity.

After that gate, use the existing proposal export. The supervisor reviews rows,
accepts/corrects labels, supplies their reference and provenance, and submits
SUBMITTED decisions. Changed labels need notes. Incomplete/UNRESOLVED rows may be
saved and resumed. They cannot yield an approval ledger or official analysis.

~~~text
phase2 review-export CHECKPOINT EXPORT --history HISTORY --source-root SOURCE
phase2 review GATE_A_JSON DECISIONS_CSV_OR_JSON CHECKPOINT HISTORY --source-root SOURCE
phase2 approval-export GATE_A_JSON CHECKPOINT HISTORY REVIEWER_REFERENCE UNSIGNED_EXPORT --source-root SOURCE
~~~

review-export retains original proposals and separately exports the latest
unverified submitted decisions (JSON and submitted-decisions.csv). It never
promotes original proposal fields into human labels. approval-export refuses a
missing record, blank final label or unresolved latest decision, and writes
ledger.json for explicit inspection. It does not sign it.

Move ledger.json and the relevant public review/history evidence to the
supervisor's trusted context. Inspect every required row and fingerprint.
There, using a trusted reviewed copy of this software, run:

~~~text
python scripts/sign_phase2_review.py --ledger LEDGER_JSON --private-key EXTERNAL_ENCRYPTED_KEY --output ATTESTATION_JSON --confirm-reviewed
~~~

The helper reads an existing encrypted Ed25519 key, obtains its password
interactively, signs only the canonical ledger, and writes public attestation
data. It never generates/stores a signing key, logs its password, or overwrites
an output. Do not invoke this helper with an actual supervisor key from an
autonomous agent context. Tests exercise it with disposable encrypted TEMP keys
only. Public-key provisioning is separate from this signing operation.

Transfer the public attestation back, then authenticate and consume it:

~~~text
phase2 approval-import GATE_A_JSON CHECKPOINT HISTORY ATTESTATION_JSON EXTERNAL_TRUST_CONFIG AUTHENTICATED_OUTPUT --source-root SOURCE
phase2 analyze GATE_A_JSON CHECKPOINT HISTORY ANALYSIS_OUTPUT --supervisor-attestation AUTHENTICATED_OUTPUT --trust-config EXTERNAL_TRUST_CONFIG --source-root SOURCE
~~~

Analysis also accepts the original signed attestation JSON directly; both paths
perform the same authentication and source validation. A saved authenticated
bundle's status is never trusted by itself. Every CLI derivative remains under
the implementation worktree's artifacts/reports/phase2 namespace. The audited
source root stays read-only.

## Failure and correction behavior

Missing/unreadable trust, unknown key, bad signature, stale cohort/protocol/
proposal, modified labels or hashes, wrong reviewer, incomplete review, legacy
unsigned approvals, history changes and caller-supplied authorization flags are
refused before authenticated import or analysis output is reserved.

After a correction or reopening, retain prior events and attestations. Export a
new versioned ledger and obtain a new supervisor signature when review is complete.
An earlier signature cannot authorize the changed history. Signing all rows is
one operation; 120 separate signatures are not required.

Synthetic fixture approval uses disposable test credentials and remains explicitly
fixture evidence. Analysis requires fixture_only=True for those tests and reports
official=false. The production CLI exposes no fixture permission switch.

## Operational limits

A verified signature establishes possession of the protected signing credential.
It does not prove that a human personally inspected every row, that the proposed
labels are scientifically correct, or that personnel-independent review occurred.
If an agent can access the signing credential, replace trust configuration, or
modify trusted executing code, that separation is lost. Keep the trusted signing
context and provisioned public-key policy outside agent control.

Signatures bind the current history tip, preventing reuse after an observed
history change or on another cohort. They do not establish freshness against
deletion of an entire later history suffix. Retain the expected accepted tip or
ledger fingerprint in a separate protected supervisor record to detect rollback.
Key revocation/rotation requires deliberate replacement of externally provisioned
trust; there is no automatic fallback to an older key.

Selected-cohort sampling limitations, unverified dataset semantics, actual human
review, and all later scientific approval gates remain unchanged.

Cryptographic API reference:
https://cryptography.io/en/50.0.2/hazmat/primitives/asymmetric/ed25519/
