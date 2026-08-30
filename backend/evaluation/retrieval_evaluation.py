"""Reproducible, provenance-aware evaluation of the existing retrieval stack.

The evaluator deliberately does not implement a second retriever. It loads the
versioned golden set through normal ingestion, then calls the production
lexical, semantic, hybrid, and reranked retrieval facades against PostgreSQL.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.application.use_cases.embedding_indexing import EmbeddingIndexService
from backend.app.application.use_cases.ingestion import DocumentIngestionService
from backend.app.core.config import settings
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.database.models import (
    DocumentModel,
    PassageModel,
    SourceModel,
)
from backend.app.infrastructure.database.session import AsyncSessionLocal
from backend.app.infrastructure.llm.embedding_client import LocalEmbeddingClient
from backend.app.infrastructure.rag.lexical_retriever import ScoredPassage
from backend.app.infrastructure.rag.reranker import AdvancedRetriever
from backend.app.infrastructure.rag.retriever import HybridRetriever
from backend.app.infrastructure.storage.local_storage import LocalStorageService


class EvaluationError(RuntimeError):
    """Raised when the dataset or evaluation corpus cannot be verified."""


METHODS = ("lexical", "semantic", "hybrid", "reranked")


def _canonical_reference(source_key: str, document_key: str, passage_key: str) -> str:
    return f"{source_key}/{document_key}/{passage_key}"


def _dataset_path(path: str | None) -> Path:
    return (
        Path(path).resolve()
        if path
        else Path(__file__).resolve().parent
        / "datasets"
        / "retrieval_golden_set_v1.json"
    )


def load_dataset(path: str | None = None) -> tuple[dict[str, Any], Path]:
    dataset_path = _dataset_path(path)
    if not dataset_path.is_file():
        raise EvaluationError(f"Evaluation dataset is missing: {dataset_path}")
    try:
        dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"Evaluation dataset could not be loaded: {exc}") from exc
    validate_dataset(dataset, dataset_path)
    return dataset, dataset_path


def _validate_reference(
    reference: dict[str, Any],
    corpus_refs: set[str],
    query_id: str,
    location: str,
) -> None:
    required = {"source_key", "document_key", "passage_key", "relevance"}
    missing = required - reference.keys()
    if missing:
        raise EvaluationError(f"{query_id} {location} is missing: {sorted(missing)}")
    relevance = reference["relevance"]
    if (
        not isinstance(relevance, int)
        or isinstance(relevance, bool)
        or not 1 <= relevance <= 3
    ):
        raise EvaluationError(
            f"{query_id} {location} relevance must be an integer from 1 to 3."
        )
    key = _canonical_reference(
        reference["source_key"], reference["document_key"], reference["passage_key"]
    )
    if key not in corpus_refs:
        raise EvaluationError(
            f"{query_id} {location} references missing passage {key}."
        )


def validate_dataset(dataset: dict[str, Any], dataset_path: Path | None = None) -> None:
    if not isinstance(dataset, dict) or not dataset.get("dataset_id"):
        raise EvaluationError("Evaluation dataset must have a dataset_id.")
    corpus = dataset.get("corpus")
    queries = dataset.get("queries")
    if not isinstance(corpus, list) or not corpus:
        raise EvaluationError("Evaluation dataset corpus is empty.")
    if not isinstance(queries, list) or not queries:
        raise EvaluationError("Evaluation dataset query set is empty.")

    corpus_refs: set[str] = set()
    source_keys: set[str] = set()
    document_keys: set[str] = set()
    root = (
        (dataset_path.parent / dataset.get("corpus_root", "corpus")).resolve()
        if dataset_path
        else None
    )
    for document in corpus:
        for field in (
            "source_key",
            "document_key",
            "filename",
            "title",
            "source_type",
            "passages",
        ):
            if field not in document:
                raise EvaluationError(f"Corpus document is missing {field}.")
        source_key = document["source_key"]
        document_key = document["document_key"]
        if source_key in source_keys:
            raise EvaluationError(f"Duplicate source_key: {source_key}")
        if document_key in document_keys:
            raise EvaluationError(f"Duplicate document_key: {document_key}")
        source_keys.add(source_key)
        document_keys.add(document_key)
        if document["source_type"] not in {item.value for item in SourceType}:
            raise EvaluationError(
                f"Unsupported source_type for {document_key}: {document['source_type']}"
            )
        if root is not None:
            fixture_path = (root / document["filename"]).resolve()
            try:
                fixture_path.relative_to(root)
            except ValueError as exc:
                raise EvaluationError(
                    f"Corpus filename escapes corpus_root: {document['filename']}"
                ) from exc
            if not fixture_path.is_file():
                raise EvaluationError(f"Corpus fixture is missing: {fixture_path}")
        passage_keys: set[str] = set()
        for passage in document["passages"]:
            for field in ("passage_key", "page_number", "content"):
                if field not in passage:
                    raise EvaluationError(f"{document_key} passage is missing {field}.")
            passage_key = passage["passage_key"]
            if passage_key in passage_keys:
                raise EvaluationError(
                    f"Duplicate passage_key in {document_key}: {passage_key}"
                )
            if (
                not isinstance(passage["page_number"], int)
                or passage["page_number"] < 1
            ):
                raise EvaluationError(
                    f"Invalid page_number in {document_key}/{passage_key}."
                )
            if (
                not isinstance(passage["content"], str)
                or not passage["content"].strip()
            ):
                raise EvaluationError(
                    f"Empty passage content in {document_key}/{passage_key}."
                )
            passage_keys.add(passage_key)
            corpus_refs.add(_canonical_reference(source_key, document_key, passage_key))

    query_ids: set[str] = set()
    for query in queries:
        for field in (
            "query_id",
            "query",
            "domain",
            "difficulty",
            "evaluation_type",
            "expected",
            "acceptable_alternatives",
        ):
            if field not in query:
                raise EvaluationError(f"Query is missing {field}.")
        query_id = query["query_id"]
        if query_id in query_ids:
            raise EvaluationError(f"Duplicate query_id: {query_id}")
        query_ids.add(query_id)
        if not query["query"].strip() or not query["expected"]:
            raise EvaluationError(
                f"Query {query_id} must have text and expected evidence."
            )
        seen: set[str] = set()
        for location, references in (
            ("expected", query["expected"]),
            ("acceptable_alternatives", query["acceptable_alternatives"]),
        ):
            if not isinstance(references, list):
                raise EvaluationError(f"Query {query_id} {location} must be a list.")
            for index, reference in enumerate(references):
                if not isinstance(reference, dict):
                    raise EvaluationError(
                        f"Query {query_id} {location}[{index}] must be an object."
                    )
                _validate_reference(
                    reference, corpus_refs, query_id, f"{location}[{index}]"
                )
                key = _canonical_reference(
                    reference["source_key"],
                    reference["document_key"],
                    reference["passage_key"],
                )
                if key in seen:
                    raise EvaluationError(
                        f"Query {query_id} duplicates ground truth passage {key}."
                    )
                seen.add(key)


async def _get_document(session, checksum: str) -> DocumentModel | None:
    result = await session.execute(
        select(DocumentModel)
        .where(DocumentModel.checksum_sha256 == checksum)
        .options(
            selectinload(DocumentModel.source),
            selectinload(DocumentModel.passages),
        )
    )
    return result.scalars().first()


async def ensure_corpus(
    dataset: dict[str, Any], dataset_path: Path
) -> dict[str, dict[str, Any]]:
    """Load/reuse the durable corpus and return stable-key to DB identity maps."""
    root = (dataset_path.parent / dataset.get("corpus_root", "corpus")).resolve()
    identity: dict[str, dict[str, Any]] = {}
    async with AsyncSessionLocal() as session:
        for corpus_document in dataset["corpus"]:
            fixture_path = (root / corpus_document["filename"]).resolve()
            content = fixture_path.read_bytes()
            checksum = hashlib.sha256(content).hexdigest()
            document = await _get_document(session, checksum)
            if document is None:
                source = SourceModel(
                    title=corpus_document["title"],
                    author=corpus_document.get("author"),
                    original_language=corpus_document.get("original_language"),
                    source_type=SourceType(corpus_document["source_type"]),
                    reference_url=corpus_document.get("reference_url"),
                )
                session.add(source)
                await session.flush()
                await DocumentIngestionService(
                    session, LocalStorageService()
                ).ingest_file(
                    source_id=source.id,
                    filename=corpus_document["filename"],
                    content=content,
                    mime_type=(
                        "application/pdf"
                        if fixture_path.suffix.lower() == ".pdf"
                        else "text/plain"
                    ),
                )
                document = await _get_document(session, checksum)
            if document is None or document.source is None:
                raise EvaluationError(
                    f"Corpus document could not be loaded: {corpus_document['document_key']}"
                )
            expected_passages = corpus_document["passages"]
            passages = sorted(
                document.passages,
                key=lambda item: (
                    item.passage_order is None,
                    item.passage_order,
                    item.id,
                ),
            )
            if len(passages) != len(expected_passages):
                raise EvaluationError(
                    f"Corpus document {corpus_document['document_key']} has {len(passages)} DB passages; "
                    f"expected {len(expected_passages)}."
                )
            passage_map: dict[str, PassageModel] = {}
            for expected, passage in zip(expected_passages, passages):
                if (
                    passage.content != expected["content"]
                    or passage.page_number != expected["page_number"]
                ):
                    raise EvaluationError(
                        f"Corpus content/page mismatch for {corpus_document['document_key']}/{expected['passage_key']}."
                    )
                passage_map[expected["passage_key"]] = passage
            if any(passage.embedding is None for passage in passages):
                await EmbeddingIndexService(session).index_passages(
                    passage_ids=[passage.id for passage in passages]
                )
            identity[corpus_document["document_key"]] = {
                "source_key": corpus_document["source_key"],
                "document_key": corpus_document["document_key"],
                "checksum_sha256": checksum,
                "source": document.source,
                "document": document,
                "passages": passage_map,
                "loaded": document.created_at,
            }
        await session.commit()
    return identity


def _labels(query: dict[str, Any]) -> dict[str, int]:
    references = [*query["expected"], *query["acceptable_alternatives"]]
    return {
        _canonical_reference(
            item["source_key"], item["document_key"], item["passage_key"]
        ): item["relevance"]
        for item in references
    }


def _dcg(relevances: Iterable[int]) -> float:
    return sum(
        relevance / math.log2(rank + 2) for rank, relevance in enumerate(relevances)
    )


def calculate_metrics(
    retrieved: list[str], labels: dict[str, int], k: int
) -> dict[str, float | None]:
    top = retrieved[:k]
    relevant = set(labels)
    hits = [item for item in top if item in relevant]
    recall = len(set(hits)) / len(relevant) if relevant else None
    precision = len(set(hits)) / k if k else None
    reciprocal_rank = next(
        (1.0 / (index + 1) for index, item in enumerate(retrieved) if item in relevant),
        0.0,
    )
    actual = [labels.get(item, 0) for item in top]
    ideal = sorted(labels.values(), reverse=True)[:k]
    ideal_dcg = _dcg(ideal)
    ndcg = _dcg(actual) / ideal_dcg if ideal_dcg else None
    return {
        f"recall@{k}": recall,
        f"precision@{k}": precision,
        "mrr": reciprocal_rank,
        f"ndcg@{k}": ndcg,
    }


def _mean(values: list[float | None]) -> float | None:
    usable = [value for value in values if value is not None]
    return sum(usable) / len(usable) if usable else None


def _scored_identity(item: ScoredPassage, key_by_id: dict[str, str]) -> dict[str, Any]:
    passage = item.passage
    document = passage.document
    source = document.source
    return {
        "passage_key": key_by_id[passage.id],
        "passage_id": passage.id,
        "document_id": passage.document_id,
        "document_version_id": passage.document_version_id,
        "page_id": passage.page_id,
        "page_number": passage.page_number,
        "source_id": source.id,
        "source_type": source.source_type.value
        if hasattr(source.source_type, "value")
        else str(source.source_type),
        "source_title": source.title,
        "citation": f"{source.title}, p. {passage.page_number}",
        "score": item.score,
        "retrieval_method": item.retrieval_method,
    }


async def _retrieve(
    method: str,
    query: str,
    retriever: HybridRetriever,
    advanced: AdvancedRetriever,
    top_k: int,
) -> list[ScoredPassage]:
    if method == "lexical":
        return (await retriever.lexical_retrieve(query=query, top_k=top_k)).results
    if method == "semantic":
        outcome = await retriever.semantic_retrieve(query=query, top_k=top_k)
        if outcome.status != "complete":
            raise EvaluationError(
                "; ".join(outcome.warnings) or "Semantic retrieval failed."
            )
        return outcome.results
    if method == "hybrid":
        outcome = await retriever.hybrid_retrieve_with_metadata(
            query=query, top_k=top_k
        )
        if outcome.status == "failed":
            raise EvaluationError(
                "; ".join(outcome.warnings) or "Hybrid retrieval failed."
            )
        return outcome.results
    outcome = await advanced.retrieve_and_rerank_with_metadata(query=query, top_k=top_k)
    if outcome.status != "complete":
        raise EvaluationError(
            "; ".join(outcome.warnings) or "Reranked retrieval failed."
        )
    return outcome.results


async def evaluate_dataset(
    dataset: dict[str, Any], dataset_path: Path, top_k: int = 5
) -> dict[str, Any]:
    if top_k < 1:
        raise EvaluationError("top_k must be positive.")
    if not settings.DATABASE_URL.startswith("postgresql"):
        raise EvaluationError(
            "Authoritative retrieval evaluation requires PostgreSQL/pgvector."
        )
    identity = await ensure_corpus(dataset, dataset_path)
    key_by_id = {
        passage.id: _canonical_reference(info["source_key"], document_key, passage_key)
        for document_key, info in identity.items()
        for passage_key, passage in info["passages"].items()
    }
    corpus_identity = {
        document_key: {
            "source_key": info["source_key"],
            "source_id": info["source"].id,
            "document_id": info["document"].id,
            "checksum_sha256": info["checksum_sha256"],
            "passage_ids": {
                passage_key: passage.id
                for passage_key, passage in info["passages"].items()
            },
            "passage_pages": {
                passage_key: passage.page_number
                for passage_key, passage in info["passages"].items()
            },
        }
        for document_key, info in identity.items()
    }
    report: dict[str, Any] = {
        "dataset": {
            "dataset_id": dataset["dataset_id"],
            "dataset_version": dataset["dataset_version"],
            "query_count": len(dataset["queries"]),
            "corpus_document_count": len(dataset["corpus"]),
            "corpus_passage_count": len(key_by_id),
        },
        "configuration": {
            "database_dialect": "postgresql",
            "top_k": top_k,
            "embedding_model": settings.EMBEDDING_MODEL,
            "embedding_provider": settings.EMBEDDING_PROVIDER,
            "embedding_dimensions": settings.EMBEDDING_DIMENSIONS,
            "reranker_enabled": settings.RERANKER_ENABLED,
            "reranker_model": settings.RERANKER_MODEL,
            "lexical_search_config": settings.LEXICAL_SEARCH_CONFIG,
            "hybrid_rrf_k": settings.HYBRID_RRF_K,
        },
        "corpus_identity": corpus_identity,
        "methods": {},
        "warnings": [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    for method in METHODS:
        query_reports = []
        failures = []
        metrics_by_query: list[dict[str, float | None]] = []
        candidate_k = max(top_k, len(key_by_id))
        async with AsyncSessionLocal() as session:
            embedding_client = LocalEmbeddingClient()
            retriever = HybridRetriever(session, embedding_client=embedding_client)
            advanced = AdvancedRetriever(session, embedding_client=embedding_client)
            for query in dataset["queries"]:
                labels = _labels(query)
                try:
                    scored = await _retrieve(
                        method, query["query"], retriever, advanced, candidate_k
                    )
                    excluded_out_of_corpus = sum(
                        1 for item in scored if item.passage.id not in key_by_id
                    )
                    scored = [item for item in scored if item.passage.id in key_by_id][
                        :top_k
                    ]
                    retrieved_records = [
                        _scored_identity(item, key_by_id) for item in scored
                    ]
                    retrieved_keys = [
                        record["passage_key"] for record in retrieved_records
                    ]
                    query_metrics = calculate_metrics(retrieved_keys, labels, top_k)
                    relevant_retrieved = [
                        record
                        for record in retrieved_records
                        if record["passage_key"] in labels
                    ]
                    citation_accuracy = (
                        sum(
                            1
                            for record in relevant_retrieved
                            if record["passage_id"]
                            == corpus_identity[record["passage_key"].split("/")[1]][
                                "passage_ids"
                            ][record["passage_key"].split("/")[2]]
                            and record["page_number"]
                            == corpus_identity[record["passage_key"].split("/")[1]][
                                "passage_pages"
                            ][record["passage_key"].split("/")[2]]
                            and record["document_id"]
                            and record["document_version_id"]
                            and record["source_id"]
                        )
                        / len(relevant_retrieved)
                        if relevant_retrieved
                        else None
                    )
                    query_metrics["citation_accuracy@k"] = citation_accuracy
                    query_metrics["provenance_resolution_rate@k"] = (
                        sum(
                            1
                            for record in retrieved_records
                            if record["document_id"]
                            and record["document_version_id"]
                            and record["page_number"]
                            and record["source_id"]
                        )
                        / len(retrieved_records)
                        if retrieved_records
                        else 0.0
                    )
                    query_metrics["primary_source_hit"] = float(
                        any(
                            record["source_type"] == SourceType.PRIMARY.value
                            and record["passage_key"] in labels
                            for record in retrieved_records
                        )
                    )
                    if query["evaluation_type"] == "contradiction":
                        query_metrics[f"contradiction_recall@{top_k}"] = query_metrics[
                            f"recall@{top_k}"
                        ]
                    query_reports.append(
                        {
                            "query_id": query["query_id"],
                            "query": query["query"],
                            "domain": query["domain"],
                            "difficulty": query["difficulty"],
                            "evaluation_type": query["evaluation_type"],
                            "ground_truth": labels,
                            "retrieved": retrieved_records,
                            "metrics": query_metrics,
                            "empty_result": not retrieved_records,
                            "excluded_out_of_corpus_count": excluded_out_of_corpus,
                        }
                    )
                    metrics_by_query.append(query_metrics)
                except Exception as exc:  # noqa: BLE001 - record per-query failures without fabricating metrics
                    failures.append(
                        {
                            "query_id": query["query_id"],
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
        if failures:
            raise EvaluationError(f"{method} evaluation failed: {failures}")
        metric_names = sorted({name for item in metrics_by_query for name in item})
        aggregate = {
            name: _mean([item.get(name) for item in metrics_by_query])
            for name in metric_names
        }
        primary = [
            item["metrics"]["primary_source_hit"]
            for item in query_reports
            if item["evaluation_type"] == "primary"
        ]
        contradiction = [
            item["metrics"].get("contradiction_recall@" + str(top_k))
            for item in query_reports
            if item["evaluation_type"] == "contradiction"
        ]
        aggregate["primary_source_hit_rate"] = _mean(primary)
        aggregate["contradiction_recall"] = _mean(contradiction)
        report["methods"][method] = {
            "status": "complete",
            "metrics": aggregate,
            "queries": query_reports,
            "empty_result_count": sum(
                1 for item in query_reports if item["empty_result"]
            ),
        }
    stable = {
        "dataset": report["dataset"],
        "configuration": report["configuration"],
        "corpus_identity": {
            document_key: {
                "source_key": identity["source_key"],
                "checksum_sha256": identity["checksum_sha256"],
                "passage_pages": identity["passage_pages"],
            }
            for document_key, identity in report["corpus_identity"].items()
        },
        "methods": {
            method: {
                "metrics": report["methods"][method]["metrics"],
                "queries": [
                    {
                        "query_id": item["query_id"],
                        "retrieved": [
                            record["passage_key"] for record in item["retrieved"]
                        ],
                        "metrics": item["metrics"],
                    }
                    for item in report["methods"][method]["queries"]
                ],
            }
            for method in METHODS
        },
    }
    report["deterministic_signature"] = hashlib.sha256(
        json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return report


def compare_baseline(
    report: dict[str, Any], baseline_path: str | None
) -> dict[str, Any] | None:
    if not baseline_path:
        return None
    path = Path(baseline_path)
    if not path.is_file():
        raise EvaluationError(f"Baseline report is missing: {path}")
    try:
        baseline = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"Baseline report could not be loaded: {exc}") from exc
    comparison: dict[str, Any] = {
        "baseline_dataset_id": baseline.get("dataset", {}).get("dataset_id"),
        "methods": {},
    }
    for method in METHODS:
        current_metrics = report["methods"].get(method, {}).get("metrics", {})
        baseline_metrics = (
            baseline.get("methods", {}).get(method, {}).get("metrics", {})
        )
        comparison["methods"][method] = {
            name: (current_metrics[name] - baseline_metrics[name])
            for name in current_metrics
            if isinstance(current_metrics.get(name), (int, float))
            and isinstance(baseline_metrics.get(name), (int, float))
        }
    return comparison


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    dataset, dataset_path = load_dataset(args.dataset)
    report = await evaluate_dataset(dataset, dataset_path, top_k=args.top_k)
    report["baseline_comparison"] = compare_baseline(report, args.baseline)
    if args.write_baseline:
        Path(args.write_baseline).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate Anvikshiki retrieval against the versioned philosophical golden set."
    )
    parser.add_argument("--dataset", help="Path to a retrieval dataset JSON file.")
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Ranking cutoff used for Recall, Precision, and nDCG.",
    )
    parser.add_argument(
        "--baseline", help="Existing JSON report used for metric deltas."
    )
    parser.add_argument(
        "--write-baseline", help="Write this report as a reusable baseline JSON file."
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit the complete JSON report."
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        report = asyncio.run(_run(args))
    except (EvaluationError, OSError) as exc:
        print(f"EVALUATION_FAILED: {exc}")
        return 2
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"dataset={report['dataset']['dataset_id']} signature={report['deterministic_signature']}"
        )
        for method in METHODS:
            metrics = report["methods"][method]["metrics"]
            print(
                f"{method}: recall@{args.top_k}={metrics.get(f'recall@{args.top_k}'):.4f} "
                f"precision@{args.top_k}={metrics.get(f'precision@{args.top_k}'):.4f} "
                f"mrr={metrics.get('mrr'):.4f} ndcg@{args.top_k}={metrics.get(f'ndcg@{args.top_k}'):.4f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
