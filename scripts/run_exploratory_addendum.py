"""Run the exploratory addendum declared in addendum/v1/addendum-v1.json (once)."""
from __future__ import annotations

import argparse
from pathlib import Path

from rcqasyn.empirical.addendum import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(Path(__file__).resolve().parents[1], args.source_root.resolve(), args.output.resolve())
    print(result["status_counts"], result["rows_by_track"], result["result_content_fingerprint"])
