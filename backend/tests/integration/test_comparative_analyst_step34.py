import pytest

from backend.app.application.agents.comparative_analyst import ComparativeAnalyst
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
async def test_comparative_analyst_structured_output(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        analyst = ComparativeAnalyst(session)

        result = await analyst.compare_perspectives(
            primary_source_id="source_nyaya_1",
            secondary_source_id="source_buddhist_2",
            claims_to_compare=[
                {"statement": "Perception is valid knowledge.", "relation": "AGREEMENT"},
                {"statement": "Perception apprehends a permanent substance.", "relation": "CONTRADICTION"}
            ],
            interpretations=[
                {"scholar": "Vatsyayana", "view": "Direct realism"},
                {"scholar": "Dignaga", "view": "Sensation-based constructivism"}
            ],
            terminology_map={"substance": "Dravya vs. Svena"},
            methodological_notes=["Nyaya employs direct category analysis; Buddhist epistemology employs momentariness analysis."]
        )

        # Assertions & Checkpoints Verification
        assert len(result["agreements"]) == 1
        assert len(result["contradictions"]) == 1
        assert len(result["terminology_differences"]) == 1
        assert len(result["methodological_differences"]) == 1
        assert result["is_evidence_linked"] is True