import pytest

from app.infrastructure.observability import get_current_trace_id, get_trace_store, new_trace_id, set_current_trace_id
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


def test_handle_message_generates_its_own_trace_id_when_none_active():
    assert get_current_trace_id() is None
    result = handle_message(
        "how does reasoning work?", llm_adapter=GroundedAdapter(), memory_engine=MemoryEngine(),
    )
    assert result.trace_id != ""


def test_full_pipeline_is_traceable_end_to_end_via_one_trace_id():
    document_id = relational_db.create_document("Doc A", "path/a.txt", "hash")
    vector_store.insert_embedding(document_id, "a grounded fact.", [1.0, 0.0, 0.0])

    result = handle_message(
        "tell me the grounded fact", llm_adapter=GroundedAdapter(), memory_engine=MemoryEngine(),
    )

    events = get_trace_store().get_trace(result.trace_id)
    stages_seen = {e.stage for e in events}

    # every dialogue stage the turn walked through left a trace event
    assert "conversation_turn" in stages_seen
    assert "retrieve" in stages_seen
    assert "reason" in stages_seen
    assert "generate" in stages_seen
    assert "verify" in stages_seen
    assert "reflect" in stages_seen


def test_pre_existing_trace_id_is_reused_not_overwritten():
    trace_id = new_trace_id()
    set_current_trace_id(trace_id)

    result = handle_message("hello there friend", llm_adapter=GroundedAdapter(), memory_engine=MemoryEngine())

    assert result.trace_id == trace_id
