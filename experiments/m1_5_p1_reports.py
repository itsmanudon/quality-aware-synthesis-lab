"""M1.5 P1 report roll-up.

Reads completed P1 run directories (and the prior P0-v3 runs for the diversity
scaling comparison), runs the diagnostic-only copying / TRAIN-support analysis,
and writes reports into a fresh ``artifacts/derived/p1-reports-<execution-id>/``
namespace. An existing historical P1 review selection is consumed as recorded.

Usage:
    python experiments/m1_5_p1_reports.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from rcqasyn.experiments import (
    copying_diagnostics,
    cross_dataset_comparison,
    diversity_scaling,
    p1_human_review_sample,
    support_diagnostics,
)
from rcqasyn.experiments.diagnostics import classify_b2_reason
from rcqasyn.experiments.readers import validate_source
from rcqasyn.storage.artifacts import create_run_dir, immutable_text_stream, write_json
from rcqasyn.storage.ownership import file_hash, seal_bundle

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "artifacts" / "runs"
OUT = ROOT / "artifacts" / "reports" / "p1"

P1 = {
    "page-blocks0": "m1-p1-real-page-blocks0-gemma4-e4b-20260829",
    "Ecoli4": "m1-p1-real-Ecoli4-gemma4-e4b-20260829",
    "Abalone19": "m1-p1-real-Abalone19-gemma4-e4b-20260829",
}
P0V3 = {
    "page-blocks0": "m1-p0-real-v3-page-blocks0-gemma4-e4b-20260829",
    "Ecoli4": "m1-p0-real-v3-Ecoli4-gemma4-e4b-20260829",
    "Abalone19": "m1-p0-real-v3-Abalone19-gemma4-e4b-20260829",
}


def _w(name: str, value: Any) -> None:
    write_json(OUT / name, value)
    print(f"wrote {OUT / name}")


def write_disagreement_summary(value: Any) -> None:
    """Write the stable cross-dataset disagreement-summary artifact."""

    _w("p1_b2_b3_disagreements_summary.json", value)


def _read(run_dir: Path, rel: str) -> Any:
    validate_source(run_dir)
    return json.loads((run_dir / rel).read_text(encoding="utf-8"))


def _jsonl(run_dir: Path, rel: str) -> list[dict[str, Any]]:
    p = run_dir / rel
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []


def _review_sample(run_dirs: list[Path]) -> dict[str, Any]:
    recorded = ROOT / "artifacts" / "reports" / "p1" / "p1_human_review.csv"
    return p1_human_review_sample(
        run_dirs, ROOT, OUT / "p1_human_review.csv", target=120, seed=42,
        recorded_sample=recorded if recorded.is_file() else None,
    )


def main() -> None:
    global OUT
    OUT = create_run_dir(ROOT / "artifacts" / "derived", f"p1-reports-{uuid4().hex}")
    p1_dirs = [RUNS / r for r in P1.values()]
    p0_dirs = [RUNS / r for r in P0V3.values()]

    copying = {name: copying_diagnostics(RUNS / rid, ROOT, write=False) for name, rid in P1.items()}
    support = {name: support_diagnostics(RUNS / rid, ROOT, write=False) for name, rid in P1.items()}
    comparisons = {name: _read(RUNS / rid, "comparison.json") for name, rid in P1.items()}

    _w("source_provenance.json", {rid: {"manifest_sha256": file_hash(RUNS / rid / "manifest.json"), "comparison_sha256": file_hash(RUNS / rid / "comparison.json")} for rid in (*P1.values(), *P0V3.values())})

    # --- P1 cross-dataset comparison (existing machine-only builder) -----------
    _w("p1_cross_dataset_comparison.json", cross_dataset_comparison(list(comparisons.values())))

    # --- P0-v3 vs P1 diversity scaling ---------------------------------------
    _w("p0v3_vs_p1_diversity.json", diversity_scaling(p0_dirs, p1_dirs))

    # --- copying diagnostic report -----------------------------------------
    _w("p1_copying_diagnostics.json", {
        name: {"overall": c["overall"], "by_target_class": c["by_target_class"],
               "by_requested_class": c["by_requested_class"],
               "reference_examples_shown": c["reference_examples_shown"]}
        for name, c in copying.items()
    })

    # --- class-conditional report ----------------------------------------
    _w("p1_class_conditional.json", {
        name: {
            "diversity_by_class": copying[name]["by_requested_class"],
            "intrinsic_class_conditional": cmp["baselines"]["b1"]["intrinsic"].get("class_conditional", {}),
            "minority_analysis": cmp.get("minority_analysis", {}),
        }
        for name, cmp in comparisons.items()
    })

    # --- support-distance diagnostic summary ----------------------------
    _w("p1_support_distance_summary.json", {
        name: {k: s[k] for k in ("overall", "by_target_class", "distance_representation",
                                 "exact_train_contact_count", "train_rows")}
        for name, s in support.items()
    })

    # --- B1/B2/B3 comparison ------------------------------------------
    b_rows = {}
    for name, cmp in comparisons.items():
        b = cmp["baselines"]
        b_rows[name] = {
            side: {"accepted": b[side]["accepted"], "raw_pool": b[side]["raw_pool_count"],
                   "acceptance_rate": b[side]["acceptance_rate"],
                   "failure_counts": b[side].get("failure_counts", {})}
            for side in ("b1", "b2", "b3")
        }
        b_rows[name]["b3_detail"] = {
            k: b["b3"].get(k) for k in ("judge_rejections", "judge_malformed",
                                        "judge_provider_failures", "judge_rejection_rate")
        }
    _w("p1_b1_b2_b3.json", b_rows)

    # --- TRTR / TSTR table ---------------------------------------------
    def util(cmp: dict[str, Any]) -> dict[str, Any]:
        b = cmp["baselines"]
        out = {"TRTR": b["b1"]["utility"].get("TRTR", {})}
        for side in ("b1", "b2", "b3"):
            out[f"{side}_TSTR"] = b[side]["utility"].get("TSTR", {})
        return out
    _w("p1_trtr_tstr.json", {name: util(cmp) for name, cmp in comparisons.items()})

    # --- quality-cost table ------------------------------------------
    qc = {}
    for name, cmp in comparisons.items():
        raw = cmp["raw_pool_count"]
        uniq = cmp["baselines"]["b1"]["unique_count"]
        it, ot = cmp.get("input_tokens"), cmp.get("output_tokens")
        gen_out = cmp.get("generation_output_tokens")
        gen_in = cmp.get("generation_input_tokens")
        jt = cmp.get("judge_total_tokens")
        qc[name] = {
            "generation_calls": cmp.get("generation_attempted_calls"),
            "judge_calls": cmp.get("judge_attempted_calls"),
            "input_tokens": it, "output_tokens": ot, "total_tokens": cmp.get("total_tokens"),
            "generation_input_tokens": gen_in, "generation_output_tokens": gen_out,
            "judge_total_tokens": jt,
            "latency_ms": cmp.get("latency_ms"),
            "generation_latency_ms": cmp.get("generation_latency_ms"),
            "judge_latency_ms": cmp.get("judge_latency_ms"),
            "cost_usd": cmp.get("cost_usd"),
            "raw_records": raw, "unique_records": uniq,
            "gen_output_tokens_per_generated_record": (gen_out / raw) if isinstance(gen_out, (int, float)) and raw else None,
            "gen_output_tokens_per_unique_record": (gen_out / uniq) if isinstance(gen_out, (int, float)) and uniq else None,
            "judge_tokens_per_record": (jt / raw) if isinstance(jt, (int, float)) and raw else None,
        }
    _w("p1_quality_cost.json", qc)

    # --- cross-dataset B2/B3 disagreement CSV with reason class ---------
    dis_rows: list[dict[str, str]] = []
    for name, rid in P1.items():
        run_dir = RUNS / rid
        for row in csv.DictReader((run_dir / "b2_b3_disagreements.csv").open(newline="", encoding="utf-8")):
            row["b2_reason_class"] = classify_b2_reason(row.get("b2_reasons", ""), row.get("b2_reasons", ""))
            row["direction"] = (
                "B2_ACCEPT_B3_REJECT" if row["b2_status"] == "accepted" else "B2_REJECT_B3_ACCEPT"
            )
            dis_rows.append(row)
    if dis_rows:
        cols = [*dict.fromkeys(k for r in dis_rows for k in r)]
        with immutable_text_stream(OUT / "p1_b2_b3_disagreements.csv") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(dis_rows)
        print(f"wrote {OUT / 'p1_b2_b3_disagreements.csv'} ({len(dis_rows)} rows)")
    write_disagreement_summary({
        name: {
            "rows": sum(1 for r in dis_rows if r["dataset_id"] == comparisons[name]["dataset_id"]),
            "by_direction": _count(dis_rows, comparisons[name]["dataset_id"], "direction"),
            "by_reason_class": _count(dis_rows, comparisons[name]["dataset_id"], "b2_reason_class"),
        }
        for name in P1
    })

    # --- Consume recorded P1 selection, or sample new candidates ----------
    hr = _review_sample(p1_dirs)
    _w("p1_human_review_manifest.json", hr)
    seal_bundle(OUT)
    print("human review:", hr)


def _count(rows: list[dict[str, str]], dataset_id: str, key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        if r["dataset_id"] == dataset_id:
            out[r[key]] = out.get(r[key], 0) + 1
    return out


if __name__ == "__main__":
    main()
