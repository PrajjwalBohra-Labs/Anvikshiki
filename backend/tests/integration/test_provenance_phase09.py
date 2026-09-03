import pytest

from backend.app.application.use_cases.provenance import ProvenanceService
from backend.app.domain.models.enums import SourceRelationshipType, SourceType
from backend.app.infrastructure.database.models import SourceModel
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
async def test_provenance_lineage_trace(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        # 1. Create the chain of sources
        primary = SourceModel(title="Nyaya Sutras", source_type=SourceType.PRIMARY)
        translation = SourceModel(title="Jha Translation", source_type=SourceType.TRANSLATION)
        commentary = SourceModel(title="Modern Commentary on Jha", source_type=SourceType.SCHOLARLY_SECONDARY)
        
        session.add_all([primary, translation, commentary])
        await session.commit()
        
        prov_service = ProvenanceService(session)
        
        # 2. Link them: Commentary -> Translation -> Primary
        await prov_service.link_sources(commentary.id, translation.id, SourceRelationshipType.COMMENTARY_ON)
        await prov_service.link_sources(translation.id, primary.id, SourceRelationshipType.TRANSLATION_OF)
        
        # 3. Trace the lineage from the bottom up
        lineage = await prov_service.trace_lineage(commentary.id)
        
        # Verify the chain structure
        assert len(lineage) == 3
        
        assert lineage[0]["title"] == "Modern Commentary on Jha"
        assert lineage[0]["derived_via"] == SourceRelationshipType.COMMENTARY_ON
        
        assert lineage[1]["title"] == "Jha Translation"
        assert lineage[1]["derived_via"] == SourceRelationshipType.TRANSLATION_OF
        
        assert lineage[2]["title"] == "Nyaya Sutras"
        assert "derived_via" not in lineage[2] # Top of the chain