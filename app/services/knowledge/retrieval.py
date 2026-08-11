"""
Retrieval pipeline (§19 "Retrieval (software detail)"):
Normalization -> Expansion -> Hybrid search (semantic + keyword) ->
Ranking -> Filtering -> Context packaging.

"Retrieval combines: semantic retrieval, keyword retrieval, metadata
filtering" (§19). Expansion here is deliberately minimal -- a token
set of the query -- and is a named seam for a smarter synonym/LLM-
driven expansion to replace later (§17 replaceability).

Wired to the retrieval cache (§26): an identical (query, top_k,
document_id, min_score) call returns the cached result without
re-embedding the query or re-scanning the vector store. Invalidation
happens on document updates -- see the ingestion pipeline's
retrieval_cache.clear() call.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.infrastructure.cache import retrieval_cache
from app.infrastructure.errors import LLMProviderError
from app.infrastructure.observability import record_event
from app.infrastructure.llm_adapter import LLMAdapter, get_llm_adapter
from app.persistence import relational_db, vector_store

DEFAULT_TOP_K = 5
SEMANTIC_WEIGHT = 0.7
KEYWORD_WEIGHT = 0.3
_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str | None
    document_title: str | None
    chunk_text: str
    score: float
    semantic_score: float
    keyword_score: float
    metadata: dict
    source_type: str = "local"  # "local" (knowledge base) or "web" (post-Step-16 amendment)
    source_type: str = "local"  # "local" (knowledge base) or "web" (post-Step-16 amendment)


def _normalize_query(query: str) -> str:
    query = unicodedata.normalize("NFC", query)
    return re.sub(r"\s+", " ", query).strip()


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def _expand_query(normalized_query: str) -> set[str]:
    """Minimal expansion: the token set of the query itself."""
    return _tokenize(normalized_query)


def _keyword_score(query_tokens: set[str], chunk_text: str) -> float:
    if not query_tokens:
        return 0.0
    chunk_tokens = _tokenize(chunk_text)
    if not chunk_tokens:
        return 0.0
    overlap = query_tokens & chunk_tokens
    return len(overlap) / len(query_tokens)


def _cache_key(normalized_query: str, top_k: int, document_id: str | None, min_score: float) -> str:
    return f"retrieval:{normalized_query}|{top_k}|{document_id}|{min_score}"


def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    min_score: float = 0.0,
    document_id: str | None = None,
    llm_adapter: LLMAdapter | None = None,
) -> list[RetrievedChunk]:
    """Runs the full §19 retrieval pipeline for one query."""

    normalized_query = _normalize_query(query)
    if not normalized_query:
        return []

    cache_key = _cache_key(normalized_query, top_k, document_id, min_score)
    cached = retrieval_cache.get(cache_key)
    if cached is not None:
        record_event(
            "retrieval", "metric", cache_hit=True, chunk_count=len(cached),
            top_score=cached[0].score if cached else None,
        )
        return cached

    llm_adapter = llm_adapter or get_llm_adapter()
    query_tokens = _expand_query(normalized_query)

    try:
        query_embedding = llm_adapter.embed(normalized_query)
    except LLMProviderError as exc:
        # Graceful degradation (§4/§29): retrieval failing does not
        # crash the pipeline -- it just means no evidence was found,
        # which §16 Failure Behaviour (Steps 8-10) already handles
        # honestly (acknowledge, avoid fabrication, expose uncertainty).
        record_event("retrieval", "failure", error=str(exc), error_type="LLMProviderError")
        return []

    candidates_pool = vector_store.get_all_chunks()

    if document_id is not None:
        candidates_pool = [c for c in candidates_pool if c["document_id"] == document_id]

    scored_candidates = []
    for chunk in candidates_pool:
        semantic_score = vector_store.cosine_similarity(query_embedding, chunk["embedding"])
        keyword_score = _keyword_score(query_tokens, chunk["chunk_text"])
        combined = SEMANTIC_WEIGHT * semantic_score + KEYWORD_WEIGHT * keyword_score
        scored_candidates.append((chunk, semantic_score, keyword_score, combined))

    scored_candidates.sort(key=lambda item: item[3], reverse=True)
    filtered = [c for c in scored_candidates if c[3] >= min_score][:top_k]

    title_cache: dict[str, str | None] = {}
    results: list[RetrievedChunk] = []
    for chunk, semantic_score, keyword_score, combined in filtered:
        doc_id = chunk["document_id"]
        if doc_id not in title_cache:
            document = relational_db.get_document(doc_id) if doc_id else None
            title_cache[doc_id] = document["title"] if document else None

        results.append(
            RetrievedChunk(
                chunk_id=chunk["id"],
                document_id=doc_id,
                document_title=title_cache[doc_id],
                chunk_text=chunk["chunk_text"],
                score=combined,
                semantic_score=semantic_score,
                keyword_score=keyword_score,
                metadata=chunk["metadata"],
            )
        )

    retrieval_cache.set(cache_key, results)
    record_event(
        "retrieval", "metric", cache_hit=False, chunk_count=len(results),
        top_score=results[0].score if results else None,
    )
    return results




