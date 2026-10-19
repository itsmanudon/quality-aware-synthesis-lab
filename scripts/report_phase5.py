"""Render a reproducible M7 geometric construction report from sealed study artifacts."""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import itertools

import matplotlib.pyplot as plt

from rcqasyn.phase2.common import csv_text, digest, envelope, read_bundle, verify_envelope
from rcqasyn.phase5.contracts import STRATEGIES
from rcqasyn.storage.artifacts import create_run_dir, write_json, write_text
from rcqasyn.storage.ownership import seal_bundle, write_scope

plt.rcParams.update({"svg.hashsalt":"rcqasyn-phase5-report-v1","font.size":10})
COLORS = {"source-order":"#707B7C", "farthest-first":"#2471A3", "coverage-greedy":"#148F77", "quality-coverage":"#A93226"}


def table(headers: list[str], rows: list[list[Any]]) -> str:
    def cell(v: Any) -> str:
        return "n/a" if v is None else f"{v:.4f}" if isinstance(v,float) else str(v)
    return "\n".join(["| "+" | ".join(headers)+" |","| "+" | ".join(["---"]*len(headers))+" |",*["| "+" | ".join(cell(v) for v in r)+" |" for r in rows]])


def save(fig: Any, output: Path, name: str) -> None:
    for ext in ("png","svg"):
        stream=io.BytesIO(); opts={"metadata":{"Date":None}} if ext=="svg" else {}
        fig.savefig(stream,format=ext,dpi=180,bbox_inches="tight",**opts)
        path=output/f"{name}.{ext}"
        with write_scope(path),path.open("xb") as target: target.write(stream.getvalue())
    plt.close(fig)


