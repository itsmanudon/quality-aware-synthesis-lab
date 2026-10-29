"""Run the exploratory addendum v2 benchmark declared in addendum/v2/addendum-v2.json (once)."""
from __future__ import annotations

import argparse
from pathlib import Path

from rcqasyn.empirical.addendum_v2 import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(Path(__file__).resolve().parents[1], args.source_root.resolve(), args.output.resolve())
    print(result["status_counts"], result["rows_by_category"], result["pool_identity_all_match"],
          result["result_content_fingerprint"])
