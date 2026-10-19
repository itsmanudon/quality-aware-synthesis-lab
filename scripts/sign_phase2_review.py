"""Supervisor-only offline operation. Never invoke with an actual key from an agent context."""
from __future__ import annotations

import argparse
import getpass
import json
from hashlib import sha256
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from rcqasyn.phase2.approval import read_approval_json, signing_bytes
from rcqasyn.phase2.contracts import (
    ApprovalLedger,
    DetachedSupervisorSignature,
    SupervisorAttestation,
)
from rcqasyn.storage.artifacts import write_json


def sign_review(ledger_path: Path, private_key_path: Path, output: Path) -> None:
    """Use an existing encrypted key in the supervisor's separate protected context."""
    key_path = private_key_path.resolve(strict=True)
    if any((parent / ".git").exists() for parent in key_path.parents):
        raise ValueError("supervisor private key must be outside every repository")
    pem = key_path.read_bytes()
    if not pem.startswith(b"-----BEGIN ENCRYPTED PRIVATE KEY-----"):
        raise ValueError("an existing encrypted PKCS8 supervisor key is required")
    password = getpass.getpass("Supervisor key password (never logged): ").encode("utf-8")
    if not password:
        raise ValueError("empty key password is forbidden")
    key = load_pem_private_key(pem, password=password)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("supervisor key must be Ed25519")
    raw = read_approval_json(ledger_path)
    message = signing_bytes(raw)
    ledger = ApprovalLedger.model_validate_json(json.dumps(raw))
    public = key.public_key().public_bytes_raw()
    signature = DetachedSupervisorSignature(
        key_id=sha256(public).hexdigest(), signature_hex=key.sign(message).hex())
    value = SupervisorAttestation(ledger=ledger, signature=signature)
    write_json(output, value.model_dump(mode="json"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--confirm-reviewed", action="store_true", required=True,
                        help="Explicit operation after inspecting the full ledger and history.")
    args = parser.parse_args()
    sign_review(args.ledger, args.private_key, args.output)


if __name__ == "__main__":
    main()
