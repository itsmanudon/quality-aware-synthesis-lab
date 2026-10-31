"""Repair variant ``integer-round-all-half-even-v3`` (Gate 1 decision 4), reported separately.

SMOTE-style interpolation breaks every integer-declared field of vehicle0 at once, so the
frozen ``integer-half-even-max3-v1`` policy (``rcqasyn.phase6.repair``, at most 3 fields)
rescues none of them. This variant rounds EVERY integer-declared numerical field half-even
(``Decimal(str(value))``, so each edit is at most 0.5) and changes nothing else. It is a new,
declared variant: the frozen policy is not edited or widened, and every Phase 2 report keeps
the unrepaired pool next to the repaired one.

The same guards as the frozen policy apply after rounding: the authoritative postcondition
(``authoritative_postcondition``) and ``complete_record``. A record that still fails keeps its
original payload, and the reason is counted. This is an integer compatibility correction, not
semantic validation.
"""

from __future__ import annotations

import copy
from collections import Counter
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

import pandas as pd

from rcqasyn.phase3.validators import number
from rcqasyn.phase5.geometry import complete_record
from rcqasyn.phase6.repair import authoritative_postcondition

POLICY = {
    "version": "integer-round-all-half-even-v3",
    "maximum_fields": None,
    "maximum_absolute_edit": "0.5",
    "rounding": "Decimal(str(JSON number)), ROUND_HALF_EVEN",
    "frozen_policy_unchanged": "integer-half-even-max3-v1",
}


def round_integers(payload: dict[str, Any], spec: dict[str, Any]
                   ) -> tuple[dict[str, Any], int, str | None]:
    """Return (payload, fields edited, failure reason or None).

    The original payload is returned unchanged when nothing needed rounding, or when the
    rounded record would still fail a guard.
    """
    repaired = copy.deepcopy(payload)
    edited = 0
    for field in spec["features"]:
        name = field["name"]
        if (field["type"] != "numerical"
                or not field.get("source_declaration", "").startswith("integer")
                or not number(payload.get(name)) or payload[name] == int(payload[name])):
            continue
        original = Decimal(str(payload[name]))
        rounded = original.to_integral_value(rounding=ROUND_HALF_EVEN)
        if abs(rounded - original) > Decimal(POLICY["maximum_absolute_edit"]):
            raise AssertionError("half-even rounding moved a value by more than 0.5")
        repaired[name] = int(rounded)
        edited += 1
    if not edited:
        return payload, 0, None
    reason = authoritative_postcondition(spec, repaired)
    if reason is None and not complete_record(repaired, spec):
        reason = "OTHER_UNRESOLVED_LABELED_RECORD_REQUIREMENT"
    if reason is not None:
        return payload, edited, reason
    return repaired, edited, None


def repair_pool(candidates: pd.DataFrame, spec: dict[str, Any]
                ) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Apply the variant to a candidate frame; returns the frame and outcome counts."""
    outcomes: Counter[str] = Counter()
    fields_edited: Counter[int] = Counter()
    rows = []
    for payload in candidates.to_dict(orient="records"):
        before = complete_record(payload, spec)
        repaired, edited, reason = round_integers(payload, spec)
        fields_edited[edited] += 1
        if edited == 0:
            outcomes["complete_unchanged" if before else "incomplete_no_integer_edit"] += 1
        elif reason is None:
            outcomes["recovered" if not before else "rounded_already_complete"] += 1
        else:
            outcomes["still_failing:" + reason] += 1
        rows.append(repaired)
    frame = pd.DataFrame(rows, columns=candidates.columns)
    return frame, {"policy": POLICY, "candidates_n": len(candidates),
                   "outcomes": dict(outcomes),
                   "fields_edited_histogram": {str(k): v for k, v in sorted(fields_edited.items())},
                   "complete_before_n": sum(complete_record(r, spec) for r in
                                            candidates.to_dict(orient="records")),
                   "complete_after_n": sum(complete_record(r, spec) for r in rows)}
