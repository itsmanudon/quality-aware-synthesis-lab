"""Run the pinned U2/UGO benchmark (ml_ugo@a6710ea) on a local dev dataset, unmodified.

Runs inside the isolated U2 environment (``study/v3/vendor/.venv-u2``; ml_ugo pins
pandas 3.x and scikit-learn 1.6, which conflict with rcqasyn's ``pandas<3``), so this file
imports nothing from ``rcqasyn`` or ``study``.

What it does, and what it deliberately does not do:

- Verifies the vendored checkout is at the pinned commit and records the notebook SHA-256.
- Reads the embedded module sources from ``UGO_30_Datasets.ipynb`` with ``ast`` (each
  bundled cell must be a single ``BUNDLE_SOURCES['x.py'] = r'''...'''`` assignment; nothing
  in the notebook is executed), and materializes them exactly as the notebook's own
  materialize cell does, recording the same bundle SHA-256.
- Replaces one function at runtime, ``portable_ugo.benchmark._load_dataset``, with a
  reader for a local, hash-verified KEEL ``.dat`` file. U2's own loader downloads from
  OpenML through the ``openml`` package, which would bypass the one declared Study v3
  fetcher. Labels are factorized exactly as U2 does (sorted), row ids are file order.
  Every other function, default and protocol is the vendored code.

Usage (from the repository root)::

    study/v3/vendor/.venv-u2/Scripts/python.exe -I study/v3/u2_bridge.py \
        --keel data/raw/abalone19/abalone19.dat --sha256 <expected> --name keel-Abalone19 \
        --output study/v3/runs/u2-dev-check [--smoke] [--seeds 42] [--classifiers ...]
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PINNED_COMMIT = "a6710ea760497e91d48c77abda0178b67e250adc"
REPO = Path(__file__).resolve().parents[2]
VENDOR = REPO / "study" / "v3" / "vendor" / "ml_ugo"
NOTEBOOK = VENDOR / "UGO_30_Datasets.ipynb"


def check_pin() -> str:
    head = subprocess.run(["git", "-C", str(VENDOR), "rev-parse", "HEAD"], check=True,
                          capture_output=True, text=True).stdout.strip()
    if head != PINNED_COMMIT:
        raise SystemExit(f"ml_ugo is at {head}, expected pinned {PINNED_COMMIT}")
    dirty = subprocess.run(["git", "-C", str(VENDOR), "status", "--porcelain"], check=True,
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit("ml_ugo checkout has local modifications; it must stay read-only")
    return head


def bundle_sources() -> dict[str, str]:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    sources: dict[str, str] = {}
    for cell in notebook["cells"]:
        text = "".join(cell["source"])
        if cell["cell_type"] != "code" or not text.startswith("# Bundled module:"):
            continue
        tree = ast.parse(text)
        if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Assign):
            raise SystemExit("unexpected bundled-module cell shape; refusing to execute it")
        target = tree.body[0].targets[0]
        if not (isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name)
                and target.value.id == "BUNDLE_SOURCES"):
            raise SystemExit("unexpected bundled-module assignment target")
        key = ast.literal_eval(target.slice)
        value = ast.literal_eval(tree.body[0].value)
        if not isinstance(key, str) or not isinstance(value, str):
            raise SystemExit("bundled module key/value must be string literals")
        sources[key] = value
    return sources


def materialize(sources: dict[str, str], runtime_root: Path) -> str:
    digest = hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest()
    package = runtime_root / digest[:16] / "portable_ugo"
    package.mkdir(parents=True, exist_ok=True)
    for relative, source in sources.items():
        (package / relative).write_text(source, encoding="utf-8")
    sys.path.insert(0, str(package.parent))
    return digest


def read_keel(path: Path) -> tuple[Any, Any, list[str]]:
    import pandas as pd

    attributes: list[tuple[str, str]] = []
    rows: list[list[str]] = []
    in_data = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("%"):
            continue
        if in_data:
            rows.append([cell.strip() for cell in stripped.split(",")])
        elif stripped.lower().startswith("@attribute"):
            body = stripped[len("@attribute"):].strip()
            name, _, kind = body.partition(" ")
            attributes.append((name.strip(), kind.strip()))
        elif stripped.lower() == "@data":
            in_data = True
    names = [name for name, _ in attributes]
    frame = pd.DataFrame(rows, columns=pd.Index(names))
    target_name = names[-1]
    for name, kind in attributes[:-1]:
        if kind.startswith("{"):
            frame[name] = frame[name].astype("category")
        else:
            frame[name] = pd.to_numeric(frame[name])
    nominal = [name for name, kind in attributes[:-1] if kind.startswith("{")]
    return frame.drop(columns=[target_name]), frame[target_name].to_numpy(), nominal


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keel", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--seeds", type=int, nargs="+", default=[42])
    parser.add_argument("--classifiers", nargs="+", default=None)
    args = parser.parse_args()

    commit = check_pin()
    raw = args.keel.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != args.sha256:
        raise SystemExit(f"{args.keel} sha256 {actual} != expected {args.sha256}")
    bundle_sha = materialize(bundle_sources(), args.output / "runtime")

    import numpy as np
    import pandas as pd
    from portable_ugo import benchmark  # type: ignore[import-not-found]

    features, target, nominal = read_keel(args.keel)

    def load_local(entry: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        # Mirrors the vendored loader's contract and metadata keys; only the source differs.
        y, labels = pd.factorize(target, sort=True)
        y = np.asarray(y, dtype=np.int64)
        if len(labels) != 2:
            raise ValueError(f"Expected a binary source, got {len(labels)} classes")
        row_ids = np.arange(len(features), dtype=np.int64)
        metadata = {
            "source": "local_keel_dat_via_study_v3_bridge", "openml_id": 0,
            "catalogue_number": int(entry["number"]), "catalogue_name": entry["name"],
            "imbalance_type": entry["imbalance_type"], "local_path": str(args.keel),
            "local_sha256": actual, "target_attribute": "Class", "row_id_attributes": [],
            "row_id_source": "original_row_position",
            "raw_fingerprint": benchmark._fingerprint(features, target, row_ids),
            "fingerprint_algorithm": "sha256_pandas_raw_values_v1",
            "label_mapping": [{"label": label, "encoded": i} for i, label in enumerate(labels)],
            "feature_dtypes": {str(c): str(d) for c, d in features.dtypes.items()},
            "nominal_columns": nominal, "source_n_rows": len(features),
            "n_features": features.shape[1], "explicit_development_row_cap": None,
            "development_subset": False,
        }
        metadata.update(n_rows=len(y), data_fingerprint=metadata["raw_fingerprint"],
                        class_counts=benchmark._counts(y))
        return {**entry, "X": features.copy(), "y": y, "row_ids": row_ids, "metadata": metadata}

    benchmark._load_dataset = load_local
    catalogue = [{"number": 1, "openml_id": 0, "name": args.name, "imbalance_type": "dev"}]
    config: dict[str, Any] = {
        "DATASET_RANGE": "1-1", "EXCLUDED_DATASETS": [], "SEEDS": args.seeds,
        "SMOKE": bool(args.smoke), "OUTPUT_DIR": str(args.output / "results"),
        "DATA_HOME": str(args.output / "unused_openml_cache"),
    }
    if args.classifiers:
        config["CLASSIFIERS"] = args.classifiers
    provenance = {"ml_ugo_commit": commit, "bundle_sha256": bundle_sha,
                  "notebook_sha256": hashlib.sha256(NOTEBOOK.read_bytes()).hexdigest(),
                  "dataset": args.name, "local_sha256": actual, "config_overrides": config,
                  "replaced_functions": ["portable_ugo.benchmark._load_dataset"]}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "bridge_provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = benchmark.run_benchmark(config, catalogue)
    print("RUN_DIR", result["run_dir"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
