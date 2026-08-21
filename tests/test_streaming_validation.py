import pytest

from app.infrastructure.llm_adapter import LLMAdapter
from app.persistence import relational_db, vector_store
from app.services.conversation.conversation_controller import handle_message_stream
from app.services.memory.memory_engine import MemoryEngine


class GroundedStreamAdapter(LLMAdapter):
    def embed(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]

    def generate(self, prompt, **kwargs):
        raise NotImplementedError

    def stream(self, prompt, **kwargs):
        for token in ["[Doc A]", " a grounded", " streamed answer."]:
            yield token

    def summarize(self, text, **kwargs):
        raise NotImplementedError


class FabricatingStreamAdapter(GroundedStreamAdapter):
    def stream(self, prompt, **kwargs):
        for token in ["[Nonexistent Source]", " a fabricated claim."]:
            yield token


@pytest.fixture(autouse=True)
def _init_stores():
    relational_db.init_db()
    vector_store.init_vector_store()


@pytest.fixture
def seeded_document():
    document_id = relational_db.create_document("Doc A", "path/a.txt", "hash")
    vector_store.insert_embedding(document_id, "a grounded fact.", [1.0, 0.0, 0.0])
    return document_id


def test_stream_yields_tokens_then_a_real_validated_done_event(seeded_document):
    events = list(
        handle_message_stream(
            "tell me the grounded fact", llm_adapter=GroundedStreamAdapter(), memory_engine=MemoryEngine()
        )
    )
    token_events = [e for e in events if e["type"] == "token"]
    done_events = [e for e in events if e["type"] == "done"]

    assert len(token_events) == 3  # real incremental tokens, not one blob
    assert len(done_events) == 1
    assert done_events[0]["delivered"] is True
    assert done_events[0]["verification"] is not None


def test_stream_honestly_flags_undelivered_when_validation_fails(seeded_document):
    events = list(
        handle_message_stream(
            "tell me the grounded fact", llm_adapter=FabricatingStreamAdapter(), memory_engine=MemoryEngine()
        )
    )
    done_event = next(e for e in events if e["type"] == "done")

    assert done_event["delivered"] is False
    assert done_event["response"] is None  # not persisted/re-delivered as fact, even though tokens streamed


def test_stream_persists_question_and_answer_same_as_validated_path(seeded_document):
    events = list(
        handle_message_stream(
            "tell me the grounded fact", llm_adapter=GroundedStreamAdapter(), memory_engine=MemoryEngine()
        )
    )
    done_event = next(e for e in events if e["type"] == "done")

    assert relational_db.get_question(done_event["question_id"]) is not None
    assert relational_db.get_answer(done_event["answer_id"]) is not None
