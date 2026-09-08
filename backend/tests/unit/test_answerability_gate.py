from backend.app.application.use_cases.adaptive_reasoning import normalize_question_analysis
from backend.app.application.use_cases.research_reasoning import group_underlying_works
from backend.app.application.use_cases.synthesis_validation_service import (
    SynthesisValidationService,
)


QUESTION = "How perceptions changes with time but the experience remains stationary?"
PASSAGE = {
    "passage_id": "p1",
    "source_id": "s1",
    "source_title": "Temporal Experience Study",
    "author": "A. Scholar",
    "content": "Perception changes as sensory conditions vary, while temporal retention connects successive experiences.",
}


def _understanding():
    return normalize_question_analysis(
        {
            "concepts": [
                {"label": "perception"},
                {"label": "experience"},
                {"label": "stationary"},
                {"label": "change"},
                {"label": "time"},
            ],
            "research_requirements": [
                {
                    "requirement_id": "relation",
                    "question_component": QUESTION,
                    "search_queries": [QUESTION],
                    "required": True,
                }
            ],
        },
        QUESTION,
        "Philosophy",
        "deep",
    )


def test_metadata_summary_is_rejected_even_with_a_citation():
    result = SynthesisValidationService.validate_answerability(
        QUESTION,
        "The passages are from the Philosophy Institute and were published in 2026. [P1]",
        _understanding(),
        [PASSAGE],
    )

    assert result["is_approved"] is False
    assert result["relevance"] == "FAIL"
    assert result["question_coverage"] == "FAIL"


def test_direct_answer_without_evidence_is_not_falsely_approved():
    result = SynthesisValidationService.validate_answerability(
        QUESTION,
        "Perception can change over time while experience may remain continuous; stationary may mean stable awareness rather than unchanging contents.",
        _understanding(),
        [PASSAGE],
    )

    assert result["answerability"] == "PASS"
    assert result["evidence_support"] == "FAIL"
    assert result["is_approved"] is False


def test_relevant_substantive_passage_supports_answer():
    result = SynthesisValidationService.validate_answerability(
        QUESTION,
        "Perception can change over time while experience may remain continuous; stationary may mean stable awareness rather than unchanging contents. [P1]",
        _understanding(),
        [PASSAGE],
    )

    assert result["is_approved"] is True
    assert all(value == "PASS" for value in result["gates"].values())


def test_citation_to_unrelated_passage_fails_support_gate():
    unrelated = {**PASSAGE, "content": "The medieval text describes poetic meter and ornament."}
    result = SynthesisValidationService.validate_answerability(
        QUESTION,
        "Perception can change over time while experience may remain continuous; stationary may mean stable awareness. [P1]",
        _understanding(),
        [unrelated],
    )

    assert result["is_approved"] is False
    assert result["evidence_support"] == "FAIL"


def test_question_specific_terms_are_supported_when_supplied_by_the_llm():
    understanding = _understanding()
    assert [item["label"] for item in understanding["concepts"]] == [
        "perception", "experience", "stationary", "change", "time"
    ]
    assert understanding["research_requirements"]


def test_archived_versions_group_as_one_underlying_work():
    groups = group_underlying_works([
        {"title": "Temporal Experience", "author": "A. Scholar", "canonical_url": "https://example.org/work"},
        {"title": "Temporal Experience", "author": "A. Scholar", "canonical_url": "https://example.org/work?archive=2024"},
    ])

    assert len(groups) == 1
    assert len(next(iter(groups.values()))) == 2
