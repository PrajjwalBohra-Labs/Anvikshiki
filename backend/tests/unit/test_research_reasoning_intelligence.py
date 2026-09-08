from backend.app.application.use_cases.research_reasoning import (
    build_reasoning_chains,
    build_research_plan,
    classify_question,
    compare_source_positions,
)


def test_exact_question_is_understood_as_a_tension_not_a_definition_list():
    question = classify_question(
        "How perceptions changes with time but the experience remains stationary?",
        "Philosophy & Empirical Epistemology",
        "deep",
    )

    assert question["central_problem"] == "Changing perceptual content versus the claimed continuity or stability of experience"
    assert question["answer_type"] == "philosophical_analysis"
    assert {item["concept"] for item in question["ambiguities"]} == {"experience", "stationary"}
    plan = build_research_plan(question)
    assert len(plan) >= 4
    assert all(item["purpose"] and item["expected_evidence"] for item in plan)


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

    assert relationships[0]["relation"] == "contradicts"
    assert "incompatible" in relationships[0]["explanation"]


def test_insufficient_evidence_is_explicit():
    chains = build_reasoning_chains(
        {
            "literal_question": "Is this true?",
            "underlying_question": "Is this true?",
            "ambiguities": [],
            "premise_challenges": [],
        },
        [],
        [],
        [],
        [],
    )

    assert chains["gaps"]
    assert "cannot be answered" in chains["gaps"][0]


def test_simple_factual_question_gets_one_direct_direction():
    question = classify_question("What is the capital of France?", "general", "standard")

    assert question["answer_type"] == "fact_verification"
    assert len(build_research_plan(question)) == 1
