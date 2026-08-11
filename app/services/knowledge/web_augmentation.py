"""
Web-Augmented Knowledge (post-Step-16 amendment). Wraps web search
results into the same RetrievedChunk shape local retrieval uses
(Step 5), so downstream code (Reasoning, Prompt Builder, Validation)
handles both uniformly while still being able to tell them apart via
source_type.
"""

from __future__ import annotations

import uuid

from app.infrastructure.web_search_adapter import WebSearchAdapter
from app.services.knowledge.retrieval import RetrievedChunk


def fetch_web_evidence(query: str, adapter: WebSearchAdapter, max_results: int = 3) -> list[RetrievedChunk]:
    results = adapter.search(query, max_results=max_results)
    return [
        RetrievedChunk(
            chunk_id=str(uuid.uuid4()),
            document_id=None,
            document_title=result.title,
            chunk_text=result.content,
            score=result.score,
            semantic_score=result.score,
            keyword_score=0.0,
            metadata={"url": result.url, "source_type": "web"},
            source_type="web",
        )
        for result in results
    ]
