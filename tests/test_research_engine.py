import pytest

from app.infrastructure.llm_adapter import LLMAdapter
from app.persistence import relational_db, vector_store
from app.services.memory.memory_engine import MemoryEngine, MemoryTier
from app.services.research.research_engine import research


class RoutingAdapter(LLMAdapter):
    """Embeds toward whichever seeded topic the sub-question mentions,
    so a multi-part question genuinely retrieves from multiple
    distinct documents -- a single fixed vector wouldn't exercise
    that. generate() returns a fixed synthesized answer citing both."""

    def embed(self, text: str) -> list[float]:
        lowered = text.lower()
        if "reasoning" in lowered:
            return [1.0, 0.0, 0.0]
        if "memory" in lowered:
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]

    def generate(self, prompt, **kwargs):
        return "[Reasoning Doc] handles reasoning. [Memory Doc] handles memory. They differ in scope."

    def stream(self, prompt, **kwargs):
        yield self.generate(prompt)

    def summarize(self, text, **kwargs):
        raise NotImplementedError


@pytest.fixture(autouse=True)
def _init_stores():
    relational_db.init_db()
    vector_store.init_vector_store()


@pytest.fixture
def seeded_two_topic_documents():
    doc_reasoning = relational_db.create_document("Reasoning Doc", "path/r.txt", "hash-r")
    doc_memory = relational_db.create_document("Memory Doc", "path/m.txt", "hash-m")
    vector_store.insert_embedding(doc_reasoning, "Reasoning is handled by a dedicated engine.", [1.0, 0.0, 0.0])
    vector_store.insert_embedding(doc_memory, "Memory is handled across seven tiers.", [0.0, 1.0, 0.0])
    return doc_reasoning, doc_memory


def test_multi_part_question_is_decomposed_into_sub_questions(seeded_two_topic_documents):
    result = research(
        "How does Anvikshiki handle reasoning and how does it handle memory?",
        llm_adapter=RoutingAdapter(),
        memory_engine=MemoryEngine(),
    )
    assert len(result.sub_questions) == 2


def test_multi_part_question_returns_multiple_distinct_references(seeded_two_topic_documents):
    result = research(
        "How does Anvikshiki handle reasoning and how does it handle memory?",
        llm_adapter=RoutingAdapter(),
        memory_engine=MemoryEngine(),
    )
    reference_ids = {ref["document_id"] for ref in result.references}
    assert len(reference_ids) == 2


def test_synthesized_answer_cites_both_sources(seeded_two_topic_documents):
    result = research(
        "How does Anvikshiki handle reasoning and how does it handle memory?",
        llm_adapter=RoutingAdapter(),
        memory_engine=MemoryEngine(),
    )
    assert "[Reasoning Doc]" in result.synthesized_answer
    assert "[Memory Doc]" in result.synthesized_answer


def test_comparisons_are_computed_across_distinct_documents(seeded_two_topic_documents):
    result = research(
        "How does Anvikshiki handle reasoning and how does it handle memory?",
        llm_adapter=RoutingAdapter(),
        memory_engine=MemoryEngine(),
    )
    assert len(result.comparisons) == 1
    pair = result.comparisons[0]
    reference_ids = {r["document_id"] for r in result.references}
    assert {pair["source_a"], pair["source_b"]} == reference_ids


def test_single_part_question_is_not_decomposed(seeded_two_topic_documents):
    result = research("How does Anvikshiki handle reasoning?", llm_adapter=RoutingAdapter(), memory_engine=MemoryEngine())
    assert result.sub_questions == ["How does Anvikshiki handle reasoning?"]


def test_research_result_is_persisted_to_research_memory(seeded_two_topic_documents):
    memory_engine = MemoryEngine()
    result = research(
        "How does Anvikshiki handle reasoning and how does it handle memory?",
        llm_adapter=RoutingAdapter(),
        memory_engine=memory_engine,
    )
    stored = memory_engine.recall(MemoryTier.RESEARCH, result.memory_id)
    assert stored is not None
    assert stored.content == result.synthesized_answer
    assert stored.metadata["question"] == "How does Anvikshiki handle reasoning and how does it handle memory?"


def test_no_evidence_produces_honest_fallback_not_fabrication():
    result = research("completely unrelated gibberish query", llm_adapter=RoutingAdapter(), memory_engine=MemoryEngine())
    assert result.chunks == []
    assert result.references == []
    assert "No evidence was found" in result.synthesized_answer


def test_research_falls_back_honestly_when_synthesis_invents_citations(seeded_two_topic_documents):
    class FabricatingAdapter(RoutingAdapter):
        def generate(self, prompt, **kwargs):
            return "Debate is a modular concept [1] that separates reasoning [2] from generation [3]."

    result = research(
        "How does Anvikshiki handle reasoning and how does it handle memory?",
        llm_adapter=FabricatingAdapter(), memory_engine=MemoryEngine(),
    )
    assert result.delivered is False
    assert "don't have enough verified evidence" in result.synthesized_answer
    assert result.validation_violations


def test_research_delivers_when_synthesis_cites_real_sources(seeded_two_topic_documents):
    result = research(
        "How does Anvikshiki handle reasoning and how does it handle memory?",
        llm_adapter=RoutingAdapter(), memory_engine=MemoryEngine(),
    )
    assert result.delivered is True
    assert result.validation_violations == []



def test_synthesize_prompt_includes_confidence_and_hedging_instruction_when_low(seeded_two_topic_documents):
    from app.services.reasoning.reasoning_engine import ConfidenceBreakdown
    from app.services.research.research_engine import _synthesize

    class CapturingAdapter(RoutingAdapter):
        def __init__(self):
            self.received_prompt = None

        def generate(self, prompt, **kwargs):
            self.received_prompt = prompt
            return "[Reasoning Doc] a hedged answer, though the evidence is limited."

    adapter = CapturingAdapter()
    low_confidence = ConfidenceBreakdown(0.5, 1.0, 0.5, 0.5, 0.3, 0.35)
    chunks = [
        c for c in _search(["reasoning"], top_k=5, llm_adapter=RoutingAdapter())
    ] if False else None  # placeholder not used; build minimal chunk directly below

    from app.services.knowledge.retrieval import RetrievedChunk
    chunk = RetrievedChunk(
        chunk_id="c1", document_id="d1", document_title="Reasoning Doc",
        chunk_text="Reasoning is handled by a dedicated engine.", score=0.3,
        semantic_score=0.3, keyword_score=0.0, metadata={}, source_type="local",
    )

    _synthesize("how does reasoning work?", [chunk], adapter, low_confidence)

    assert "0.35" in adapter.received_prompt
    assert "LOW" in adapter.received_prompt
    assert "hedging phrase" in adapter.received_prompt
