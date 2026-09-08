from backend.app.application.use_cases.adaptive_reasoning import (
    normalize_question_analysis,
    normalize_relevance_assessment,
    normalize_semantic_audit,
    research_plan_from_analysis,
)


def test_question_analysis_preserves_inquiry_specific_structure_without_ontology():
    analysis = normalize_question_analysis(
        {
            "literal_question": "Why do communities treat a river as a legal person?",
            "central_problem": "The relation between legal status and communal practice",
            "requested_task": "explain why the status is adopted",
            "inquiry_mode": "institutional and causal explanation",
            "concepts": [
                {"label": "legal personhood", "role": "institutional status"},
                {"label": "communal practice", "role": "social mechanism"},
            ],
            "relationships": [
                {"source": "legal personhood", "relation": "shapes", "target": "communal practice"}
            ],
            "research_requirements": [
                {
                    "requirement_id": "mechanisms",
                    "question_component": "why the status is adopted",
                    "evidence_needed": "legal history and community accounts",
                    "search_queries": ["river legal personhood adoption community reasons"],
                }
            ],
        },
        "Why do communities treat a river as a legal person?",
        "unspecified",
        "standard",
    )

    assert [item["label"] for item in analysis["concepts"]] == ["legal personhood", "communal practice"]
    assert analysis["relationships"][0]["relation"] == "shapes"
    assert research_plan_from_analysis(analysis)[0]["search_terms"] == [
        "river legal personhood adoption community reasons"
    ]


def test_relevance_judgment_excludes_substantive_but_unrelated_passage():
    candidates = [
        {"passage_id": "p1", "content": "Legal recognition changed the community's duties toward the river."},
        {"passage_id": "p2", "content": "Human memory depends on distributed neural processes."},
    ]
    assessment = normalize_relevance_assessment(
        {
            "evaluations": [
                {
                    "passage_id": "p1",
                    "relevance": "direct",
                    "supports_requirements": ["mechanisms"],
                    "supported_proposition": "Recognition changed communal duties.",
                    "use_for_synthesis": True,
                    "evidence_role": "direct evidence",
                },
                {
                    "passage_id": "p2",
                    "relevance": "irrelevant",
                    "supports_requirements": [],
                    "use_for_synthesis": False,
                    "evidence_role": "none",
                },
            ],
            "sufficiency": "partial",
            "missing_requirements": ["history"],
        },
        {"research_requirements": [{"requirement_id": "mechanisms"}, {"requirement_id": "history"}]},
        candidates,
    )

    assert assessment["usable_passage_ids"] == ["p1"]
    assert assessment["missing_requirements"] == ["history"]


def test_semantic_audit_rejects_topic_drift_even_when_passage_ids_are_valid():
    audit = normalize_semantic_audit(
        {
            "addresses_question": False,
            "topic_drift": True,
            "sufficient_for_answer": False,
            "irrelevant_or_unsupported_claims": ["The answer discusses an unrelated memory system."],
            "evidence_alignment": [{"passage_id": "p1", "supports": False}],
        },
        [{"passage_id": "p1", "content": "Relevant evidence."}],
    )

    assert audit["status"] == "llm"
    assert audit["topic_drift"] is True
    assert audit["evidence_alignment"][0]["supports"] is False
