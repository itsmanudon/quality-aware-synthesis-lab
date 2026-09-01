# M1.6 Human Audit Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build network-free CLI and library infrastructure that validates external human annotations and, only when complete, generates the traceable M1.6 human-audit report bundle.

**Architecture:** Add one focused analysis module containing immutable CSV loading, taxonomy parsing, metric helpers, B2 evidence classification, optional agreement, and deterministic report writing. Expose it through a Typer `human-review` group, while retaining the existing M1 analysis API for compatibility. All calculations consume explicit human labels and refuse incomplete or unknown annotations.

**Tech Stack:** Python 3.12, standard-library CSV/JSON/hashlib/statistics, NumPy, SciPy, scikit-learn, Typer, pytest

**Spec:** `docs/superpowers/specs/2026-08-30-m1-6-human-audit-design.md`

## Global Constraints

- Never modify `artifacts/reports/p1/p1_human_review.csv` or infer a human label.
- Do not regenerate P1 or call Ollama/network providers.
- Treat `DUPLICATE` as dataset-level redundancy, not record invalidity.
- Treat human-invalid as the positive class for B2/B3 metrics.
- Do not tune thresholds, calibrate B3, or implement any M2 validator.
- Preserve unknown taxonomy labels in status/error output.
- Emit no Brier score because B3 score probability semantics are not established.

---

### Task 1: Annotation parsing and completeness status

**Files:**
- Create: `src/rcqasyn/experiments/human_audit.py`
- Modify: `src/rcqasyn/experiments/__init__.py`
- Create: `tests/m1/test_human_audit.py`

**Interfaces:**
- Produces: `parse_failure_labels(value: str) -> tuple[str, ...]`
- Produces: `load_review(path: Path) -> list[dict[str, str]]`
- Produces: `review_status(path: Path) -> dict[str, Any]`
- Produces: `HumanAuditError(ValueError)`

- [ ] **Step 1: Write failing parsing and blank-status tests**

```python
def test_parse_failure_labels_is_multilabel_and_preserves_unknown() -> None:
    assert parse_failure_labels("DUPLICATE; STATISTICAL_IMPLAUSIBILITY") == (
        "DUPLICATE", "STATISTICAL_IMPLAUSIBILITY",
    )
    assert parse_failure_labels("SCHEMA|ALIEN_LABEL,SCHEMA") == ("SCHEMA", "ALIEN_LABEL")


def test_review_status_never_infers_blank_labels(review_csv: Path) -> None:
    result = review_status(review_csv)
    assert result["rows"] == 3
    assert result["labelled"] == 0
    assert result["unlabelled"] == 3
    assert result["valid"] == result["invalid"] == 0
    assert result["analysis_ready"] is False
```

- [ ] **Step 2: Run tests and verify missing imports fail**

Run: `python -m pytest tests/m1/test_human_audit.py -q`
Expected: collection fails because `rcqasyn.experiments.human_audit` does not exist.

- [ ] **Step 3: Implement deterministic parsing and status validation**

```python
def parse_failure_labels(value: str) -> tuple[str, ...]:
    labels: list[str] = []
    for token in re.split(r"[;|,]", value):
        label = token.strip().upper()
        if label and label not in labels:
            labels.append(label)
    return tuple(labels)


def review_status(path: Path) -> dict[str, Any]:
    rows = load_review(path)
    parsed = [_explicit_bool(row["human_valid"]) for row in rows]
    labelled = sum(value is not None for value in parsed)
    unknown = sorted({
        label
        for row in rows
        for label in parse_failure_labels(row["human_failure_type"])
        if label not in HUMAN_FAILURE_TAXONOMY
    })
    return {
        "rows": len(rows),
        "labelled": labelled,
        "unlabelled": len(rows) - labelled,
        "valid": sum(value is True for value in parsed),
        "invalid": sum(value is False for value in parsed),
        "unknown_taxonomy_labels": unknown,
        "analysis_ready": labelled == len(rows) and not unknown,
    }
```

The implementation must validate required identity, machine-decision, diagnostic,
provider, and human columns; count dataset/class/taxonomy values; verify unique row
identities and canonical hashes; and report invalid booleans, unknown labels, blank
diagnostics, and `analysis_ready`.

- [ ] **Step 4: Run the focused tests and verify green**

Run: `python -m pytest tests/m1/test_human_audit.py -q`
Expected: parsing and status tests pass.

- [ ] **Step 5: Export the new public API and run existing analysis tests**

Add the new names to `src/rcqasyn/experiments/__init__.py`, then run:

`python -m pytest tests/m1/test_m1_analysis.py tests/m1/test_human_audit.py -q`

Expected: both the compatibility suite and new tests pass.

### Task 2: Metrics, score distributions, distances, and agreement

**Files:**
- Modify: `src/rcqasyn/experiments/human_audit.py`
- Modify: `tests/m1/test_human_audit.py`

