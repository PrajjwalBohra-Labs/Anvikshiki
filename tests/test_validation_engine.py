from app.infrastructure.llm_adapter import LLMAdapter
from app.services.reasoning.reasoning_engine import ConfidenceBreakdown, ReasoningObject
from app.services.validation.validation_engine import generate_and_validate, validate


def _reasoning(confidence_overall=0.8, agreement=1.0, with_evidence=True) -> ReasoningObject:
    evidence = (
        [{"chunk_id": "ch1", "source_document_id": "d1", "source_document_title": "Doc A", "score": 0.9}]
        if with_evidence
        else []
    )
    facts = [{"chunk_id": "ch1", "text": "Anvikshiki separates reasoning from generation."}] if with_evidence else []
    return ReasoningObject(
        problem="What is Anvikshiki?",
        facts=facts,
        evidence=evidence,
        confidence=ConfidenceBreakdown(0.5, agreement, 0.6, 0.8, 0.9, confidence_overall),
        conclusion={"primary_chunk_id": "ch1" if with_evidence else None, "supporting_relationship_count": 0, "requires_generation": True},
    )


class FixedTextAdapter(LLMAdapter):
    def __init__(self, text: str):
        self._text = text

    def generate(self, prompt, **kwargs):
        return self._text

    def stream(self, prompt, **kwargs):
        yield self._text

    def embed(self, text):
        raise NotImplementedError

    def summarize(self, text, **kwargs):
        raise NotImplementedError


def test_valid_citation_and_matching_confidence_passes():
    reasoning = _reasoning(confidence_overall=0.8)
    text = "[Doc A] Anvikshiki separates reasoning from generation. My confidence is 0.80 out of 1.0."
    result = validate(text, reasoning)
    assert result.passed is True


def test_unknown_citation_is_flagged():
    reasoning = _reasoning()
    text = "[Fake Source] this is unsupported."
    result = validate(text, reasoning)
    assert result.passed is False
    assert any("Fake Source" in v for v in result.citation_violations)


def test_confidence_mismatch_is_flagged():
    reasoning = _reasoning(confidence_overall=0.58)
    text = "[Doc A] some claim. My confidence is 0.95 out of 1.0."
    result = validate(text, reasoning)
    assert result.passed is False
    assert result.consistency_violations


def test_low_confidence_without_uncertainty_language_is_flagged():
    reasoning = _reasoning(confidence_overall=0.3)
    text = "[Doc A] This is definitely true with no doubt whatsoever."
    result = validate(text, reasoning)
    assert result.passed is False
    assert result.confidence_violations


def test_low_confidence_with_uncertainty_language_passes():
    reasoning = _reasoning(confidence_overall=0.3)
    text = "[Doc A] this seems likely, but the evidence is limited evidence and I'm not fully certain."
    result = validate(text, reasoning)
    assert result.confidence_violations == []


def test_no_evidence_without_acknowledgement_is_flagged():
    reasoning = _reasoning(with_evidence=False)
    text = "The answer is definitely yes."
    result = validate(text, reasoning)
    assert result.passed is False
    assert result.completeness_violations


def test_generate_and_validate_blocks_a_deliberately_unsupported_response():
    reasoning = _reasoning(confidence_overall=0.58)
    fabricated_text = "[Nonexistent Source] Anvikshiki was invented in 1990. My confidence is 0.99 out of 1.0."
    adapter = FixedTextAdapter(fabricated_text)

    delivered, result = generate_and_validate(reasoning, "What is Anvikshiki?", llm_adapter=adapter)

    assert delivered is None
    assert result.passed is False
    assert result.all_violations


def test_generate_and_validate_delivers_a_supported_response():
    reasoning = _reasoning(confidence_overall=0.8)
    grounded_text = "[Doc A] Anvikshiki separates reasoning from generation. My confidence is 0.80 out of 1.0."
    adapter = FixedTextAdapter(grounded_text)

    delivered, result = generate_and_validate(reasoning, "What is Anvikshiki?", llm_adapter=adapter)

    assert delivered == grounded_text
    assert result.passed is True
