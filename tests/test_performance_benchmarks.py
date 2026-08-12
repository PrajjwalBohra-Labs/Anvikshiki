"""
Performance Benchmarks (§31). Uses mocked adapters (fast,
deterministic -- no live Ollama) to measure actual algorithmic
performance: the vector store does a linear pure-Python cosine-
similarity scan (§4 "no native build steps" ruled out a compiled ANN
index), so it's worth knowing how that scales before the real corpus
grows large. These are generous soft ceilings for personal local
hardware, not strict SLAs -- but a 10x-scale regression should fail.
"""

import time

import pytest

from app.infrastructure.llm_adapter import LLMAdapter
from app.persistence import relational_db, vector_store
from app.services.knowledge.retrieval import retrieve

RETRIEVAL_CEILING_SECONDS = 2.0


class FixedEmbeddingAdapter(LLMAdapter):
    def embed(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]

    def generate(self, prompt, **kwargs):
        raise NotImplementedError

    def stream(self, prompt, **kwargs):
        raise NotImplementedError

    def summarize(self, text, **kwargs):
        raise NotImplementedError


@pytest.fixture(autouse=True)
def _init_stores():
    relational_db.init_db()
    vector_store.init_vector_store()


def test_retrieval_scales_acceptably_over_two_hundred_chunks():
    document_id = relational_db.create_document("Big Doc", "path/big.txt", "hash")
    for i in range(200):
        vector_store.insert_embedding(document_id, f"chunk number {i} about various topics.", [1.0, 0.0, 0.0])

    start = time.perf_counter()
    results = retrieve("various topics", top_k=5, llm_adapter=FixedEmbeddingAdapter())
    duration = time.perf_counter() - start

    assert len(results) == 5
    assert duration < RETRIEVAL_CEILING_SECONDS, (
        f"Retrieval over 200 chunks took {duration:.3f}s, exceeding the {RETRIEVAL_CEILING_SECONDS}s "
        "soft ceiling -- investigate before the real corpus grows this large."
    )
    print(f"\n[benchmark] retrieval over 200 chunks: {duration * 1000:.1f}ms")
