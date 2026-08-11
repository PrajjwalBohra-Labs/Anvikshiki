import pytest

from app.infrastructure.llm_adapter import LLMAdapter
from app.persistence import relational_db, vector_store
from app.services.conversation.conversation_controller import (
    INTERNAL_ERROR_RESPONSE,
    handle_message,
)
from app.services.memory.memory_engine import MemoryEngine


class WorkingAdapter(LLMAdapter):
    def embed(self, text):
        return [1.0, 0.0, 0.0]

    def generate(self, prompt, **kwargs):
        return "[Doc A] a grounded answer."

    def stream(self, prompt, **kwargs):
        yield self.generate(prompt)

    def summarize(self, text, **kwargs):
        raise NotImplementedError


class ReasoningExplodesAdapter(WorkingAdapter):
    """Everything works except we'"'"'ll monkeypatch reason() itself to
    fail -- this adapter is just here so retrieval/generation succeed
    right up to the point of the simulated engine failure."""


@pytest.fixture(autouse=True)
def _init_stores():
    relational_db.init_db()
    vector_store.init_vector_store()


@pytest.fixture
def seeded_document():
    document_id = relational_db.create_document("Doc A", "path/a.txt", "hash")
    vector_store.insert_embedding(document_id, "a grounded fact.", [1.0, 0.0, 0.0])
    return document_id


def test_baseline_pipeline_still_works(seeded_document):
    """Sanity check before we disable anything."""
    result = handle_message("what is the grounded fact?", llm_adapter=WorkingAdapter(), memory_engine=MemoryEngine())
    assert result.delivered is True


def test_reasoning_engine_failure_degrades_gracefully_other_subsystems_still_work(seeded_document, monkeypatch):
    """§4 exit criteria: disable one engine, confirm the rest keep
    working. Reasoning is 'disabled' by forcing it to raise; Session
    creation, Retrieval, and Persistence must still have functioned."""
    import app.services.conversation.conversation_controller as controller_module

    def exploding_reason(query, context):
        raise RuntimeError("simulated Reasoning Engine failure")

    monkeypatch.setattr(controller_module, "reason", exploding_reason)

    result = handle_message(
        "what is the grounded fact?", llm_adapter=WorkingAdapter(), memory_engine=MemoryEngine(),
    )

    # The pipeline did NOT crash -- it returned a safe result.
    assert result.delivered is False
    assert result.response == INTERNAL_ERROR_RESPONSE

    # Other subsystems that ran BEFORE the failure still did their job:
    assert relational_db.get_session(result.session_id) is not None  # Session Engine worked
    assert relational_db.get_question(result.question_id) is not None  # Persistence worked


def test_generation_engine_failure_degrades_gracefully(seeded_document, monkeypatch):
    import app.services.conversation.conversation_controller as controller_module

    def exploding_generate(*args, **kwargs):
        raise RuntimeError("simulated Generation Engine failure")

    monkeypatch.setattr(controller_module, "generate_response_text", exploding_generate)

    result = handle_message(
        "what is the grounded fact?", llm_adapter=WorkingAdapter(), memory_engine=MemoryEngine(),
    )

    assert result.delivered is False
    assert result.response == INTERNAL_ERROR_RESPONSE
    assert relational_db.get_session(result.session_id) is not None


def test_validation_engine_failure_degrades_gracefully(seeded_document, monkeypatch):
    import app.services.conversation.conversation_controller as controller_module

    def exploding_validate(*args, **kwargs):
        raise RuntimeError("simulated Validation Engine failure")

    monkeypatch.setattr(controller_module, "validate", exploding_validate)

    result = handle_message(
        "what is the grounded fact?", llm_adapter=WorkingAdapter(), memory_engine=MemoryEngine(),
    )

    assert result.delivered is False
    assert result.response == INTERNAL_ERROR_RESPONSE
