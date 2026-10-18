"""Bounded a priori offline experiments and one exact evidence replay."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rcqasyn.phase2.common import envelope, write_bundle
from rcqasyn.phase3.contracts import M2Config
from rcqasyn.phase3.workflow import read_results, run_offline


def main(root: Path, source: Path, output_root: Path) -> None:
    design = json.loads((root / "configs/phase3/m2-offline-v1.json").read_text(encoding="utf-8"))
    output = (root / output_root).resolve()
    namespace = (root / "artifacts/reports/phase3").resolve()
    if output == namespace or not output.is_relative_to(namespace):
        raise ValueError("experiment versions must stay under artifacts/reports/phase3")
    runs = []
    for entry in design["configurations"]:
        config = M2Config.model_validate_json(json.dumps({k: v for k, v in entry.items() if k != "name"}))
        destination = output / entry["name"]
        result = read_results(destination) if destination.exists() else run_offline(
            source, root / "artifacts/reports/phase2/gate-a-v3", destination, config, root)
        if result["configuration"] != config.model_dump(mode="json"):
            raise ValueError("existing experiment configuration differs")
        runs.append({"name": entry["name"], "artifact_fingerprint": result["fingerprint"],
                     "evidence_content_fingerprint": result["evidence_content_fingerprint"],
                     "runtime_seconds": result["runtime_seconds"], "evidence_records": len(result["evidence"])})
        print(json.dumps(runs[-1]), flush=True)
    baseline = read_results(output / design["configurations"][0]["name"])
    replay_path = output / "baseline-replay"
    replay = read_results(replay_path) if replay_path.exists() else run_offline(
        source, root / "artifacts/reports/phase2/gate-a-v3", replay_path,
        M2Config.model_validate_json(json.dumps(baseline["configuration"])), root)
    assert baseline["evidence_content_fingerprint"] == replay["evidence_content_fingerprint"]
    assert baseline["model_parameters"] == replay["model_parameters"]
    assert baseline["reference_populations"] == replay["reference_populations"]
    value = envelope("m2-bounded-experiment-manifest-v1", {
        "design": design, "runs": runs, "stable_replay": True,
        "replay_evidence_content_fingerprint": replay["evidence_content_fingerprint"],
        "human_labels_used": False, "test_fitting_or_selection": False,
        "scientific_status": "EXPLORATORY_HUMAN_LABEL_EVALUATION_PENDING"})
    write_bundle(output / "manifest", value)
    print("STABLE OFFLINE REPLAY: PASS", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/reports/phase3/experiments-v2"))
    args = parser.parse_args()
    main(Path.cwd(), args.source_root, args.output_root)
