import pytest

from app.infrastructure.event_bus import EventBus, EventName
from app.infrastructure.llm_adapter import LLMAdapter
from app.persistence import relational_db, vector_store
from app.services.conversation.conversation_controller import handle_message
from app.services.memory.memory_engine import MemoryEngine


class GroundedAdapter(LLMAdapter):
    def generate(self, prompt, **kwargs):
        return "[Doc A] a grounded answer."

    def stream(self, prompt, **kwargs):
        yield self.generate(prompt)

    def embed(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]

    def summarize(self, text, **kwargs):
        raise NotImplementedError


@pytest.fixture(autouse=True)
def _init_stores():
    relational_db.init_db()
    vector_store.init_vector_store()


@pytest.fixture
def seeded_document():
    document_id = relational_db.create_document("Doc A", "path/a.txt", "hash")
    vector_store.insert_embedding(document_id, "a grounded fact.", [1.0, 0.0, 0.0])
    return document_id


def test_new_session_publishes_conversation_started(seeded_document):
    bus = EventBus()
    received = []
    bus.subscribe(EventName.CONVERSATION_STARTED, lambda e: received.append(e))

    handle_message(
        "tell me the grounded fact", llm_adapter=GroundedAdapter(),
        memory_engine=MemoryEngine(), event_bus=bus,
    )

    assert len(received) == 1


def test_reused_session_does_not_publish_conversation_started_again(seeded_document):
    bus = EventBus()
    received = []
    bus.subscribe(EventName.CONVERSATION_STARTED, lambda e: received.append(e))

    existing_session_id = relational_db.create_session()
    handle_message(
        "tell me the grounded fact", session_id=existing_session_id,
        llm_adapter=GroundedAdapter(), memory_engine=MemoryEngine(), event_bus=bus,
    )

    assert received == []


def test_reasoning_completed_is_published(seeded_document):
    bus = EventBus()
    received = []
    bus.subscribe(EventName.REASONING_COMPLETED, lambda e: received.append(e))

    handle_message(
        "tell me the grounded fact", llm_adapter=GroundedAdapter(),
        memory_engine=MemoryEngine(), event_bus=bus,
    )

    assert len(received) == 1
    assert received[0].payload["confidence"] is not None
