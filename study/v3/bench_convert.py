"""Convert the 40 verified OpenML benchmark ARFF files to KEEL-format files (U2 venv only).

The RC-QASyn gate's specification builder reads KEEL declarations (``inspect_keel``) and the
literal labels positive/negative. To reuse it unchanged, each acquired ARFF (SHA-256 checked
against ``report/acquisitions.json``) is rewritten as a KEEL ``.dat`` with a declared,
recorded and deterministic transformation:

* attributes OpenML marks as row id or ignore are dropped, as U2's loader drops them;
* the default target attribute becomes ``class``; its minority label (by count) becomes
  ``positive`` and the other ``negative`` (U2's sources are already binary);
* ARFF INTEGER -> ``integer``, NUMERIC/REAL -> ``real``, nominal -> the declared category
  list. Ranges are NOT written, so no TEST-derived bound enters a declaration;
* names and category tokens are sanitised for the KEEL grammar (``[^A-Za-z0-9_.-]`` ->
  ``_``); the full mapping is recorded and must be one-to-one;
* missing values become ``?``; row order is kept (row identity = original position);
* STRING/DATE attributes are dropped and recorded (none expected).

Output: ``<root>/data/raw/<id>/<id>.dat`` and ``<root>/conversions/<id>.json`` with source
and output SHA-256, counts and mappings. Dataset ids are ``oml<openml_id>``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TOKEN = re.compile(r"[^A-Za-z0-9_.-]")


def clean(token: str) -> str:
    value = TOKEN.sub("_", str(token).strip())
    return value or "_"


def _one_to_one(mapping: dict[str, str], what: str, *, fold_case: bool) -> None:
    """Sanitised tokens must stay distinct; names also case-insensitively (the spec builder
    looks attributes up by lower-cased name), categories only exactly (compared exactly)."""
    values = [v.lower() for v in mapping.values()] if fold_case else list(mapping.values())
    if len(set(values)) != len(mapping):
        raise ValueError(f"sanitised {what} collide: {mapping}")


def _split_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [v.strip() for v in str(value).split(",") if v.strip()]


def convert(record: dict[str, Any], meta: dict[str, Any], root: Path) -> dict[str, Any]:
    import arff  # type: ignore[import-not-found]  (liac-arff, U2 venv only)

    source = HERE / record["local_path"]
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != record["sha256"]:
        raise ValueError(f"{source}: SHA-256 differs from the acquisition record")
    loaded = arff.loads(data.decode("utf-8", errors="replace"))
    attributes: list[tuple[str, Any]] = loaded["attributes"]
    rows: list[list[Any]] = loaded["data"]
    target = meta["default_target"]
    dropped = set(_split_list(meta.get("row_id_attribute"))) | set(
        _split_list(meta.get("ignore_attribute")))
    names = [a for a, _ in attributes]
    if target not in names:
        raise ValueError(f"target {target!r} not among ARFF attributes")
    keep, dropped_types = [], {}
    for index, (name, kind) in enumerate(attributes):
        if name == target or name in dropped:
            continue
        if isinstance(kind, str) and kind.upper() in ("STRING", "DATE") or (
                isinstance(kind, str) and kind.upper().startswith("DATE")):
            dropped_types[name] = kind
            continue
        keep.append(index)
    t_index = names.index(target)
    labels = [r[t_index] for r in rows]
    if any(v is None for v in labels):
        raise ValueError("missing target labels")
    counts = Counter(str(v) for v in labels)
    if len(counts) != 2:
        raise ValueError(f"expected 2 target labels, got {dict(counts)}")
    minority = min(counts, key=lambda k: (counts[k], k))
    name_map = {names[i]: clean(names[i]) for i in keep}
    _one_to_one({**name_map, "__target__": "class"}, "attribute names", fold_case=True)
    declarations, category_maps = [], {}
    for i in keep:
        name, kind = attributes[i]
        if isinstance(kind, list):
            cmap = {str(c): clean(c) for c in kind}
            _one_to_one(cmap, f"categories of {name}", fold_case=False)
            category_maps[name] = cmap
            declarations.append(f"@attribute {name_map[name]} {{{','.join(cmap.values())}}}")
        elif str(kind).upper() == "INTEGER":
            declarations.append(f"@attribute {name_map[name]} integer")
        else:
            declarations.append(f"@attribute {name_map[name]} real")
    declarations.append("@attribute class {positive,negative}")

    def fmt(i: int, value: Any) -> str:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return "?"
        kind = attributes[i][1]
        if isinstance(kind, list):
            return category_maps[attributes[i][0]][str(value)]
        if str(kind).upper() == "INTEGER":
            if float(value) != int(float(value)):
                raise ValueError(f"non-integral value in INTEGER attribute {attributes[i][0]}")
            return str(int(float(value)))
        return repr(float(value))

    dataset_id = f"oml{record['openml_id']}"
    lines = [f"@relation {dataset_id}", *declarations,
             "@inputs " + ", ".join(name_map[names[i]] for i in keep), "@outputs class",
             "@data"]
    missing = 0
    for r in rows:
        values = [fmt(i, r[i]) for i in keep]
        missing += values.count("?")
        values.append("positive" if str(r[t_index]) == minority else "negative")
        lines.append(", ".join(values))
    out = root / "data" / "raw" / dataset_id / f"{dataset_id}.dat"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    out.write_bytes(payload)
    info = {"dataset_id": dataset_id, "key": record["key"], "openml_id": record["openml_id"],
            "openml_name": record["openml_name"], "version": record["version"],
            "source_url": record["url"], "source_sha256": record["sha256"],
            "output_path": str(out.relative_to(root)).replace("\\", "/"),
            "output_sha256": hashlib.sha256(payload).hexdigest(),
            "target_attribute": target, "label_mapping": {str(minority): "positive",
                                                          **{k: "negative" for k in counts
                                                             if k != minority}},
            "class_counts": {"positive": counts[minority],
                             "negative": len(labels) - counts[minority]},
            "rows": len(rows), "dropped_row_id_or_ignore": sorted(dropped & set(names)),
            "dropped_string_or_date": dropped_types, "name_map": name_map,
            "category_maps": category_maps, "missing_cells": missing,
            "features": [name_map[names[i]] for i in keep],
            "categorical": [name_map[attributes[i][0]] for i in keep
                            if isinstance(attributes[i][1], list)],
            "integer": [name_map[attributes[i][0]] for i in keep
                        if str(attributes[i][1]).upper() == "INTEGER"]}
    (root / "conversions").mkdir(parents=True, exist_ok=True)
    (root / "conversions" / f"{dataset_id}.json").write_text(json.dumps(info, indent=1),
                                                             encoding="utf-8")
    return info


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=HERE / "runs" / "benchroot")
    parser.add_argument("--only", nargs="*", default=None, help="OpenML ids")
    args = parser.parse_args()
    acquisitions = json.loads((HERE / "report" / "acquisitions.json").read_text("utf-8"))
    metadata = json.loads((HERE / "report" / "source-metadata.json").read_text("utf-8"))
    sources = json.loads((HERE / "sources.json").read_text("utf-8"))["datasets"]
    for entry in sources:
        if entry["role"] != "benchmark":
            continue
        if args.only and str(entry["openml_id"]) not in args.only:
            continue
        record = acquisitions[entry["key"]]
        if record.get("status") != "ok":
            print(entry["key"], "UNAVAILABLE", flush=True)
            continue
        out = args.root / "conversions" / f"oml{entry['openml_id']}.json"
        if out.exists():
            continue
        info = convert(record, metadata[entry["key"]], args.root)
        print(info["dataset_id"], info["rows"], len(info["features"]), info["class_counts"],
              "missing", info["missing_cells"], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
