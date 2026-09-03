import pytest

from backend.app.application.use_cases.research_question_service import (
    ResearchQuestionService,
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
async def test_research_question_persistence_and_continuity(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        service = ResearchQuestionService(session)
        
        # 1. Create Research Question with subquestions, scope, and user position
        rq = await service.create_question(
            main_question="What are the valid means of knowledge (Pramana) in Nyaya philosophy?",
            subquestions=["What is Pratyaksha?", "How does Anumana operate?"],
            scope="Classical Indian Epistemology",
            domain="Philosophy",
            constraints=["Primary texts only"],
            user_position="Inference depends entirely on prior direct perception."
        )

        assert rq.id is not None
        assert rq.main_question is not None
        assert len(rq.subquestions) == 2

        # 2. Test Research Continuity (Updating History)
        updated = await service.update_research_history(rq.id, {"step": "Retrieved primary passages from Nyaya Sutra", "timestamp": "2026-08-24"})
        assert len(updated.research_history) == 1
        assert updated.research_history[0]["step"] == "Retrieved primary passages from Nyaya Sutra"