"""Offline supervisor operation; creates public enrollment evidence, never credentials."""
from __future__ import annotations

import argparse
from pathlib import Path

from rcqasyn.phase2.enrollment import prepare_offline_enrollment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-policy", type=Path, required=True)
    parser.add_argument("--expected-key-id", required=True,
                        help="Fingerprint independently confirmed by the supervisor.")
    parser.add_argument("--expected-history-tip", required=True,
                        help="History tip independently retained by the supervisor.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--confirm-protected-environment", action="store_true", required=True,
                        help="Operator assertion only; this flag does not provide OS isolation.")
    args = parser.parse_args()
    result = prepare_offline_enrollment(args.public_policy, args.expected_key_id,
                                        args.expected_history_tip, args.output)
    print(f"Public enrollment evidence saved: {result}. Production approval remains disabled.")


if __name__ == "__main__":
    main()
