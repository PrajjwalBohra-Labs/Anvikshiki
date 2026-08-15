"""
Cross-source comparison (shared by §13 Reasoning and §19 Research):
pairwise agreement/divergence between retrieved chunks, based on
keyword overlap. Used by both the Research Engine (Step 12) and now
the Reasoning Engine (this extension), so "contradictions detected"
shown anywhere in the UI is always a real, computed signal --
never an invented number.
"""

from __future__ import annotations

import re

from app.services.knowledge.retrieval import RetrievedChunk

_TOKEN_RE = re.compile(r"[a-z0-9]+")
DIVERGENCE_THRESHOLD = 0.3  # overlap ratio below this counts as divergence, not a spec number


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def source_key(chunk: RetrievedChunk) -> str:
    """A stable grouping key that works for both local documents
    (document_id) and web results (which have no document_id)."""
    return chunk.document_id or chunk.metadata.get("url") or chunk.chunk_id


def compare_chunks(chunks: list[RetrievedChunk]) -> list[dict]:
    by_source: dict[str, list[RetrievedChunk]] = {}
    for chunk in chunks:
        by_source.setdefault(source_key(chunk), []).append(chunk)

    keys = list(by_source.keys())
    comparisons = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            key_a, key_b = keys[i], keys[j]
            text_a = " ".join(c.chunk_text for c in by_source[key_a])
            text_b = " ".join(c.chunk_text for c in by_source[key_b])
            tokens_a, tokens_b = _tokenize(text_a), _tokenize(text_b)
            union = tokens_a | tokens_b
            overlap_ratio = len(tokens_a & tokens_b) / len(union) if union else 0.0
            comparisons.append(
                {
                    "source_a": key_a,
                    "source_b": key_b,
                    "overlap_ratio": overlap_ratio,
                    "relation": "agreement" if overlap_ratio >= DIVERGENCE_THRESHOLD else "divergence",
                }
            )
    return comparisons
