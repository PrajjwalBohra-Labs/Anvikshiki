import pytest

from backend.app.application.agents.research_agent import ResearchAgent
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
async def test_research_agent_discovery_and_provenance(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        agent = ResearchAgent(session, max_results=3)

        # Candidate URLs including valid scholarly, discovery, and unverified social media
        candidate_urls = [
            "https://plato.stanford.edu/entries/epistemology/",
            "https://en.wikipedia.org/wiki/Pramana",
            "https://twitter.com/random_post/status/999",  # Should be rejected
            "https://plato.stanford.edu/entries/epistemology/" # Duplicate test
        ]

        sources = await agent.execute_discovery("What is valid knowledge?", candidate_urls)

        # Assertions & Checkpoints Verification
        # 1. Agent found sources and deduplicated correctly
        assert len(sources) == 2
        assert sources[0]["reference_url"] == "https://plato.stanford.edu/entries/epistemology/"
        assert sources[1]["reference_url"] == "https://en.wikipedia.org/wiki/Pramana"

        # 2. Every source has provenance
        for src in sources:
            assert src["provenance_reason"] is not None
            assert src["source_type"] is not None