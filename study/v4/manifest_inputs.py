"""Phase 0: SHA-256 manifest of every Study v3 input that Study v4 reads (read-only)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

V3 = Path("study/v3/runs")
OUT = Path("study/v4/report/phase0/inputs.json")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    groups = {
        "llm_pools": sorted(p for p in (V3 / "phase3" / "llm").glob("*/oml*__s*/*")
                            if p.suffix in (".jsonl", ".json")),
        "u2_units": sorted((V3 / "phase3" / "u2" / "units").glob("*.json")),
        "benchroot_data": sorted((V3 / "benchroot" / "data" / "raw").rglob("*.dat")),
        "benchroot_conversions": sorted((V3 / "benchroot" / "conversions").glob("*.json")),
        "u2_jobs": [V3 / "phase3" / "u2" / "jobs.json"],
    }
    manifest = {name: {p.as_posix(): {"bytes": p.stat().st_size, "sha256": sha256(p)}
                       for p in paths} for name, paths in groups.items()}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")
    for name, files in manifest.items():
        print(name, len(files), "files", f"{sum(f['bytes'] for f in files.values()) / 1e9:.2f} GB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
