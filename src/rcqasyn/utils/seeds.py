from __future__ import annotations

import hashlib


def derive_seed(root_seed: int, namespace: str, *parts: object) -> int:
    """Derive a stable 63-bit seed using SHA-256, independent of process hash randomization."""
    if not isinstance(root_seed, int) or isinstance(root_seed, bool) or root_seed < 0:
        raise ValueError("root_seed must be a non-negative integer")
    if not namespace:
        raise ValueError("namespace must be non-empty")
    payload = "\x1f".join((str(root_seed), namespace, *(str(part) for part in parts))).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") & ((1 << 63) - 1)


stable_seed = derive_seed
