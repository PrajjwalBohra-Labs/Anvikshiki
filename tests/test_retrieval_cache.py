import pytest

from app.infrastructure.llm_adapter import LLMAdapter
from app.persistence import relational_db, vector_store
from app.services.knowledge.retrieval import retrieve


class CountingAdapter(LLMAdapter):
    def __init__(self):
        self.embed_call_count = 0

    def embed(self, text: str) -> list[float]:
        self.embed_call_count += 1
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


def test_repeated_identical_query_hits_cache_and_skips_re_embedding():
    document_id = relational_db.create_document("Doc A", "path/a.txt", "hash")
    vector_store.insert_embedding(document_id, "cats are wonderful pets", [1.0, 0.0, 0.0])

    adapter = CountingAdapter()
    first = retrieve("cats", llm_adapter=adapter)
    second = retrieve("cats", llm_adapter=adapter)

    assert adapter.embed_call_count == 1  # second call was a cache hit, no re-embedding
    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]


def test_different_queries_do_not_share_a_cache_entry():
    document_id = relational_db.create_document("Doc A", "path/a.txt", "hash")
    vector_store.insert_embedding(document_id, "cats are wonderful pets", [1.0, 0.0, 0.0])

    adapter = CountingAdapter()
    retrieve("cats", llm_adapter=adapter)
    retrieve("dogs", llm_adapter=adapter)

    assert adapter.embed_call_count == 2
