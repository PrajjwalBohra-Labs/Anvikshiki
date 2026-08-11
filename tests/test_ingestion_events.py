import pytest

from app.infrastructure.cache import retrieval_cache
from app.infrastructure.event_bus import EventBus, EventName
from app.infrastructure.llm_adapter import LLMAdapter
from app.persistence import relational_db, vector_store
from app.services.knowledge.ingestion import ingest_document


class FakeEmbeddingAdapter(LLMAdapter):
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


def test_ingestion_publishes_document_imported_and_embedding_created():
    bus = EventBus()
    document_events, embedding_events = [], []
    bus.subscribe(EventName.DOCUMENT_IMPORTED, lambda e: document_events.append(e))
    bus.subscribe(EventName.EMBEDDING_CREATED, lambda e: embedding_events.append(e))

    result = ingest_document(
        "note.txt", b"Anvikshiki test content for the event bus.",
        llm_adapter=FakeEmbeddingAdapter(), event_bus=bus,
    )

    assert len(document_events) == 1
    assert document_events[0].payload["document_id"] == result.document_id
    assert len(embedding_events) == result.chunk_count


def test_ingestion_clears_the_retrieval_cache():
    retrieval_cache.set("retrieval:some-stale-key", ["stale result"])
    ingest_document("note.txt", b"fresh content", llm_adapter=FakeEmbeddingAdapter(), event_bus=EventBus())
    assert retrieval_cache.get("retrieval:some-stale-key") is None
