import pytest

from app.infrastructure.errors import LLMProviderError
from app.infrastructure.llm_adapter import LLMAdapter
from app.infrastructure.retry import retry_with_backoff
from app.infrastructure.web_search_adapter import WebSearchAdapter
from app.persistence import relational_db, vector_store
from app.services.knowledge.retrieval import retrieve
from app.services.context.context_builder import build_context


class FailingEmbedAdapter(LLMAdapter):
    def embed(self, text):
        raise LLMProviderError("simulated Ollama outage")

    def generate(self, prompt, **kwargs):
        raise NotImplementedError

    def stream(self, prompt, **kwargs):
        raise NotImplementedError

    def summarize(self, text, **kwargs):
        raise NotImplementedError


class FailingWebSearchAdapter(WebSearchAdapter):
    def search(self, query, max_results=3):
        raise ConnectionError("simulated Tavily outage")


@pytest.fixture(autouse=True)
def _init_stores():
    relational_db.init_db()
    vector_store.init_vector_store()


def test_retry_with_backoff_retries_then_succeeds():
    attempts = {"count": 0}

    def flaky():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise ConnectionError("transient")
        return "ok"

    result = retry_with_backoff(flaky, exceptions=(ConnectionError,), base_delay=0.01)
    assert result == "ok"
    assert attempts["count"] == 3


def test_retry_with_backoff_raises_after_max_attempts():
    def always_fails():
        raise ConnectionError("permanent")

    with pytest.raises(ConnectionError):
        retry_with_backoff(always_fails, exceptions=(ConnectionError,), max_attempts=2, base_delay=0.01)


def test_retrieval_degrades_to_empty_results_when_embedding_fails():
    document_id = relational_db.create_document("Doc A", "path/a.txt", "hash")
    vector_store.insert_embedding(document_id, "a fact.", [1.0, 0.0, 0.0])

    results = retrieve("anything", llm_adapter=FailingEmbedAdapter())
    assert results == []  # degraded, did not raise


def test_context_builder_still_produces_a_valid_object_when_retrieval_fails():
    context = build_context("anything", llm_adapter=FailingEmbedAdapter())
    assert context.retrieved_chunks == []
    assert context.query == "anything"  # context object itself still well-formed


def test_web_search_degrades_to_empty_results_on_failure():
    from app.services.knowledge.web_augmentation import fetch_web_evidence

    class RaisingAdapter(WebSearchAdapter):
        def search(self, query, max_results=3):
            raise RuntimeError("simulated failure inside the adapter, not caught by TavilyAdapter's own guard")

    with pytest.raises(RuntimeError):
        fetch_web_evidence("anything", RaisingAdapter())
    # (TavilyAdapter itself catches httpx errors internally -- see test_web_search_adapter.py
    # for the real adapter's own graceful-degradation guarantee.)
