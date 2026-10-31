"""Assemble the gitignored project root for the 40 benchmark datasets (main venv).

For every conversion written by ``bench_convert.py`` (U2 venv) this writes
``configs/datasets/oml<id>.yaml`` (features, categorical/numerical split and target taken
from the conversion record; ``preserve_as_null`` missing policy; the stratified 80/20 split
policy of the dev configs), copies ``docs/datasets.md``, then runs the existing
``rcqasyn datasets record-acquisition`` and ``rcqasyn datasets prepare --seed 42`` with
``--root`` so the manifests ``dataset_specification`` re-verifies are produced by the
standard tooling. The converted file's SHA-256 must equal the conversion record. The
protected ``configs/`` and ``data/`` trees are not touched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = REPO / "study" / "v3"
BENCHROOT = HERE / "runs" / "benchroot"
CLI = Path(sys.executable).with_name("rcqasyn.exe")


def _yaml_list(values: list[str]) -> str:
    return "[" + ", ".join(json.dumps(v) for v in values) + "]"


def config_text(info: dict) -> str:
    features = info["features"]
    categorical = info["categorical"]
    numerical = [f for f in features if f not in categorical]
    return "\n".join([
        f"dataset_id: {info['dataset_id']}",
        (f"display_name: OpenML {info['openml_id']} {json.dumps(info['openml_name'])} "
         f"(Study v3 KEEL conversion)"),
        f"raw_path: {info['output_path']}",
        f"accepted_filenames: [{info['dataset_id']}.dat]",
        "format: keel_dat",
        "target_column: class",
        f"feature_columns: {_yaml_list(features)}",
        f"categorical_columns: {_yaml_list(categorical)}",
        f"numerical_columns: {_yaml_list(numerical)}",
        "missing_policy: preserve_as_null",
        "minority_label: positive",
        "task_type: classification",
        f"source_url: {info['source_url']}",
        f"source_page: https://www.openml.org/d/{info['openml_id']}",
        "preprocessing: [study_v3_keel_conversion]",
        "metadata:",
        (f"  identity_provenance: OpenML {info['openml_id']} v{info['version']} ARFF, "
         f"SHA-256 {info['source_sha256']}"),
        "  schema_provenance: ARFF declarations converted by study/v3/bench_convert.py",
        "  label_provenance: minority source label mapped to positive (U2 sources are binary)",
        "  statistics_provenance: conversion record study/v3/runs/benchroot/conversions",
        "split:",
        "  test_size: 0.2",
        "  seed_offset: 0",
        "  stratify: true",
        ""])


def build(root: Path = BENCHROOT, only: list[str] | None = None) -> dict[str, str]:
    (root / "configs" / "datasets").mkdir(parents=True, exist_ok=True)
    (root / "docs").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO / "docs" / "datasets.md", root / "docs" / "datasets.md")
    status = {}
    for path in sorted((root / "conversions").glob("oml*.json")):
        info = json.loads(path.read_text(encoding="utf-8"))
        dataset = info["dataset_id"]
        if only and dataset not in only:
            continue
        raw = root / info["output_path"]
        if hashlib.sha256(raw.read_bytes()).hexdigest() != info["output_sha256"]:
            raise ValueError(f"{dataset}: converted file differs from its record")
        (root / "configs" / "datasets" / f"{dataset}.yaml").write_text(config_text(info),
                                                                     encoding="utf-8")
        manifests = root / "data" / "manifests" / dataset
        if not (manifests / "source.json").exists():
            subprocess.run([str(CLI), "datasets", "record-acquisition", dataset, "--root",
                            str(root), "--source-url", info["source_url"]], check=True,
                           capture_output=True)
        if not (manifests / "split_manifest.json").exists():
            subprocess.run([str(CLI), "datasets", "prepare", dataset, "--root", str(root),
                            "--seed", "42"], check=True, capture_output=True)
        status[dataset] = "ok"
        print(dataset, "ok", flush=True)
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", default=None)
    args = parser.parse_args(argv)
    build(only=args.only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