def report_data(study: Path, replay: Path | None = None) -> dict[str,Any]:
    manifest=read_bundle(study/"manifest"); verify_envelope(manifest,"m7-experiment-manifest-v1")
    data={}
    for row in manifest["runs"]:
        value=read_bundle(study/"datasets"/row["name"]); verify_envelope(value,"m7-constructed-dataset-v1")
        if value["fingerprint"]!=row["fingerprint"] or digest(value["selected_records"])!=value["selected_content_fingerprint"]:
            raise ValueError("manifest/constructed dataset identity differs")
        audit=json.loads((study/"datasets"/row["name"]/"audit.json").read_text())
        if audit["status"]!="PASS" or audit["constructed_dataset_fingerprint"]!=value["fingerprint"]:
            raise ValueError("missing or mismatched completed dataset audit")
        data[row["name"]]=value
    stable=None
    if replay is not None:
        other=read_bundle(replay/"manifest")
        stable=(manifest["construction_content_fingerprint"]==other["construction_content_fingerprint"]
                and [r["fingerprint"] for r in manifest["runs"]]==[r["fingerprint"] for r in other["runs"]])
        if not stable: raise ValueError("construction replay differs")
    rows=[]
    for row in manifest["runs"]:
        v=data[row["name"]]; m=v["metrics"]; minority=m["minority_literal_label"]
        rows.append({"name":row["name"],"dataset":row["dataset_id"],"strategy":row["strategy"],
            "policy":row["policy"],"control_intersection":row["control_intersection"],
            "budget":row["budget"],"selected_n":row["selected_n"],"eligible_n":v["eligible_n"],"shortfall":v["shortfall"],
            "train_row_coverage":m["train_row_coverage"],"unique_train_feature_coverage":m["unique_train_feature_coverage"],
            "train_region_coverage":m["train_region_coverage"],"balanced_region_coverage":m["class_balanced_region_coverage"],
            "exact_duplicate_rate":m["exact_duplicate_rate"],"near_duplicate_rate":m["near_duplicate_rate"],
            "pairwise_mean":m["pairwise_separation"]["mean"],"nearest_selected_median":m["nearest_selected_distance"]["quantiles"].get("median"),
            "nearest_train_median":m["nearest_train_distance"]["quantiles"].get("median"),
            "minority_label":minority,"same_class_minority_coverage":m["class_coverage"][minority]["coverage_by_same_declared_class"] if minority is not None else None,
            "minority_selected_n":m["class_coverage"][minority]["selected_declared_class_n"] if minority is not None else None,
            "quota_requested":v["minority_quota_requested"],"quota_feasible":v["minority_quota_feasible"],"quota_unavailable":v["minority_quota_unavailable"],
            "dense_region_share":m["dense_region_selection_fraction"],"assignment_hhi":m["nearest_train_region_hhi"],
            "audit_status":"PASS","fingerprint":v["fingerprint"]})
    plan=manifest["plan"]; datasets=sorted(plan["budgets"])
    primary=[r for r in rows if r["policy"]==plan["primary_policy"] and r["control_intersection"] is None]
    stability=[]; sensitivities=[]; cases=[]
    for d in datasets:
        for strategy in STRATEGIES:
            group=sorted([r for r in primary if r["dataset"]==d and r["strategy"]==strategy],key=lambda r:r["budget"])
            for small,large in itertools.pairwise(group):
                a=[r["occurrence_id"] for r in data[small["name"]]["selected_records"]]
                b=[r["occurrence_id"] for r in data[large["name"]]["selected_records"]]
                stability.append({"dataset":d,"strategy":strategy,"small_budget":small["budget"],"large_budget":large["budget"],
                    "exact_prefix":a==b[:len(a)],"smaller_set_retained_fraction":len(set(a)&set(b))/len(a),
                    "jaccard":len(set(a)&set(b))/len(set(a)|set(b))})
        middle=plan["budgets"][d][1]
        main=next(r for r in primary if r["dataset"]==d and r["strategy"]=="quality-coverage" and r["budget"]==middle)
        a={r["occurrence_id"] for r in data[main["name"]]["selected_records"]}
        for row in rows:
            if row["dataset"]==d and row["policy"]!=plan["primary_policy"]:
                b={r["occurrence_id"] for r in data[row["name"]]["selected_records"]}
                sensitivities.append({"dataset":d,"policy":row["policy"],"budget":middle,
                    "eligible_n":row["eligible_n"],"selected_n":row["selected_n"],
                    "selected_jaccard_with_primary":len(a&b)/len(a|b) if a|b else None,
                    "unique_train_feature_coverage":row["unique_train_feature_coverage"],"shortfall":row["shortfall"]})
        for strategy in STRATEGIES:
            run=next(r for r in primary if r["dataset"]==d and r["strategy"]==strategy and r["budget"]==middle)
            value=data[run["name"]]
            if not value["trace"]: continue
            indices=list(dict.fromkeys([0,max(range(len(value["trace"])),key=lambda i:value["trace"][i]["marginal_weighted_coverage"]),len(value["trace"])-1]))
            for index in indices:
                selected=value["selected_records"][index]; trace=value["trace"][index]
                cases.append({"dataset":d,"strategy":strategy,"budget":middle,"dataset_fingerprint":value["fingerprint"],
                    **selected,**trace,"human_approval":"PENDING","not_validity_or_utility_evidence":True})
    decisions=[
        {"decision":"Personal review of all 120 proposals","status":"HUMAN_DECISION_PENDING","evidence":"Preserved Phase-3 review-v2; no human-final labels or approved ledger exists"},
        {"decision":"Domain semantics and literal target mappings","status":"HUMAN_DECISION_PENDING","evidence":"Three frozen specifications; unresolved physical meanings, mappings and cross-field constraints"},
        {"decision":"Radius, quota and objective adequacy","status":"HUMAN_DECISION_PENDING","evidence":"Predeclared .05 radius, .01 near tolerance, availability-capped .5 quota and geometric trade-offs; no utility claim"},
        {"decision":"Scientific acceptance of Phases 3/4/5","status":"HUMAN_DECISION_PENDING","evidence":"Engineering completion, source-bound artifacts and reports; no scientific freeze"},
        {"decision":"Future calibration and leakage-safe utility study","status":"HUMAN_DECISION_PENDING","evidence":"Independent approved labels, sufficient classes and a separately approved validation/evaluation protocol required"},
        {"decision":"Phase-6 repair authorization and final claims","status":"HUMAN_DECISION_PENDING","evidence":"No repair implemented; future permitted edits, budgets, provenance and reevaluation must be justified"}]
    return envelope("m7-exploratory-report-v1",{"study_fingerprint":manifest["fingerprint"],
        "phase4_parent":manifest["phase4_parent"],"implementation_revision":manifest["implementation_revision"],
        "construction_content_fingerprint":manifest["construction_content_fingerprint"],"plan":plan,
        "replay_identical":stable,"constructed_datasets":len(rows),"all_audits":"PASS",
        "total_selected_occurrences_across_datasets":sum(r["selected_n"] for r in rows),
        "shortfall_cases":sum(r["shortfall"]>0 for r in rows),"results":rows,"primary":primary,
        "stability":stability,"sensitivities":sensitivities,"cases":cases,"decision_ledger":decisions,
        "runtime_seconds":manifest["runtime_seconds"],"per_dataset_runtime_seconds":{r["name"]:r["runtime_seconds"] for r in manifest["runs"]},
        "matplotlib_version":matplotlib.__version__,"human_validity":"PENDING","real_test_used":False})


