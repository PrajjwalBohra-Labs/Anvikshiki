from app.infrastructure.llm_adapter import LLMAdapter
from app.services.generation.generation_engine import generate_response, generate_response_text
from app.services.reasoning.reasoning_engine import ConfidenceBreakdown, ReasoningObject


class RecordingAdapter(LLMAdapter):
    """Records the prompt it was called with, for assertion, and
    returns fixed content -- no live Ollama needed."""

    def __init__(self):
        self.received_prompt = None

    def generate(self, prompt, **kwargs):
        self.received_prompt = prompt
        return "full response text"

    def stream(self, prompt, **kwargs):
        self.received_prompt = prompt
        for token in ["Hello", " world", "."]:
            yield token

    def embed(self, text):
        raise NotImplementedError

    def summarize(self, text, **kwargs):
        raise NotImplementedError


def _sample_reasoning() -> ReasoningObject:
    return ReasoningObject(
        problem="What is Anvikshiki?",
        facts=[{"chunk_id": "ch1", "text": "Anvikshiki separates reasoning from generation."}],
        evidence=[
            {"chunk_id": "ch1", "source_document_id": "d1", "source_document_title": "Doc A", "score": 0.9}
        ],
        confidence=ConfidenceBreakdown(0.5, 1.0, 0.6, 0.8, 0.9, 0.76),
        conclusion={"primary_chunk_id": "ch1", "supporting_relationship_count": 0, "requires_generation": True},
    )


def test_generate_response_streams_tokens_from_adapter():
    adapter = RecordingAdapter()
    tokens = list(generate_response(_sample_reasoning(), "What is Anvikshiki?", llm_adapter=adapter))
    assert tokens == ["Hello", " world", "."]


def test_generate_response_sends_evidence_and_query_in_prompt():
    adapter = RecordingAdapter()
    list(generate_response(_sample_reasoning(), "What is Anvikshiki?", llm_adapter=adapter))
    assert "Anvikshiki separates reasoning from generation." in adapter.received_prompt
    assert "What is Anvikshiki?" in adapter.received_prompt


def test_generate_response_text_returns_full_string_non_streaming():
    adapter = RecordingAdapter()
    result = generate_response_text(_sample_reasoning(), "What is Anvikshiki?", llm_adapter=adapter)
    assert result == "full response text"
