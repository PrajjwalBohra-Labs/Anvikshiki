"""Focused contract tests for the deterministic evaluation primitives."""

import copy
import json
from pathlib import Path

import pytest

from backend.evaluation.retrieval_evaluation import (
    EvaluationError,
    calculate_metrics,
    canonical_evaluation_result,
    compare_baseline,
    deterministic_signature,
    load_dataset,
    validate_dataset,
)

DATASET = Path("backend/evaluation/datasets/retrieval_golden_set_v1.json")


def dataset_copy() -> dict:
    dataset, _ = load_dataset(str(DATASET))
    return copy.deepcopy(dataset)


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("../outside.txt", "escapes corpus_root"),
        ("", "non-empty string"),
    ],
)
def test_dataset_rejects_unsafe_or_invalid_corpus_filename(path, message):
    dataset = dataset_copy()
    dataset["corpus"][0]["filename"] = path
    with pytest.raises(EvaluationError, match=message):
        validate_dataset(dataset, DATASET.resolve())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("dataset_id", ""),
        ("dataset_version", None),
        ("corpus", []),
        ("queries", []),
    ],
)
def test_dataset_rejects_missing_or_empty_required_sections(field, value):
    dataset = dataset_copy()
    dataset[field] = value
    with pytest.raises(EvaluationError):
        validate_dataset(dataset)


def test_dataset_rejects_duplicate_keys_and_malformed_fields():
    dataset = dataset_copy()
    duplicate = copy.deepcopy(dataset["corpus"][0])
    dataset["corpus"].append(duplicate)
    with pytest.raises(EvaluationError, match="Duplicate source_key"):
        validate_dataset(dataset)

    dataset = dataset_copy()
    dataset["queries"][0]["query"] = None
    with pytest.raises(EvaluationError, match="non-empty string"):
        validate_dataset(dataset)

    dataset = dataset_copy()
    dataset["corpus"][0]["passages"][0]["page_number"] = 0
    with pytest.raises(EvaluationError, match="Invalid page_number"):
        validate_dataset(dataset)

    dataset = dataset_copy()
    dataset["queries"][0]["expected"][0]["relevance"] = 4
    with pytest.raises(EvaluationError, match="relevance"):
        validate_dataset(dataset)


def test_metrics_are_correct_at_cutoffs_and_for_empty_results():
    labels = {"high": 3, "low": 1}
    perfect = calculate_metrics(["high", "low"], labels, 3)
    assert perfect == {
        "recall@3": 1.0,
        "precision@3": pytest.approx(2 / 3),
        "mrr": 1.0,
        "ndcg@3": pytest.approx(1.0),
    }
    assert calculate_metrics([], labels, 3) == {
        "recall@3": 0.0,
        "precision@3": 0.0,
        "mrr": 0.0,
        "ndcg@3": 0.0,
    }
    assert calculate_metrics(["noise", "high"], labels, 1)["mrr"] == 0.0
    assert calculate_metrics(["high"], {}, 1)["recall@1"] == 0.0
    assert calculate_metrics(["high"], labels, 1)["ndcg@1"] > calculate_metrics(
        ["low", "high"], labels, 2
    )["ndcg@2"]


def test_canonical_result_and_signature_ignore_non_deterministic_report_fields():
    report = {
        "dataset": {"dataset_id": "d"},
        "configuration": {"top_k": 3},
        "corpus_identity": {
            "doc": {
                "source_key": "source",
                "checksum_sha256": "checksum",
                "passage_pages": {"p": 1},
                "document_id": "db-id",
            }
        },
        "methods": {
            method: {
                "metrics": {"recall@3": 1.0},
                "queries": [
                    {"query_id": "q", "retrieved": [{"passage_key": "source/doc/p"}], "metrics": {"recall@3": 1.0}}
                ],
            }
            for method in ("lexical", "semantic", "hybrid", "reranked")
        },
        "generated_at": "different",
    }
    first = deterministic_signature(report)
    report["generated_at"] = "another-value"
    assert canonical_evaluation_result(report) == canonical_evaluation_result(report)
    assert deterministic_signature(report) == first
    assert len(first) == 64


def test_baseline_comparison_reports_all_delta_directions(tmp_path):
    current = {
        "methods": {
            "lexical": {"metrics": {"recall@3": 0.8, "mrr": 0.5, "ndcg@3": 0.2}},
        }
    }
    baseline = {
        "dataset": {"dataset_id": "baseline"},
        "methods": {
            "lexical": {"metrics": {"recall@3": 0.7, "mrr": 0.5, "ndcg@3": 0.3}},
        },
    }
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(baseline), encoding="utf-8")
    comparison = compare_baseline(current, str(path))
    assert comparison["methods"]["lexical"] == {
        "mrr": 0.0,
        "ndcg@3": pytest.approx(-0.1),
        "recall@3": pytest.approx(0.1),
    }
    assert comparison["regressions"] == [
        {"method": "lexical", "metric": "ndcg@3", "delta": pytest.approx(-0.1)}
    ]
