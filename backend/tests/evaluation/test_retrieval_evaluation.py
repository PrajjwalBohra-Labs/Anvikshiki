import copy
from pathlib import Path

import pytest

from backend.evaluation.retrieval_evaluation import (
    EvaluationError,
    calculate_metrics,
    load_dataset,
    validate_dataset,
)

DATASET_PATH = Path("backend/evaluation/datasets/retrieval_golden_set_v1.json")


def test_evaluation_dataset_loads_with_explicit_ground_truth():
    dataset, path = load_dataset(str(DATASET_PATH))

    assert path.name == DATASET_PATH.name
    assert dataset["dataset_id"] == "anvikshiki-philosophy-retrieval-golden-v1"
    assert len(dataset["corpus"]) == 6
    assert len(dataset["queries"]) == 7
    assert all(query["expected"] for query in dataset["queries"])


def test_dataset_rejects_duplicate_query_and_missing_ground_truth():
    dataset, _ = load_dataset(str(DATASET_PATH))
    duplicate = copy.deepcopy(dataset)
    duplicate["queries"].append(copy.deepcopy(duplicate["queries"][0]))
    with pytest.raises(EvaluationError, match="Duplicate query_id"):
        validate_dataset(duplicate)

    invalid_reference = copy.deepcopy(dataset)
    invalid_reference["queries"][0]["expected"][0]["passage_key"] = "missing"
    with pytest.raises(EvaluationError, match="references missing passage"):
        validate_dataset(invalid_reference)


def test_dataset_rejects_duplicate_ground_truth_and_invalid_relevance():
    dataset, _ = load_dataset(str(DATASET_PATH))
    duplicate = copy.deepcopy(dataset)
    duplicate["queries"][0]["acceptable_alternatives"] = copy.deepcopy(
        duplicate["queries"][0]["expected"]
    )
    with pytest.raises(EvaluationError, match="duplicates ground truth"):
        validate_dataset(duplicate)

    invalid_relevance = copy.deepcopy(dataset)
    invalid_relevance["queries"][0]["expected"][0]["relevance"] = 4
    with pytest.raises(EvaluationError, match="relevance"):
        validate_dataset(invalid_relevance)


def test_metrics_use_graded_explicit_labels_and_empty_results():
    labels = {"direct": 3, "alternative": 1}
    metrics = calculate_metrics(["noise", "alternative", "direct"], labels, k=3)

    assert metrics["recall@3"] == 1.0
    assert metrics["precision@3"] == pytest.approx(2 / 3)
    assert metrics["mrr"] == pytest.approx(1 / 2)
    assert metrics["ndcg@3"] < 1.0

    empty = calculate_metrics([], labels, k=3)
    assert empty["recall@3"] == 0.0
    assert empty["precision@3"] == 0.0
    assert empty["mrr"] == 0.0
    assert empty["ndcg@3"] == 0.0


def test_metrics_are_repeatable_and_order_sensitive():
    labels = {"a": 3}
    first = calculate_metrics(["a", "b"], labels, k=2)
    second = calculate_metrics(["a", "b"], labels, k=2)
    changed = calculate_metrics(["b", "a"], labels, k=2)

    assert first == second
    assert first["mrr"] > changed["mrr"]
