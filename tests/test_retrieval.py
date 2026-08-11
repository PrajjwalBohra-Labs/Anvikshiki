import pytest

from app.infrastructure.llm_adapter import LLMAdapter
from app.persistence import relational_db, vector_store
from app.services.knowledge.retrieval import retrieve


class FixedEmbeddingAdapter(LLMAdapter):
    """Every query embeds to [1, 0, 0] — makes semantic ranking
    against known chunk vectors deterministic for testing."""

    def generate(self, prompt, **kwargs):
        raise NotImplementedError

    def stream(self, prompt, **kwargs):
        raise NotImplementedError

    def embed(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]

    def summarize(self, text, **kwargs):
        raise NotImplementedError


@pytest.fixture(autouse=True)
def _init_stores():
    relational_db.init_db()
    vector_store.init_vector_store()


@pytest.fixture
def seeded_documents():
    doc_a = relational_db.create_document("Doc A", "path/a.txt", "hash-a")
    doc_b = relational_db.create_document("Doc B", "path/b.txt", "hash-b")

    vector_store.insert_embedding(doc_a, "cats are wonderful pets", [1.0, 0.0, 0.0])
    vector_store.insert_embedding(doc_a, "dogs are loyal companions", [0.0, 1.0, 0.0])
    vector_store.insert_embedding(doc_b, "the stock market fell today", [0.0, 0.0, 1.0])

    return doc_a, doc_b


def test_retrieve_ranks_semantic_and_keyword_match_highest(seeded_documents):
    doc_a, _ = seeded_documents
    results = retrieve("cats", top_k=3, llm_adapter=FixedEmbeddingAdapter())

    assert results[0].chunk_text == "cats are wonderful pets"
    assert results[0].document_id == doc_a
    assert results[0].document_title == "Doc A"
    assert results[0].score >= results[1].score >= results[2].score


def test_retrieve_filters_by_document_id(seeded_documents):
    doc_a, doc_b = seeded_documents
    results = retrieve("market", top_k=5, document_id=doc_b, llm_adapter=FixedEmbeddingAdapter())

    assert len(results) == 1
    assert results[0].document_id == doc_b


def test_retrieve_respects_top_k(seeded_documents):
    results = retrieve("pets", top_k=1, llm_adapter=FixedEmbeddingAdapter())
    assert len(results) == 1


def test_retrieve_empty_query_returns_no_results(seeded_documents):
    assert retrieve("   ", llm_adapter=FixedEmbeddingAdapter()) == []


def test_retrieve_min_score_filters_out_weak_matches(seeded_documents):
    results = retrieve("cats", top_k=5, min_score=0.9, llm_adapter=FixedEmbeddingAdapter())
    # only the exact semantic + keyword match clears a 0.9 combined threshold
    assert all(r.chunk_text == "cats are wonderful pets" for r in results)
