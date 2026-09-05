import pytest

from backend.app.application.use_cases.research_run_service import ResearchRunService
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
async def test_research_run_lifecycle_and_steps(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        service = ResearchRunService(session)
        
        # 1. Start Run
        run = await service.start_run(query="What is epistemology?")
        assert run.id is not None
        assert run.status == "RUNNING"
        assert run.finished_at is None
        
        # 2. Log Steps
        step1 = await service.log_step(run.id, step_name="RETRIEVAL", payload={"candidates_found": 5})
        assert step1.id is not None
        assert step1.step_name == "RETRIEVAL"
        assert step1.status == "SUCCESS"
        
        step2 = await service.log_step(run.id, step_name="VALIDATION", status="SUCCESS", payload={"citations_valid": True})
        assert step2.step_name == "VALIDATION"
        
        # 3. Complete Run
        completed_run = await service.complete_run(run.id)
        assert completed_run.status == "COMPLETED"
        assert completed_run.finished_at is not None