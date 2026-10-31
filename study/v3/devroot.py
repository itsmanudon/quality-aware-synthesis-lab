"""Assemble a read-only project root for the 8 Study v3 dev datasets.

The existing specification builder (``rcqasyn.phase2.specifications.dataset_specification``)
expects a project root with ``configs/datasets/<id>.yaml``, ``data/manifests/<id>/`` and the
raw ``.dat`` at the declared path, and it re-verifies the recorded split and the source
SHA-256. Rather than editing the protected ``configs/`` and ``data/`` trees, this copies the
recorded configs and manifests (top-level for Abalone19/Ecoli4, ``addendum/v1`` for the six
others) next to the KEEL files fetched by the declared fetcher, into the gitignored
``study/v3/runs/devroot``. Every raw file must match the SHA-256 recorded in its manifest.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = REPO / "study" / "v3"
DEVROOT = HERE / "runs" / "devroot"
KEEL_RAW = HERE / "data" / "raw" / "keel"

# dataset_id -> (root holding configs/ and data/manifests/, config file name, fetched folder)
DEV: dict[str, tuple[Path, str, str]] = {
    "Abalone19": (REPO, "abalone19.yaml", "Abalone19"),
    "Ecoli4": (REPO, "ecoli4.yaml", "Ecoli4"),
    "yeast3": (REPO / "addendum" / "v1", "yeast3.yaml", "yeast3"),
    "yeast4": (REPO / "addendum" / "v1", "yeast4.yaml", "yeast4"),
    "vehicle0": (REPO / "addendum" / "v1", "vehicle0.yaml", "vehicle0"),
    "segment0": (REPO / "addendum" / "v1", "segment0.yaml", "segment0"),
    "ecoli1": (REPO / "addendum" / "v1", "ecoli1.yaml", "ecoli1"),
    "abalone9-18": (REPO / "addendum" / "v1", "abalone9-18.yaml", "abalone9-18"),
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _raw_path(config: Path) -> str:
    for line in config.read_text(encoding="utf-8").splitlines():
        if line.startswith("raw_path:"):
            return line.split(":", 1)[1].strip()
    raise ValueError(f"{config} declares no raw_path")


def build(target: Path = DEVROOT) -> dict[str, str]:
    """Copy configs, manifests, docs and verified raw files; return dataset -> raw SHA-256."""
    (target / "configs" / "datasets").mkdir(parents=True, exist_ok=True)
    (target / "docs").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO / "docs" / "datasets.md", target / "docs" / "datasets.md")
    hashes: dict[str, str] = {}
    for dataset, (root, config_name, folder) in DEV.items():
        config = root / "configs" / "datasets" / config_name
        manifest = root / "data" / "manifests" / dataset
        recorded = json.loads((manifest / "source.json").read_text(encoding="utf-8"))
        relative = _raw_path(config)
        raw = KEEL_RAW / folder / Path(relative).name
        actual = sha256_file(raw)
        if actual != recorded["extracted_sha256"]:
            raise ValueError(f"{dataset}: fetched {actual} != recorded "
                             f"{recorded['extracted_sha256']}")
        shutil.copyfile(config, target / "configs" / "datasets" / config_name)
        shutil.copytree(manifest, target / "data" / "manifests" / dataset, dirs_exist_ok=True)
        (target / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(raw, target / relative)
        hashes[dataset] = actual
    return hashes


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True))