def render(study: Path, output: Path, replay: Path | None = None) -> dict[str,Any]:
    v=report_data(study,replay); output=create_run_dir(output.parent,output.name)
    write_json(output/"artifact.json",v)
    for name,rows in (("results",v["results"]),("selection-stability",v["stability"]),("policy-sensitivity",v["sensitivities"]),("cases",v["cases"]),("decision-ledger",v["decision_ledger"])):
        write_text(output/f"{name}.csv",csv_text(rows))
    datasets=sorted(v["plan"]["budgets"])
    middle=[r for r in v["primary"] if r["budget"]==v["plan"]["budgets"][r["dataset"]][1]]
    controls=[r for r in v["results"] if r["control_intersection"] is not None]
    lines=["# Phase-5 M7 exploratory dataset construction", "",
        "PHASE-5 ENGINEERING AND EXPLORATORY DATASET CONSTRUCTION COMPLETE \u2014 SCIENTIFIC REVIEW PENDING", "",
        "Every dataset is provisional, not human-validated ground truth. Better geometric coverage is not proof of record validity, classifier utility, novelty or superiority. Phases 2, 3, 4 and 5 remain scientifically unfrozen.", "",
        f"Exact Phase-4 parent `{v['phase4_parent']}`. Construction implementation `{v['implementation_revision']}`.",
        f"Study `{v['study_fingerprint']}`. Deterministic construction content `{v['construction_content_fingerprint']}`.","",
        "## Architecture and exact methodology","",
        "Frozen source occurrences and Phase-4 eligibility feed complete labeled-record checks, reused M2 TRAIN-only mixed distance, four budgeted selectors, immutable original-payload datasets and full deterministic recipe audit. No validator refit, policy rewrite, TEST-driven selection, provider call, human-label fitting or repair occurs.","",
        "See docs/phase5-m7-coverage-methods.md at repository root for every formula and reproduction command. Distance is mean clipped TRAIN-range-scaled numeric absolute difference plus nominal mismatch; class is excluded. With r=.05, a TRAIN reference is covered when its minimum selected distance is <=r. Distinct (feature,literal-class) regions prevent duplicate TRAIN rows multiplying selection objectives. Row, distinct-feature and class-balanced coverage are reported separately.","",
        "Source-order takes the earliest eligible records. Farthest-first maximizes minimum selected distance after a source-order seed. Coverage-greedy maximizes uniform uncovered-region gain. Quality-coverage retains provisional eligibility, prohibits repeated feature payloads, applies an availability-capped minority quota first, and ranks candidates by class-balanced coverage gain, fewer near neighbors, larger separation, lower uncalibrated concern and stable source order. This is a constrained geometric objective, not calibrated quality optimization.","",
        "## Pools and matched budgets","",
        table(["Dataset","Provisional pool","Distinct feature payloads","Matched budgets"],[[d,v["plan"]["pool_availability"][d]["eligible"],v["plan"]["pool_availability"][d]["unique_features"],str(v["plan"]["budgets"][d])] for d in datasets]),"",
        "Budgets were fixed as floor(.25/.50/.75 times each primary pool's distinct-feature count), before coverage outcomes. The primary pool contains 451 provisional records. Structural rejects, reviews and abstentions remain deferred. Class and every required feature must exist in the original payload; requested_class never repairs a missing class. All four primary strategies use identical per-dataset budgets.","",
        "## Main results at the middle matched budget","",
        table(["Dataset","Strategy","N","TRAIN rows covered","Distinct TRAIN features covered","Exact duplicates","Near duplicates","Same-label minority coverage"],[[r["dataset"],r["strategy"],r["selected_n"],r["train_row_coverage"],r["unique_train_feature_coverage"],r["exact_duplicate_rate"],r["near_duplicate_rate"],r["same_class_minority_coverage"]] for r in middle]),"",
        "Rates are fractions. Near-duplicate rate is the share with another selected feature vector within .01 and includes exact feature duplicates. Exact duplicate rate is 1 - unique canonical full payloads / selected count. Minority means least frequent literal TRAIN token, without assuming unknown original target mappings. Same-label minority coverage uses only selected records with that literal class. Complete 51-case metrics are in results.csv and each source dataset artifact, including distance quantiles, pairwise separation, density, concentration, quotas and class breakdowns.","",
        "![Coverage curves](budget-coverage.png)","","![Duplicate rates](budget-duplicates.png)","",
        "Geometric objectives show trade-offs rather than a guaranteed best method. Uniform and class-balanced region objectives differ. Source duplicates can inflate row coverage without increasing unique-region coverage. Quota constraints can change the order and coverage path. No strategy is selected using TEST or unapproved agent labels.","",
        "![Diversity and coverage](diversity-coverage.png)","","![Minority coverage](minority-coverage.png)","",
        "## Recorded-control intersection and frozen-policy sensitivities","",
        table(["Dataset","B2 intersection budget","N","TRAIN row coverage","Distinct feature coverage","Exact duplicates"],[[r["dataset"],r["budget"],r["selected_n"],r["train_row_coverage"],r["unique_train_feature_coverage"],r["exact_duplicate_rate"]] for r in controls]),"",
        "The control is B2-accepted INTERSECT primary provisional eligibility, not raw B2 acceptance. It retains different historical criteria and uses matched budgets. B1/B3 intersections are identical to the main pool on these candidates and need no duplicate experiment. Original B1/B2/B3 records remain unchanged.","",
        table(["Dataset","Frozen policy","Budget","Eligible","Selected","Jaccard with main D","Distinct feature coverage","Shortfall"],[[r["dataset"],r["policy"],r["budget"],r["eligible_n"],r["selected_n"],r["selected_jaccard_with_primary"],r["unique_train_feature_coverage"],r["shortfall"]] for r in v["sensitivities"]]),"",
        "Sensitivities use existing q=.80/.95 decisions; no admission or threshold is overwritten or optimized. Selected-set Jaccard is a stability measure, not correctness. Cross-budget exact-prefix, smaller-set retention and Jaccard are in selection-stability.csv. D can change prefixes as its quota changes with budget.","",
        "## Dataset audits and reproducibility","",
        f"Constructed datasets: {v['constructed_datasets']} (36 primary, 9 control-intersection, 6 policy sensitivity). Full replay identical: {v['replay_identical']}. All source-bound audits PASS. Budget shortfall cases: {v['shortfall_cases']}. Measured study runtime: {v['runtime_seconds']:.3f} seconds, including source preparation, geometry, all constructions, sealed writes and dataset audit replay; excludes report rendering. Per-case runtimes are in artifact.json.","",
        "Every bundle preserves ordered original payloads and labels in dataset.csv/JSON, exact source/specification/Phase-4/TRAIN/pool/configuration identities, objective traces, full-source defer ledger, budget/quota accounting and human-review status. The audit reloads source-bound inputs and rebuilds the exact recipe; contradictions fail rather than repair. Audit every constructed dataset with `python -m rcqasyn phase5 audit BUNDLE --source-root SOURCE`. Full commands are in the methods document. Fresh versioned paths reproduce datasets without changing history.","",
        "The total selection count across many experiment datasets counts repeated participation; it must not be interpreted as new generated records. Canonical dataset identities are deterministic; manifest runtimes can differ. Study resume validates existing outputs. Source-code content fingerprints normalize newlines for portable checkout identity.","",
        "## Explainable cases and limitations","",
        "cases.csv records first, largest-marginal-gain and final picks at the middle budgets, deduplicated by selection rank, with original payload, source ordinal, marginal gain, cumulative objective, quota phase and reason. These are deterministic illustrations, not cherry-picked validity demonstrations.","",
        "All 120 annotation proposals remain AGENT/PENDING_HUMAN_APPROVAL (0 VALID, 27 INVALID, 93 INDETERMINATE). No real calibration, human-ground-truth performance or utility evaluation is claimed. Unresolved target mappings, physical meanings/units and cross-field rules remain unknown. Selected-cohort bias and historical TRAIN/TEST exact-value overlap remain limitations; TEST values were never consulted by selection. Dense-region concentration and literal-class uncertainty limit interpretation of coverage.","",
        "The single decision-ledger.csv records personal label review, domain semantics, radius/quota adequacy, scientific acceptance, future calibration/utility protocol and Phase-6 authorization. Phase 6 is not started. A future bounded-repair study needs an approved edit space, budgets, unchanged originals, edit provenance, re-evaluation and independent scientific assessment.","",
        "## Engineering verification","",
        "Focused tests, one final full pytest suite, Ruff, Pyright, historical comparisons and the consolidated implementation-owner read-only review are preserved under ../final-verification-v1. This engineering evidence does not constitute scientific acceptance or an independent human validity judgment.",""]
    text="\n".join(lines).replace(chr(92)+"u2014",chr(0x2014))
    write_text(output/"report.md",text)
    summary=["# Academic-draft methods and results", "",
        "We constructed provisional synthetic datasets from frozen M4/M5 admissions using four deterministic strategies: source order, farthest-first diversity, marginal TRAIN-region coverage and eligibility/uniqueness/quota-constrained class-balanced coverage. Geometry reused the TRAIN-fitted mixed-type distance; numerical spans and source identities were checked without refitting validators. Fixed per-dataset budgets matched sample counts across strategies. Coverage, redundancy, literal minority support and concentration were reported separately from validity and utility.","",
        f"The bounded study produced {v['constructed_datasets']} provisional datasets across three existing datasets, with all source-bound audits passing and exact deterministic replay. Radius .05 and near-duplicate tolerance .01 were declared before outcomes. No human labels or REAL TEST values informed construction. Main middle-budget results follow; these geometric comparisons do not establish classifier performance, genuine record validity, novelty or superiority.","",
        table(["Dataset","Strategy","Budget","Distinct TRAIN feature coverage","Exact duplicate rate"],[[r["dataset"],r["strategy"],r["budget"],r["unique_train_feature_coverage"],r["exact_duplicate_rate"]] for r in middle]),"",
        "Human-label review and scientific acceptance remain pending. Unknown semantics, selected-cohort bias, candidate-pool limitations and historical exact-value TRAIN/TEST overlap constrain interpretation. Phase-6 repair is outside the current study.",""]
    write_text(output/"manuscript-summary.md","\n".join(summary))
    for metric,name,title,ylabel in [("unique_train_feature_coverage","budget-coverage","Budget-matched coverage of distinct TRAIN feature points","Distinct TRAIN feature coverage"),("exact_duplicate_rate","budget-duplicates","Budget-matched exact payload redundancy","Exact duplicate rate"),("same_class_minority_coverage","minority-coverage","Coverage of literal TRAIN minority by same-label selected records","Same-label minority TRAIN coverage")]:
        fig,axes=plt.subplots(1,3,figsize=(14,4.3),sharey=True)
        for ax,d in zip(axes,datasets,strict=True):
            for strategy in STRATEGIES:
                group=sorted([r for r in v["primary"] if r["dataset"]==d and r["strategy"]==strategy],key=lambda r:r["budget"])
                ax.plot([r["budget"] for r in group],[r[metric] for r in group],marker="o",label=strategy,color=COLORS[strategy])
            ax.set_title(d); ax.set_xlabel("Matched selection budget"); ax.set_ylim(-.03,1.03); ax.set_xticks(v["plan"]["budgets"][d])
        axes[0].set_ylabel(ylabel); axes[2].legend(fontsize=8,loc="best")
        fig.suptitle(title); fig.tight_layout(); save(fig,output,name)
    fig,axes=plt.subplots(1,3,figsize=(14,4.3))
    for ax,d in zip(axes,datasets,strict=True):
        for row in (r for r in middle if r["dataset"]==d):
            ax.scatter(row["pairwise_mean"],row["unique_train_feature_coverage"],color=COLORS[row["strategy"]],label=row["strategy"],s=75)
        ax.set_title(f"{d}, budget={v['plan']['budgets'][d][1]}")
        ax.set_xlabel("Mean pairwise mixed distance"); ax.set_ylabel("Distinct TRAIN feature coverage"); ax.set_ylim(-.03,1.03)
    axes[2].legend(fontsize=8,loc="best"); fig.suptitle("Diversity / geometric coverage trade-off at the same sample count")
    fig.tight_layout(); save(fig,output,"diversity-coverage")
    seal_bundle(output); return v


if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--study",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True); parser.add_argument("--replay",type=Path)
    args=parser.parse_args(); result=render(args.study,args.output,args.replay)
    print(json.dumps({"report_fingerprint":result["fingerprint"],"datasets":result["constructed_datasets"]}))
