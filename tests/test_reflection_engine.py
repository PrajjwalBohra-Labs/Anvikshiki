from app.services.reasoning.reasoning_engine import ConfidenceBreakdown, ReasoningObject
from app.services.validation.reflection_engine import reflect


def _reasoning(agreement=1.0, with_evidence=True, evidence_count=1) -> ReasoningObject:
    evidence = [
        {"chunk_id": f"ch{i}", "source_document_id": f"d{i}", "source_document_title": f"Doc {i}", "score": 0.8}
        for i in range(evidence_count)
    ] if with_evidence else []
    facts = [{"chunk_id": f"ch{i}", "text": f"fact {i}"} for i in range(evidence_count)] if with_evidence else []
    return ReasoningObject(
        problem="q",
        facts=facts,
        evidence=evidence,
        confidence=ConfidenceBreakdown(0.5, agreement, 0.6, 0.8, 0.9, 0.7),
    )


def test_reflection_passes_for_well_grounded_response():
    reasoning = _reasoning(agreement=1.0)
    result = reflect("[Doc 0] a grounded answer.", reasoning)
    assert result.passed is True
    assert result.failure_flags == []


def test_reflection_flags_insufficient_evidence_not_acknowledged():
    reasoning = _reasoning(with_evidence=False)
    result = reflect("The answer is definitely yes.", reasoning)
    assert "insufficient_evidence_not_acknowledged" in result.failure_flags
    assert "uncertainty_not_exposed" in result.failure_flags


def test_reflection_passes_when_insufficient_evidence_is_acknowledged():
    reasoning = _reasoning(with_evidence=False)
    result = reflect("I have insufficient evidence to answer this, and I'm not certain either way.", reasoning)
    assert result.passed is True


def test_reflection_flags_forced_synthesis_when_sources_conflict():
    reasoning = _reasoning(agreement=0.2, evidence_count=2)
    result = reflect("[Doc 0] The answer is clearly and simply yes.", reasoning)
    assert "forced_synthesis_risk" in result.failure_flags


def test_reflection_passes_when_conflict_is_acknowledged():
    reasoning = _reasoning(agreement=0.2, evidence_count=2)
    result = reflect("Sources differ here: [Doc 0] says one thing, however [Doc 1] disagrees.", reasoning)
    assert "forced_synthesis_risk" not in result.failure_flags
