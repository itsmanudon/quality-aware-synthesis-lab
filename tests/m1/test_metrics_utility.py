from pathlib import Path

import pandas as pd
import pytest

from rcqasyn.config.experiment import MetricsConfig
from rcqasyn.datasets import DatasetRegistry, load_dataset
from rcqasyn.metrics import intrinsic_metrics, utility_metrics


def test_intrinsic_metrics_known_fixture_reports_fidelity_diversity_and_empty_status() -> None:
    registry = DatasetRegistry(project_root=Path.cwd())
    dataset = load_dataset(registry.get("dev-small"), registry)
    train = dataset.frame.copy()
    synthetic = train.copy()
    result = intrinsic_metrics(train, synthetic, dataset.spec)
    assert result["numeric"]["age"]["ks"] == 0.0
    assert result["numeric"]["age"]["wasserstein"] == 0.0
    assert result["categorical"]["color"]["tvd"] == 0.0
    assert result["class_conditional"]["status"] == "ok"
    assert result["diversity"]["exact_duplicate_count"] == 0
    duplicated = pd.concat([synthetic, synthetic.iloc[[0]]], ignore_index=True)
    duplicated_result = intrinsic_metrics(train, duplicated, dataset.spec)
    no_class = duplicated_result["class_conditional"]["classes"]["no"]
    assert no_class["real_count"] == 12
    assert no_class["synthetic_count"] == 13
    assert no_class["exact_duplicate_count"] == 1
    assert no_class["exact_duplicate_rate"] == 1 / 13
    empty = intrinsic_metrics(train, synthetic.iloc[0:0], dataset.spec)
    assert empty["numeric"]["age"]["status"] == "empty"
    assert empty["numeric"]["age"]["ks"] is None
    assert empty["class_conditional"]["status"] == "empty"
    assert empty["class_conditional"]["classes"]["no"]["status"] == "empty"
    assert empty["class_conditional"]["classes"]["no"]["synthetic_count"] == 0
    assert empty["class_conditional"]["classes"]["no"]["exact_duplicate_rate"] is None


def test_utility_reports_trtr_tstr_metrics_with_mixed_columns_and_no_test_fit() -> None:
    registry = DatasetRegistry(project_root=Path.cwd())
    dataset = load_dataset(registry.get("dev-small"), registry)
    train = dataset.frame.iloc[:12].copy()
    test = dataset.frame.iloc[12:].copy()
    synthetic = train.copy()
    # This category exists only in REAL TEST; OneHotEncoder(handle_unknown=ignore)
    # must accept it without learning test-derived categories/statistics.
    test.loc[test.index[0], "color"] = "TEST_ONLY_CATEGORY"
    result = utility_metrics(train, test, synthetic, dataset.spec, seed=7)
    for split in ("TRTR", "TSTR"):
        for model in ("logistic_regression", "random_forest"):
            metrics = result[split][model]
            assert {"f1", "average_precision", "pr_auc", "mcc", "balanced_accuracy", "auroc"} <= set(metrics)
            assert metrics["status"] in {"ok", "undefined", "empty"}


def test_utility_classifier_selection_applies_to_both_trtr_and_tstr() -> None:
    registry = DatasetRegistry(project_root=Path.cwd())
    dataset = load_dataset(registry.get("dev-small"), registry)
    train = dataset.frame.iloc[:12].copy()
    test = dataset.frame.iloc[12:].copy()
    selected = utility_metrics(train, test, train.copy(), dataset.spec, classifiers=("logistic_regression",))
    assert set(selected["TRTR"]) == {"logistic_regression"}
    assert set(selected["TSTR"]) == {"logistic_regression"}
    with pytest.raises(ValueError, match="unsupported classifiers"):
        utility_metrics(train, test, train.copy(), dataset.spec, classifiers=("unknown",))
    with pytest.raises(ValueError, match="unsupported classifiers"):
        MetricsConfig.model_validate({"classifiers": ["unknown"]})
