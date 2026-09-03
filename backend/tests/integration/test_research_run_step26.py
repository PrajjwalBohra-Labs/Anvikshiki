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
async def test_research_run_lifecycle_and_failure_inspection(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        service = ResearchRunService(session)
        
        # 1. Create Research Run
        run = await service.create_run(query="What is Pramana in Indian epistemology?")
        assert run.id is not None
        assert run.status == "RUNNING"

        # 2. Add Steps (retrieval, source-selection, evidence, validation)
        await service.add_step(run.id, step_name="Lexical Retrieval", step_type="RETRIEVAL", status="SUCCESS", payload={"matches": 5})
        await service.add_step(run.id, step_name="Source Filtering", step_type="SOURCE_SELECTION", status="SUCCESS", payload={"retained": 3})
        await service.add_step(run.id, step_name="Evidence Extraction", step_type="EVIDENCE", status="SUCCESS", payload={"claims": 2})

        # 3. Simulate failure at validation step
        await service.add_step(run.id, step_name="Citation Validation", step_type="VALIDATION", status="FAILED", payload={"error": "Dangling citation"})
        await service.fail_run(run.id, error_message="Validation step failed due to dangling citation.")

        # 4. Inspect Run Details & Verify Last Successful Step
        details = await service.get_run_details(run.id)
        assert details["status"] == "FAILED"
        assert details["last_successful_step"] == "Evidence Extraction"
        assert len(details["steps"]) == 4
        assert details["error_message"] == "Validation step failed due to dangling citation."
