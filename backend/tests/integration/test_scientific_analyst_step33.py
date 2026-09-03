import pytest

from backend.app.application.agents.scientific_analyst import ScientificAnalyst
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
async def test_scientific_analyst_full_extraction(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        analyst = ScientificAnalyst(session)

        result = await analyst.analyze_study(
            study_title="Cognitive Correlates in Meditation Practice",
            research_question="Does meditation correlate with alpha wave synchronization?",
            hypothesis="Higher meditation frequency causes increased alpha power.",
            study_type="Cross-sectional Observational",
            population="Healthy adult meditators",
            sample="50 practitioners (aged 25-45)",
            methodology="EEG recording during resting state and meditation sessions.",
            variables={"independent": "meditation hours", "dependent": "alpha wave amplitude"},
            measurements=["EEG microvolts (uV)", "Self-reported practice hours"],
            results="Moderate positive correlation (r = 0.45, p < 0.05) observed.",
            limitations=["Cross-sectional design prevents causal attribution.", "Small sample size."],
            replication="Pending independent replication across larger cohorts.",
            author_interpretation="Meditation causes significant neural restructuring and cognitive enhancement.",
            is_observational=True
        )

        # Assertions & Checkpoints Verification
        assert result["population"] == "Healthy adult meditators"
        assert result["sample"] == "50 practitioners (aged 25-45)"
        assert len(result["measurements"]) == 2
        assert result["replication"] == "Pending independent replication across larger cohorts."
        assert result["distinguishes_correlation_from_causation"] is True
        assert result["distinguishes_observation_from_interpretation"] is True
        assert "Caution: Observational study design" in result["independent_assessment"]
        assert result["claims_overstated"] is True
