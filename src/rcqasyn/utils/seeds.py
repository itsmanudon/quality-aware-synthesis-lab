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


# Ollama/llama.cpp and the OpenAI ``seed`` parameter are consumed as unsigned
# 32-bit integers; keep derived provider seeds inside that range.
PROVIDER_SEED_MODULUS = 1 << 32


def generation_provider_seed(
    root_seed: int,
    dataset_id: str,
    target_class: str,
    batch_index: int,
    *,
    base_seed: int | None = None,
) -> int:
    """Deterministic per-batch provider seed for a generation call.

    The value is stable across reruns and distinct across dataset, requested
    class, and batch index.  It is derived through :func:`derive_seed` (SHA-256),
    so it does not depend on Python's randomized built-in ``hash()``.  When a
    ``base_seed`` is supplied it is folded in so the configured provider seed
    still influences the result while no longer being reused across batches.
    """

    if not isinstance(batch_index, int) or isinstance(batch_index, bool) or batch_index < 0:
        raise ValueError("batch_index must be a non-negative integer")
    if not dataset_id or not target_class:
        raise ValueError("dataset_id and target_class must be non-empty")
    namespace = f"generation:{dataset_id}:{target_class}"
    parts: tuple[object, ...] = (batch_index,) if base_seed is None else (base_seed, batch_index)
    return derive_seed(root_seed, namespace, *parts) % PROVIDER_SEED_MODULUS
