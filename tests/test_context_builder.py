import pytest

from app.infrastructure.llm_adapter import LLMAdapter
from app.persistence import relational_db, vector_store
from app.services.context.context_builder import build_context


class FixedEmbeddingAdapter(LLMAdapter):
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
def seeded_knowledge():
    document_id = relational_db.create_document("Cognitive Arch Doc", "path/doc.txt", "hash")
    concept_id = relational_db.create_concept("Modular Cognition", "core concept")
    relational_db.create_relationship(
        source_type="concept",
        source_id=concept_id,
        target_type="document",
        target_id=document_id,
        relationship_type="derived_from",
    )
    vector_store.insert_embedding(
        document_id,
        "Anvikshiki separates reasoning from generation.",
        [1.0, 0.0, 0.0],
        metadata={"concept_id": concept_id},
    )
    return document_id, concept_id


def test_build_context_includes_message_and_retrieved_knowledge(seeded_knowledge):
    context = build_context("how does reasoning work?", llm_adapter=FixedEmbeddingAdapter())

    section_names = {s.name for s in context.sections}
    assert "current_message" in section_names
    assert "system_policies" in section_names
    assert "retrieved_knowledge" in section_names
    assert context.retrieved_chunks[0].chunk_text.startswith("Anvikshiki")


def test_build_context_includes_concept_graph_when_available(seeded_knowledge):
    context = build_context("reasoning", llm_adapter=FixedEmbeddingAdapter())
    section_names = {s.name for s in context.sections}
    assert "concept_graph" in section_names


def test_build_context_includes_project_state_when_given(seeded_knowledge):
    project_id = relational_db.create_project("Anvikshiki", "modular cognitive architecture")
    context = build_context(
        "reasoning", project_id=project_id, llm_adapter=FixedEmbeddingAdapter()
    )
    section_names = {s.name for s in context.sections}
    assert "project_state" in section_names


def test_build_context_includes_dialogue_history_when_given(seeded_knowledge):
    history = [{"role": "user", "content": "what is Anvikshiki?"}]
    context = build_context(
        "reasoning", conversation_history=history, llm_adapter=FixedEmbeddingAdapter()
    )
    section_names = {s.name for s in context.sections}
    assert "dialogue_history" in section_names


def test_build_context_respects_token_budget(seeded_knowledge):
    # A generous budget keeps everything.
    generous = build_context("reasoning", max_tokens=4000, llm_adapter=FixedEmbeddingAdapter())
    generous_sections = {s.name for s in generous.sections}
    assert "retrieved_knowledge" in generous_sections

    # A tight budget (just above what the mandatory sections alone
    # cost) must still keep the mandatory sections in full, and must
    # drop or truncate optional content to fit.
    mandatory_cost = sum(
        s.estimated_tokens for s in generous.sections if s.priority == 0
    )
    tight_budget = mandatory_cost + 5
    tight = build_context("reasoning", max_tokens=tight_budget, llm_adapter=FixedEmbeddingAdapter())
    tight_sections = {s.name for s in tight.sections}

    assert "system_policies" in tight_sections
    assert "current_message" in tight_sections
    assert tight.total_estimated_tokens < generous.total_estimated_tokens


def test_build_context_keeps_mandatory_sections_even_under_extreme_budget(seeded_knowledge):
    # Even an unrealistically tiny budget must not drop mandatory content.
    context = build_context("reasoning", max_tokens=1, llm_adapter=FixedEmbeddingAdapter())
    section_names = {s.name for s in context.sections}
    assert "system_policies" in section_names
    assert "current_message" in section_names
    # optional sections have no room at all and must be excluded
    assert "retrieved_knowledge" not in section_names


def test_build_context_handles_empty_query(seeded_knowledge):
    context = build_context("   ", llm_adapter=FixedEmbeddingAdapter())
    assert context.retrieved_chunks == []
    assert context.query == ""