**Interfaces:**
- Produces: `confusion_metrics(human_valid: Sequence[bool], predicted_accept: Sequence[bool]) -> dict[str, Any]`
- Produces: `score_distribution(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]`
- Produces: `support_distance_analysis(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]`
- Produces: `annotator_agreement(annotation_sets: Mapping[str, Sequence[Mapping[str, str]]]) -> dict[str, Any]`

- [ ] **Step 1: Write failing B2/B3 confusion tests**

```python
def test_confusion_metrics_detects_human_invalid() -> None:
    result = confusion_metrics(
        human_valid=[False, False, True, True],
        predicted_accept=[False, True, False, True],
    )
    assert {key: result[key] for key in ("tp", "fp", "tn", "fn")} == {
        "tp": 1, "fp": 1, "tn": 1, "fn": 1,
    }
    assert result["precision"] == result["recall"] == result["f1"] == 0.5
    assert result["specificity"] == result["balanced_accuracy"] == 0.5
    assert result["false_accept_rate"] == result["false_reject_rate"] == 0.5
```

- [ ] **Step 2: Run the confusion test and verify red**

Run: `python -m pytest tests/m1/test_human_audit.py -q -k confusion`
Expected: fail because `confusion_metrics` is missing.

- [ ] **Step 3: Implement confusion calculations with null-safe division**

```python
def confusion_metrics(human_valid: Sequence[bool], predicted_accept: Sequence[bool]) -> dict[str, Any]:
    pairs = [(not valid, not accepted) for valid, accepted in zip(human_valid, predicted_accept, strict=True)]
    tp = sum(actual and predicted for actual, predicted in pairs)
    fp = sum(not actual and predicted for actual, predicted in pairs)
    tn = sum(not actual and not predicted for actual, predicted in pairs)
    fn = sum(actual and not predicted for actual, predicted in pairs)
    ratio = lambda numerator, denominator: numerator / denominator if denominator else None
    precision = ratio(tp, tp + fp)
    recall = ratio(tp, tp + fn)
    specificity = ratio(tn, tn + fp)
    return {
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": precision, "recall": recall,
        "f1": ratio(2 * tp, 2 * tp + fp + fn),
        "specificity": specificity,
        "balanced_accuracy": (
            (recall + specificity) / 2
            if recall is not None and specificity is not None else None
        ),
        "false_accept_rate": ratio(fn, tp + fn),
        "false_reject_rate": ratio(fp, tn + fp),
    }
```

- [ ] **Step 4: Write failing score, distance, and agreement tests**

Tests assert exact quantiles for a small score set, fixed `[0, 1]` histogram bins,
median/IQR/p10/p90 distance summaries, rank-biserial direction, optional AUC behavior,
partial-overlap raw agreement, and Cohen's kappa. A constant-label agreement fixture
must assert an explicit `not_computable` reason rather than NaN.

- [ ] **Step 5: Run the new tests and verify red**

Run: `python -m pytest tests/m1/test_human_audit.py -q -k "score or support or agreement"`
Expected: fail because the analysis helpers are missing.

- [ ] **Step 6: Implement the minimal statistical helpers**

Use `numpy.quantile`, `scipy.stats.mannwhitneyu`,
`sklearn.metrics.roc_auc_score`, `average_precision_score`, and
`cohen_kappa_score`. Filter missing numeric values per field and retain group counts.
Use `1 - b3_score` only for invalidity AUC calculations. Do not calculate Brier score.

- [ ] **Step 7: Run all human-audit tests and verify green**

Run: `python -m pytest tests/m1/test_human_audit.py -q`
Expected: all Task 1 and Task 2 tests pass.

### Task 3: B2 evidence view and complete report bundle

**Files:**
- Modify: `src/rcqasyn/experiments/human_audit.py`
- Modify: `tests/m1/test_human_audit.py`

**Interfaces:**
- Produces: `classify_b2_evidence(evidence: Sequence[Mapping[str, Any]]) -> str`
- Produces: `analyze_review(path: Path, *, project_root: Path, output_dir: Path, annotators: Mapping[str, Path] | None = None, adjudicated: Path | None = None, overwrite: bool = False) -> dict[str, Any]`
- Produces: `write_human_audit_reports(result: Mapping[str, Any], output_dir: Path, *, overwrite: bool) -> tuple[Path, ...]`

- [ ] **Step 1: Write failing duplicate-only distinction tests**

```python
def test_duplicate_only_b2_reject_is_accept_in_record_validity_view() -> None:
    assert classify_b2_evidence([{"validator": "duplicate", "severity": "FAIL"}]) == "redundancy_only"
    assert classify_b2_evidence([
        {"validator": "duplicate", "severity": "FAIL"},
        {"validator": "schema", "severity": "FAIL"},
    ]) == "structural_domain"
```

Also test that missing or unrecognized failing evidence is `ambiguous`, never inferred
from human validity.

- [ ] **Step 2: Run duplicate classification tests and verify red**

Run: `python -m pytest tests/m1/test_human_audit.py -q -k duplicate_only`
Expected: fail because `classify_b2_evidence` is missing.

