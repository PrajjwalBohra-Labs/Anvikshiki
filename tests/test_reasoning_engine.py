import inspect

import pytest

from app.infrastructure.llm_adapter import LLMAdapter
from app.persistence import relational_db, vector_store
from app.services.context.context_builder import build_context
from app.services.reasoning.reasoning_engine import reason


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


def test_reasoning_engine_has_no_llm_adapter_parameter():
    """Structural guarantee: this engine cannot call a provider even
    by mistake, because there is no way to hand it one."""
    params = inspect.signature(reason).parameters
    assert "llm_adapter" not in params


def test_reason_produces_structured_object_with_confidence(seeded_knowledge):
    context = build_context("how does reasoning work?", llm_adapter=FixedEmbeddingAdapter())
    result = reason("how does reasoning work?", context)

    assert result.problem == "how does reasoning work?"
    assert result.facts
    assert result.evidence
    assert result.relationships
    assert result.confidence is not None
    assert result.conclusion["requires_generation"] is True


def test_confidence_overall_is_between_zero_and_one(seeded_knowledge):
    context = build_context("reasoning", llm_adapter=FixedEmbeddingAdapter())
    result = reason("reasoning", context)
    assert 0.0 <= result.confidence.overall <= 1.0


def test_assumptions_flag_missing_evidence_when_nothing_retrieved():
    empty_context = build_context("completely unrelated gibberish query", llm_adapter=FixedEmbeddingAdapter())
    result = reason("completely unrelated gibberish query", empty_context)
    assert "no_retrieved_evidence" in result.assumptions


def test_relationships_included_when_concept_graph_present(seeded_knowledge):
    context = build_context("reasoning", llm_adapter=FixedEmbeddingAdapter())
    result = reason("reasoning", context)
    assert any(r["relationship_type"] == "derived_from" for r in result.relationships)


def test_reason_output_contains_zero_generated_prose_fields(seeded_knowledge):
    """conclusion must be a structured pointer, not free text."""
    context = build_context("reasoning", llm_adapter=FixedEmbeddingAdapter())
    result = reason("reasoning", context)
    assert isinstance(result.conclusion, dict)
    assert "primary_chunk_id" in result.conclusion


def test_reasoning_object_includes_real_comparisons_field(seeded_knowledge):
    context = build_context("reasoning", llm_adapter=FixedEmbeddingAdapter())
    result = reason("reasoning", context)
    assert isinstance(result.comparisons, list)
