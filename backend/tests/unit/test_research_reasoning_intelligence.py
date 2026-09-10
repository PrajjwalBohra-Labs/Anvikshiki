from backend.app.application.use_cases.research_reasoning import (
    build_reasoning_chains,
    build_research_plan,
    classify_question,
    compare_source_positions,
)


def test_compatibility_fallback_does_not_invent_an_intellectual_map():
    question = classify_question(
        "How perceptions changes with time but the experience remains stationary?",
        "Philosophy & Empirical Epistemology",
        "deep",
    )

    assert question["central_problem"] == "How perceptions changes with time but the experience remains stationary?"
    assert question["concepts"] == []
    assert question["analysis_status"] == "fallback_unavailable"
    plan = build_research_plan(question)
    assert len(plan) == 1
    assert plan[0]["search_terms"] == [question["literal_question"]]


def test_source_disagreement_is_visible_and_not_consensus():
    positions = [
        {
            "source_title": "Study A",
            "source_id": "a",
            "source_type": "SCIENTIFIC",
            "direct_statements": ["The intervention causes improved recall."],
            "qualifications": [],
        },
        {
            "source_title": "Study B",
            "source_id": "b",
            "source_type": "SCIENTIFIC",
            "direct_statements": ["The observation does not establish causation for improved recall."],
            "qualifications": ["does not establish"],
        },
    ]

    relationships = compare_source_positions(positions)

    assert relationships[0]["relation"] == "unresolved"
    assert "model-based" in relationships[0]["explanation"]


def test_insufficient_evidence_is_explicit():
    chains = build_reasoning_chains(
        {
            "literal_question": "Is this true?",
            "underlying_question": "Is this true?",
            "research_requirements": [],
        },
        [],
        [],
        [],
        [],
    )

    assert chains["gaps"]
    assert "relevant substantive passage" in chains["gaps"][0]


def test_simple_factual_question_gets_one_direct_direction():
    question = classify_question("What is the capital of France?", "general", "standard")

    assert question["inquiry_mode"] == "undetermined"
    assert len(build_research_plan(question)) == 1