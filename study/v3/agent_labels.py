"""Agent labels for the blinded Phase 2 sample. These are NOT human labels.

The user asked the coding agent to label ``blind/review_blind.csv`` because most fields in
these benchmarks (protein-localisation scores, vehicle-silhouette moments) cannot be judged
by a non-expert. The agent never fills a human column (CLAUDE.md), so this module writes a
separate file with ``agent_*`` columns. It is one more automated judge, to be reported as
such and never as human validation. ``blind/review_blind.csv`` is read, never written.

Every verdict comes from the explicit rules below, so it can be checked and reproduced.
Inputs are the record, its ``requested_class`` and the dataset's ``schema_<id>.json``,
nothing else: no hidden key, no B2/B3 or gate result, no TRAIN or TEST data. The
domain thresholds (abalone shape and weight relations, near-binary score fields) come from
the public dataset documentation and general domain knowledge. They were chosen by the
agent after it had read the 105 records once, and they were not adjusted to change any
count. Class membership ("is this believably a member of requested_class?") cannot be
checked from the schemas, which mark it UNVERIFIED, so no rule judges it and every row's
notes say so.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

SAMPLE = Path(__file__).resolve().parent / "report" / "phase2" / "label-sample"
AGENT_COLUMNS = ("agent_valid", "agent_failure_type", "agent_severity",
                 "agent_affected_fields", "agent_confidence", "agent_rules_failed",
                 "agent_notes")
_SEVERITY_ORDER = ("low", "medium", "high", "critical")

# Fields documented as taking (almost) only two values in the UCI/KEEL sources.
_TWO_VALUED = {
    "Ecoli4": {"lip": (0.48, 1.0), "chg": (0.5, 1.0)},
    "ecoli1": {"lip": (0.48, 1.0), "chg": (0.5, 1.0)},
    "yeast3": {"erl": (0.5, 1.0)},
    "yeast4": {"erl": (0.5, 1.0)},
}
_ABALONE = {"Abalone19", "abalone9-18"}
# Abalone shells are oval: diameter is roughly 0.8 x length in the source data.
_DIAM_LEN_RATIO = (0.70, 0.90)
# Heights above this are not seen apart from the two known data-entry errors in the source.
_MAX_PLAUSIBLE_HEIGHT = 0.30


class Finding:
    def __init__(self, rule: str, ftype: str, severity: str, fields: tuple[str, ...],
                 note: str) -> None:
        self.rule, self.ftype, self.severity = rule, ftype, severity
        self.fields, self.note = fields, note


def _range(decl: str) -> tuple[float, float] | None:
    m = re.search(r"\[\s*([-+0-9.eE]+)\s*,\s*([-+0-9.eE]+)\s*\]", decl)
    return (float(m.group(1)), float(m.group(2))) if m else None


def check_record(record: dict[str, Any], requested_class: str,
                 schema: dict[str, Any]) -> list[Finding]:
    out: list[Finding] = []
    target = schema["target"]["target_column"]
    fields = {f["name"]: f for f in schema["fields"]}
    expected = set(fields) | {target}
    missing = sorted(expected - set(record))
    extra = sorted(set(record) - expected)
    if missing:
        out.append(Finding("S1", "MISSING_FIELD", "high", tuple(missing),
                           f"missing {', '.join(missing)}"))
    if extra:
        out.append(Finding("S2", "SCHEMA", "high", tuple(extra),
                           f"undeclared {', '.join(extra)}"))
    if record.get(target) != requested_class:
        out.append(Finding("S3", "TARGET_MISMATCH", "critical", (target,),
                           f"class {record.get(target)!r} != requested {requested_class!r}"))
    for name, spec in fields.items():
        if name not in record:
            continue
        v = record[name]
        decl = spec["source_declaration"]
        if spec["type"] == "categorical":
            if v not in spec["documented_categories"]:
                out.append(Finding("S4", "INVALID_CATEGORY", "high", (name,),
                                   f"{name}={v!r} not in {spec['documented_categories']}"))
            continue
        if isinstance(v, bool) or not isinstance(v, int | float):
            out.append(Finding("S5", "SCHEMA", "high", (name,), f"{name}={v!r} not numeric"))
            continue
        if decl.startswith("integer") and not float(v).is_integer():
            out.append(Finding("S6", "SCHEMA", "medium", (name,), f"{name}={v} not integer"))
        bounds = _range(decl)
        if bounds and not bounds[0] <= v <= bounds[1]:
            out.append(Finding("S7", "NUMERIC_OUTLIER", "medium", (name,),
                               f"{name}={v} outside declared [{bounds[0]:g}, {bounds[1]:g}]"))
    ds = schema["dataset_id"]
    for name, allowed in _TWO_VALUED.get(ds, {}).items():
        if name in record and record[name] not in allowed:
            out.append(Finding("D1", "STATISTICAL_IMPLAUSIBILITY", "low", (name,),
                               f"{name}={record[name]} but source takes only {allowed}"))
    if ds in _ABALONE and not missing:
        out.extend(_abalone(record))
    return out


def _abalone(r: dict[str, Any]) -> list[Finding]:
    out: list[Finding] = []
    length, diam, height = r["length"], r["diameter"], r["height"]
    whole = r["whole_weight"]
    parts = {k: r[k] for k in ("shucked_weight", "viscera_weight", "shell_weight")}
    if diam > length:
        out.append(Finding("A1", "LOGICAL_INCONSISTENCY", "high", ("diameter", "length"),
                           f"diameter {diam} > length {length}"))
    if height > diam:
        out.append(Finding("A2", "LOGICAL_INCONSISTENCY", "medium", ("height", "diameter"),
                           f"height {height} > diameter {diam}"))
    for k, v in parts.items():
        if v >= whole:
            out.append(Finding("A3", "LOGICAL_INCONSISTENCY", "high", (k, "whole_weight"),
                               f"{k} {v} >= whole_weight {whole}"))
    total = round(sum(parts.values()), 6)
    if total > whole:
        out.append(Finding("A4", "LOGICAL_INCONSISTENCY", "medium",
                           (*parts, "whole_weight"),
                           f"shucked+viscera+shell = {total:g} > whole_weight {whole}"))
    if length > 0 and diam <= length:
        ratio = diam / length
        lo, hi = _DIAM_LEN_RATIO
        if not lo <= ratio <= hi:
            out.append(Finding("A5", "STATISTICAL_IMPLAUSIBILITY", "low",
                               ("diameter", "length"),
                               f"diameter/length = {ratio:.3f}, outside typical {lo}-{hi}"))
    if height > _MAX_PLAUSIBLE_HEIGHT:
        out.append(Finding("A6", "STATISTICAL_IMPLAUSIBILITY", "medium", ("height",),
                           f"height {height} > {_MAX_PLAUSIBLE_HEIGHT}"))
    return out


def label_row(row: dict[str, str], schema: dict[str, Any]) -> dict[str, str]:
    record = json.loads(row["record_json"])
    findings = check_record(record, row["requested_class"], schema)
    abalone = schema["dataset_id"] in _ABALONE
    scope = ("schema, range and physical-consistency rules checked" if abalone
             else "only schema/range and value-set rules checkable; features not "
                  "interpretable record by record")
    class_note = "class membership not assessed (schema marks it UNVERIFIED)"
    if not findings:
        return {"agent_valid": "true", "agent_failure_type": "NONE", "agent_severity": "",
                "agent_affected_fields": "", "agent_confidence": "medium" if abalone else "low",
                "agent_rules_failed": "", "agent_notes": f"no rule failed; {scope}; {class_note}"}
    types = list(dict.fromkeys(f.ftype for f in findings))
    fields = list(dict.fromkeys(x for f in findings for x in f.fields))
    severity = max((f.severity for f in findings), key=_SEVERITY_ORDER.index)
    hard = any(f.rule in {"S1", "S2", "S3", "S4", "S5", "S7", "A1", "A3"} for f in findings)
    soft_only = all(f.severity == "low" for f in findings)
    confidence = "high" if hard else ("low" if soft_only else "medium")
    return {"agent_valid": "false", "agent_failure_type": ";".join(types),
            "agent_severity": severity, "agent_affected_fields": ", ".join(fields),
            "agent_confidence": confidence,
            "agent_rules_failed": ";".join(dict.fromkeys(f.rule for f in findings)),
            "agent_notes": "; ".join(f.note for f in findings) + f"; {class_note}"}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Write rule-based agent labels (not human).")
    p.add_argument("--sample", type=Path, default=SAMPLE)
    a = p.parse_args(argv)
    blind = a.sample / "blind"
    out_dir = a.sample / "agent"
    out_dir.mkdir(exist_ok=True)
    with (blind / "review_blind.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    schemas: dict[str, dict[str, Any]] = {}
    labelled = []
    for row in rows:
        ds = row["dataset_id"]
        if ds not in schemas:
            schemas[ds] = json.loads((blind / f"schema_{ds}.json").read_text(encoding="utf-8"))
        base = {k: row[k] for k in ("review_id", "dataset_id", "requested_class", "record_json")}
        labelled.append(base | label_row(row, schemas[ds]))
    out_csv = out_dir / "review_agent_labelled.csv"
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[*labelled[0]], lineterminator="\n")
        w.writeheader()
        w.writerows(labelled)
    per_ds: dict[str, Counter[str]] = {}
    for r in labelled:
        per_ds.setdefault(r["dataset_id"], Counter())[r["agent_valid"]] += 1
    summary = {
        "label_source": "coding agent (rule-based); NOT human labels",
        "rows": len(labelled),
        "agent_valid_counts": {k: dict(sorted(v.items())) for k, v in sorted(per_ds.items())},
        "rules_failed_counts": dict(sorted(Counter(
            x for r in labelled for x in r["agent_rules_failed"].split(";") if x).items())),
        "inputs": ["blind/review_blind.csv", "blind/schema_<dataset>.json"],
        "not_used": ["key/review_key.csv", "B2/B3/gate outputs", "TRAIN/TEST data"],
        "human_columns_filled_by_agent": 0,
    }
    (out_dir / "agent_label_summary.json").write_text(
        json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
