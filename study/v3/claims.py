"""Per-unit claim locks so parallel workers never compute the same unit twice.

Used by u3_eval.py (U2 venv, imported as a top-level module) and phase3.py curate (main venv).
A lock records its owner's PID; a lock whose process is gone (killed, crashed) is taken over.
Results are written atomically elsewhere, so a half-done unit leaves no partial result.
"""

from __future__ import annotations

import os
import time
from pathlib import Path


def alive(pid: int) -> bool:
    """Whether a process exists (Windows: os.kill(pid, 0) would terminate it, not probe it)."""
    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True
    import ctypes

    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    code = ctypes.c_ulong()
    try:
        ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
    finally:
        kernel32.CloseHandle(handle)
    return bool(ok) and code.value == 259  # STILL_ACTIVE


def claim(target: Path) -> bool:
    """Claim ``target`` (a result file not yet written) for this process."""
    lock = target.with_suffix(".lock")
    for _ in range(2):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                owner = int(lock.read_text(encoding="utf-8").split()[0])
            except (OSError, ValueError, IndexError):
                return False  # being written right now by its owner
            if owner != os.getpid() and alive(owner):
                return False
            lock.unlink(missing_ok=True)
            continue
        os.write(fd, f"{os.getpid()} {time.time():.0f}".encode())
        os.close(fd)
        return not target.exists()
    return False


def release(target: Path) -> None:
    target.with_suffix(".lock").unlink(missing_ok=True)
