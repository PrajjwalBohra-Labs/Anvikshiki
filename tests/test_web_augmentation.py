import pytest

from app.infrastructure.web_search_adapter import WebSearchAdapter, WebSearchResult
from app.infrastructure.llm_adapter import LLMAdapter
from app.persistence import relational_db, vector_store
from app.services.context.context_builder import build_context
from app.services.research.research_engine import research
from app.services.memory.memory_engine import MemoryEngine


class FixedWebAdapter(WebSearchAdapter):
    def search(self, query, max_results=3):
        return [WebSearchResult(title="External Paper", url="https://example.com/paper", content="external findings", score=0.8)]


class FixedEmbeddingAdapter(LLMAdapter):
    def embed(self, text):
        return [1.0, 0.0, 0.0]

    def generate(self, prompt, **kwargs):
        return "[External Paper] cited correctly."

    def stream(self, prompt, **kwargs):
        raise NotImplementedError

    def summarize(self, text, **kwargs):
        raise NotImplementedError


@pytest.fixture(autouse=True)
def _init_stores():
    relational_db.init_db()
    vector_store.init_vector_store()


def test_web_search_disabled_by_default_does_not_add_web_evidence():
    context = build_context("anything", llm_adapter=FixedEmbeddingAdapter())
    assert all(c.source_type == "local" for c in context.retrieved_chunks)


def test_web_search_enabled_adds_tagged_web_evidence():
    context = build_context(
        "anything", llm_adapter=FixedEmbeddingAdapter(),
        use_web_search=True, web_search_adapter=FixedWebAdapter(),
    )
    assert any(c.source_type == "web" for c in context.retrieved_chunks)
    web_chunk = next(c for c in context.retrieved_chunks if c.source_type == "web")
    assert web_chunk.document_title == "External Paper"
    assert web_chunk.metadata["url"] == "https://example.com/paper"


def test_research_web_search_disabled_by_default():
    result = research("anything", llm_adapter=FixedEmbeddingAdapter(), memory_engine=MemoryEngine())
    assert all(c.source_type == "local" for c in result.chunks)


def test_research_web_search_enabled_adds_distinct_web_reference():
    result = research(
        "anything", llm_adapter=FixedEmbeddingAdapter(), memory_engine=MemoryEngine(),
        use_web_search=True, web_search_adapter=FixedWebAdapter(),
    )
    web_refs = [r for r in result.references if r["source_type"] == "web"]
    assert len(web_refs) == 1
    assert web_refs[0]["title"] == "External Paper"
