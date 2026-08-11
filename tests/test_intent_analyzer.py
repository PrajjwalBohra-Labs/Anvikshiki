from app.services.context.context_builder import ContextObject
from app.services.reasoning.intent_analyzer import analyze_intent


def test_question_is_classified_as_question():
    intent = analyze_intent("What is modular cognition?")
    assert intent.what_is_being_asked == "question"


def test_action_request_is_classified_correctly():
    intent = analyze_intent("Create a new project for this research")
    assert intent.what_is_being_asked == "action_request"


def test_statement_is_classified_correctly():
    intent = analyze_intent("Anvikshiki separates reasoning from generation")
    assert intent.what_is_being_asked == "statement"
    assert intent.should_memory_change is True


def test_short_query_requires_clarification():
    intent = analyze_intent("okay")
    assert intent.clarification_required is True
    assert intent.retrieval_should_occur is False


def test_pronoun_led_short_query_requires_clarification():
    intent = analyze_intent("it is broken")
    assert intent.clarification_required is True


def test_reasoning_trigger_sets_explicit_reasoning_flag():
    intent = analyze_intent("Why does the ingestion pipeline chunk text this way?")
    assert intent.should_reason_explicitly is True


def test_context_sufficient_reflects_retrieved_chunks():
    empty_context = ContextObject(query="x", sections=[], retrieved_chunks=[])
    intent = analyze_intent("what is this concept", context=empty_context)
    assert intent.context_sufficient is False
    assert intent.should_expose_uncertainty is True
