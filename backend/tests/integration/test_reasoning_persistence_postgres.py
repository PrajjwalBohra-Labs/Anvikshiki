import pytest

from backend.app.application.use_cases.reasoning_persistence import (
    get_reasoning_artifacts,
    persist_reasoning_artifacts,
)
from backend.app.infrastructure.database.models import ResearchQuestionModel, ResearchRunModel
from backend.app.infrastructure.database.session import AsyncSessionLocal


@pytest.mark.asyncio
async def test_reasoning_artifacts_persist_as_run_scoped_typed_records():
    async with AsyncSessionLocal() as session:
        question = ResearchQuestionModel(
            main_question="How perceptions changes with time but the experience remains stationary?",
            user_id="reasoning-persistence-test",
            domain="Philosophy",
        )
        session.add(question)
        await session.flush()
        run = ResearchRunModel(
            query=question.main_question,
            user_id=question.user_id,
            research_question_id=question.id,
            status="RUNNING",
        )
        session.add(run)
        await session.flush()

        result = {
            "reasoning": {
                "question_understanding": {
                    "literal_question": question.main_question,
                    "underlying_question": "Can changing contents coexist with continuity?",
                    "answer_type": "philosophical_analysis",
                    "key_concepts": ["perception", "experience"],
                    "ambiguities": [{"concept": "stationary", "possible_meanings": ["stable awareness"]}],
                    "assumptions": ["content and continuity may differ"],
                    "disciplines": ["philosophy"],
                },
                "research_plan": [{
                    "question": "What changes?",
                    "purpose": "Separate content and continuity.",
                    "expected_evidence": "Definitions.",
                    "search_terms": ["perception continuity"],
                }],
                "source_positions": [{
                    "source_title": "Fixture source",
                    "central_position": "The stream has continuity.",
                    "direct_statements": ["The stream has continuity."],
                    "evidence_passage_ids": [],
                    "statement_status": "direct_statement",
                }],
                "relationships": [],
                "chains": [{
                    "type": "INFERENCE",
                    "conclusion": "A distinction is needed.",
                    "analysis": "The terms differ.",
                    "evidence": [],
                    "confidence": 0.5,
                    "inference_status": "inferential",
                }],
                "gaps": ["No acquired source."],
            },
            "specialist_analysis": {
                "challenges": [{
                    "type": "premise_challenge",
                    "objection": "Stationary may be ambiguous.",
                    "confidence": 0.8,
                }]
            },
        }
        try:
            await persist_reasoning_artifacts(session, run, question, result)
            artifacts = await get_reasoning_artifacts(session, run.id)
            assert len(artifacts["research_directions"]) == 1
            assert len(artifacts["source_positions"]) == 1
            assert len(artifacts["inferences"]) == 1
            assert len(artifacts["challenges"]) == 1
            assert len(artifacts["nodes"]) >= 3
            assert artifacts["edges"]
            assert question.primary_intent == "philosophical_analysis"
        finally:
            await session.delete(run)
            await session.commit()
            await session.delete(question)
            await session.commit()
