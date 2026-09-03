import pytest

from backend.app.application.use_cases.research_continuity import (
    ResearchContinuityService,
)
from backend.app.infrastructure.database.models import (
    EpistemicPositionModel,
    ResearchQuestionModel,
    ResearchRunModel,
    ResearchStepModel,
    UserModel,
)
from backend.app.infrastructure.database.session import Base, engine


@pytest.fixture
async def setup_test_env():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_research_continuity_resumption(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        # 1. Setup persisted research state (simulating returning user session)
        user = UserModel(username="returning_scholar")
        session.add(user)
        await session.flush()

        question = ResearchQuestionModel(
            main_question="What is Pramana in Indian epistemology?",
            subquestions=["How does Pratyaksha differ from Anumana?"],
            domain="Epistemology",
            open_questions=["Does perception require conceptual construction (Vikalpa)?"],
            research_status="ACTIVE"
        )
        session.add(question)
        await session.flush()

        run = ResearchRunModel(query="What is Pramana in Indian epistemology?", status="COMPLETED")
        session.add(run)
        await session.flush()

        step = ResearchStepModel(
            run_id=run.id,
            step_name="Evidence Extraction",
            step_type="EVIDENCE",
            status="SUCCESS",
            payload={"claims": 3, "passage_id": "pass_101"}
        )
        session.add(step)

        pos = EpistemicPositionModel(
            user_id=user.id,
            claim_statement="Pratyaksha is direct non-conceptual cognition.",
            position="accepted",
            confidence=0.9,
            status="accepted"
        )
        session.add(pos)
        await session.commit()

        # 2. Invoke Research Continuity Service
        service = ResearchContinuityService(session)
        resumed_state = await service.resume_investigation(question.id, user.id)

        # 3. Assertions & Checkpoints Verification
        assert resumed_state is not None
        assert resumed_state["main_question"] == "What is Pramana in Indian epistemology?"
        assert len(resumed_state["established_findings"]) > 0
        assert len(resumed_state["unresolved_questions"]) == 1
        assert len(resumed_state["user_positions"]) == 1
        assert len(resumed_state["evidence_trail"]) == 1
        assert len(resumed_state["research_timeline"]) == 1
        assert "Address open question" in resumed_state["suggested_next_step"]