- [ ] **Step 3: Implement evidence classification and run-id joins**

Read only the evidence files named by CSV `run_id` values. Hash every joined source.
Recognize duplicate/redundancy checks separately from schema, missing-field,
categorical/domain, target, numeric/range/type, and other structural checks. Require
usable evidence for every rejected B2 row.

- [ ] **Step 4: Write failing complete/incomplete analysis tests**

Create temporary review and evidence fixtures. Assert incomplete primary annotations
raise `IncompleteAnnotationsError` before output creation. For a complete fixture,
assert all ten named output files exist, contain source hashes, preserve unknown-free
taxonomy counts, include all four B2/B3 decision cells, and do not contain
`brier_score`, `threshold_recommendation`, or inferred labels.

- [ ] **Step 5: Run bundle tests and verify red**

Run: `python -m pytest tests/m1/test_human_audit.py -q -k "analysis or bundle or incomplete"`
Expected: fail because orchestration/report writing is missing.

- [ ] **Step 6: Implement analysis assembly and deterministic report writers**

Assemble human summary, B2/B3 confusion, score splits/histograms, disagreement rows,
copying conditional counts, reference-copy counts, support-distance summaries,
taxonomy counts, dataset/class rates, optional agreement, and a concise Markdown
summary. Serialize JSON with sorted keys and stable indentation. Refuse changed-source
overwrites unless `overwrite=True`.

- [ ] **Step 7: Run all human-audit tests and verify green**

Run: `python -m pytest tests/m1/test_human_audit.py -q`
Expected: all tests pass without network access.

### Task 4: CLI commands and documentation

**Files:**
- Modify: `src/rcqasyn/cli/app.py`
- Modify: `tests/m1/test_human_audit.py`
- Modify: `docs/human-review.md`

**Interfaces:**
- Produces CLI: `rcqasyn human-review status <csv>`
- Produces CLI: `rcqasyn human-review analyze <csv> [--annotator ID=PATH]... [--adjudicated PATH] [--output-dir PATH] [--overwrite]`

- [ ] **Step 1: Write failing CLI tests**

Use `typer.testing.CliRunner`. Assert status prints rows/labelled/unlabelled,
valid/invalid, taxonomy, dataset, and class counts with exit code zero for blank
labels. Assert analyze exits nonzero with `incomplete` and creates no report directory
for blank labels. Assert malformed `ID=PATH` annotator options exit nonzero.

- [ ] **Step 2: Run CLI tests and verify red**

Run: `python -m pytest tests/m1/test_human_audit.py -q -k cli`
Expected: fail because the `human-review` group is not registered.

- [ ] **Step 3: Implement Typer commands and error presentation**

Register `human_review_app`, resolve relative inputs against the project root, print
deterministic status lines, map validation/incomplete errors to exit code 1, and pass
explicit annotator/adjudication paths to `analyze_review`.

- [ ] **Step 4: Update annotation documentation**

Document the exact human-valid definition, canonical semicolon delimiter, unknown
label behavior, status/analyze commands, optional annotators, explicit adjudication,
blank-label behavior, B2 redundancy-only record-validity view, and all output names.

- [ ] **Step 5: Run focused and regression tests**

Run: `python -m pytest tests/m1/test_human_audit.py tests/m1/test_m1_analysis.py tests/m1/test_m1_cli.py -q`
Expected: all focused and existing M1 tests pass.

### Task 5: P1 validation and quality gates

**Files:**
- Read only: `artifacts/reports/p1/p1_human_review.csv`
- Read only: `artifacts/reports/p1/*`

**Interfaces:**
- Consumes: completed CLI and analysis API
- Produces: verification evidence only; no human-audit evaluation bundle while labels are blank

- [ ] **Step 1: Run status against the real P1 review file**

Run: `python -m rcqasyn human-review status artifacts/reports/p1/p1_human_review.csv`
Expected: 120 rows, 0 labelled, 120 unlabelled, 0 valid, 0 invalid, three datasets,
majority/minority and B2/B3 coverage, unique hashes, blank human fields, and
`analysis_ready=false`.

- [ ] **Step 2: Confirm analyze refuses blank annotations**

Run: `python -m rcqasyn human-review analyze artifacts/reports/p1/p1_human_review.csv`
Expected: exit code 1 with an incomplete-annotation message and no fabricated M1.6
evaluation files.

- [ ] **Step 3: Run full verification gates**

Run in order:

```text
python -m pytest -q
ruff check .
pyright
python -m pytest --cov=rcqasyn
git diff --check
```

Expected: all project-owned checks pass. If the shell lacks the editable package or
dev tools, use the repository's declared Python 3.12 environment or report the exact
environmental blocker without claiming success.

- [ ] **Step 4: Inspect final scope**

Run: `git status --short` and `git diff --stat` plus a focused diff review. Confirm the
P1 review CSV hash is unchanged, no generated human-audit evaluation results exist,
and no M2 implementation entered the diff.
