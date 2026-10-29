"""Restore recorded historical bytes in a separate SOURCE worktree (exploratory addendum).

The historical inventory was hashed on a Windows checkout. Git normalized some of those
files to LF, so a Unix checkout fails the strict integrity check. This writes a file only
when a deterministic CRLF reconstruction reproduces the exact recorded SHA-256; anything
else is refused. It never edits the executing checkout and never weakens a check.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
from pathlib import Path

from rcqasyn.phase2.common import read_bundle
from rcqasyn.phase2.workflow import DEFAULT_OUTPUT, load_preparation

INVENTORY = "artifacts/reports/phase2/gate-a-v3/historical-integrity"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def candidates(relative: str, data: bytes) -> list[bytes]:
    lf = data.replace(b"\r\n", b"\n")
    options = [lf.replace(b"\n", b"\r\n")]
    if relative.endswith(".csv"):
        # Python's csv writer terminates rows with CRLF but keeps in-cell newlines as LF.
        rows = list(csv.reader(io.StringIO(lf.decode("utf-8"), newline="")))
        out = io.StringIO(newline="")
        csv.writer(out).writerows(rows)
        options.append(out.getvalue().encode("utf-8"))
    return options


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True, help="separate SOURCE worktree")
    parser.add_argument("--raw-from", type=Path, required=True,
                        help="root whose data/raw holds the verified KEEL files")
    args = parser.parse_args()
    here = Path(__file__).resolve().parents[1]
    target = args.target.resolve()
    if target == here:
        raise SystemExit("refusing to modify the executing checkout")
    expected: dict[str, str] = dict(read_bundle(here/INVENTORY)["source_files"])
    # Dataset specifications also bind source bytes (for example docs/datasets.md).
    _, _, _, specs = load_preparation(here/DEFAULT_OUTPUT)
    for specification in specs["specifications"]:
        for relative, digest in specification["source_files"].items():
            if expected.setdefault(relative, digest) != digest:
                raise SystemExit(f"conflicting recorded hashes for {relative}")
    log: dict[str, str] = {}
    for relative, digest in sorted(expected.items()):
        path = target/relative
        if relative.startswith("data/raw/") and not relative.endswith(".gitkeep"):
            source = args.raw_from.resolve()/relative
            if sha(source.read_bytes()) != digest:
                raise SystemExit(f"raw input does not match recorded hash: {relative}")
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, path)
            log[relative] = "copied-verified-raw"
            continue
        data = path.read_bytes()
        if sha(data) == digest:
            continue
        restored = next((c for c in candidates(relative, data) if sha(c) == digest), None)
        if restored is None:
            raise SystemExit(f"no exact reconstruction for {relative}; refusing")
        path.write_bytes(restored)
        log[relative] = "restored-crlf-exact"
    print(json.dumps({"target": str(target), "actions": log,
                      "restored": sum(v == "restored-crlf-exact" for v in log.values()),
                      "raw_copied": sum(v == "copied-verified-raw" for v in log.values())},
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
