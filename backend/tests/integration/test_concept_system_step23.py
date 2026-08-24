import pytest
from backend.app.infrastructure.database.session import engine, Base
from backend.app.application.use_cases.concept_service import ConceptService

@pytest.fixture
async def setup_test_env():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_concept_system_operations(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        service = ConceptService(session)
        
        # 1. Create concept preserving original terminology and transliteration
        concept1 = await service.create_concept(
            name="Perception",
            definition="Direct valid cognition arising from sense-object contact.",
            original_language_term="प्रत्यक्ष",
            transliteration="Pratyaksha",
            aliases=["Sensory Cognition"]
        )
        assert concept1.id is not None
        assert concept1.original_language_term == "प्रत्यक्ष"
        assert concept1.transliteration == "Pratyaksha"

        concept2 = await service.create_concept(
            name="Inference",
            definition="Cognition that follows from previous perception.",
            original_language_term="अनुमान",
            transliteration="Anumana"
        )

        # 2. Test concept searchability (English, original term, transliteration)
        search_results = await service.search_concepts("Pratyaksha")
        assert len(search_results) == 1
        assert search_results[0].name == "Perception"

        # 3. Link related concepts
        link = await service.link_concepts(concept2.id, concept1.id, "DEPENDS_ON")
        assert link.id is not None
        assert link.relationship_type == "DEPENDS_ON"