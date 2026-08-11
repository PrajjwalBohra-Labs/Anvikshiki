from app.services.prompt.prompt_builder import build_prompt
from app.services.reasoning.reasoning_engine import ConfidenceBreakdown, ReasoningObject


def _sample_reasoning() -> ReasoningObject:
    return ReasoningObject(
        problem="What is Anvikshiki?",
        definitions=[{"concept_id": "c1", "name": "Anvikshiki", "description": "a cognitive architecture"}],
        facts=[{"chunk_id": "ch1", "text": "Anvikshiki separates reasoning from generation."}],
        evidence=[
            {"chunk_id": "ch1", "source_document_id": "d1", "source_document_title": "Doc A", "score": 0.9}
        ],
        assumptions=["limited_source_coverage"],
        constraints=[],
        relationships=[],
        inference=["ch1"],
        alternatives=[],
        confidence=ConfidenceBreakdown(0.5, 1.0, 0.6, 0.8, 0.9, 0.76),
        conclusion={"primary_chunk_id": "ch1", "supporting_relationship_count": 0, "requires_generation": True},
    )


def test_layers_appear_in_the_exact_section_22_order():
    prompt = build_prompt(
        _sample_reasoning(), "What is Anvikshiki?", conversation_history=[{"role": "user", "content": "hi"}]
    )
    names = [name for name, _ in prompt.layers]
    assert names == [
        "system",
        "architecture_policy",
        "module_policy",
        "task_instructions",
        "retrieved_knowledge",
        "conversation",
        "user_message",
    ]


def test_empty_conversation_history_omits_conversation_layer():
    prompt = build_prompt(_sample_reasoning(), "What is Anvikshiki?")
    names = [name for name, _ in prompt.layers]
    assert "conversation" not in names


def test_module_policy_reflects_assumptions_and_confidence():
    prompt = build_prompt(_sample_reasoning(), "q")
    module_policy = dict(prompt.layers)["module_policy"]
    assert "limited_source_coverage" in module_policy
    assert "0.76" in module_policy


def test_retrieved_knowledge_includes_source_title_and_text():
    prompt = build_prompt(_sample_reasoning(), "q")
    retrieved = dict(prompt.layers)["retrieved_knowledge"]
    assert "Doc A" in retrieved
    assert "Anvikshiki separates reasoning from generation." in retrieved


def test_user_message_is_always_the_last_layer():
    prompt = build_prompt(_sample_reasoning(), "q")
    assert prompt.layers[-1] == ("user_message", "q")


def test_missing_evidence_is_stated_plainly_not_fabricated():
    empty_reasoning = _sample_reasoning()
    empty_reasoning.evidence = []
    prompt = build_prompt(empty_reasoning, "q")
    retrieved = dict(prompt.layers)["retrieved_knowledge"]
    assert "No evidence was retrieved" in retrieved
