import pytest
from backend.app.infrastructure.database.session import engine, Base
from backend.app.infrastructure.database.models import SourceModel, DocumentModel, PassageModel, ClaimModel, EvidenceLinkModel
from backend.app.domain.models.enums import SourceType, SourceRelationshipType, ClaimType, RelationType
from backend.app.application.use_cases.concept_service import ConceptService
from backend.app.application.use_cases.knowledge_graph_service import KnowledgeGraphService

@pytest.fixture
async def setup_test_env():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_knowledge_graph_traversal_and_queries(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        # 1. Setup Concepts and Relationships
        c_service = ConceptService(session)
        c1 = await c_service.create_concept("Pratyaksha", "Perception definition")
        c2 = await c_service.create_concept("Pramana", "Valid means of knowledge")
        await c_service.link_concepts(c1.id, c2.id, "IS_A")

        # 2. Setup Sources and Relationships
        s1 = SourceModel(title="Yoga Sutra", author="Panjali", source_type=SourceType.PRIMARY)
        s2 = SourceModel(title="Yoga Bhashya", author="Vyasa", source_type=SourceType.SECONDARY)
        session.add_all([s1, s2])
        await session.flush()

        from backend.app.infrastructure.database.models import SourceRelationshipModel
        rel = SourceRelationshipModel(source_id=s2.id, target_id=s1.id, relationship_type=SourceRelationshipType.COMMENTARY_ON)
        session.add(rel)

        # 3. Setup Claim -> Evidence -> Passage -> Source
        doc = DocumentModel(source_id=s1.id, checksum_sha256="kg_hash", mime_type="text/plain")
        session.add(doc)
        await session.flush()
        
        passage = PassageModel(document_id=doc.id, content="Yoga is the restriction of the fluctuations of mind.")
        session.add(passage)
        await session.flush()

        claim = ClaimModel(statement="Yoga controls mental fluctuations.", claim_type=ClaimType.DIRECT_SOURCE_CLAIM)
        session.add(claim)
        await session.flush()

        ev_link = EvidenceLinkModel(claim_id=claim.id, passage_id=passage.id, relation_type=RelationType.SUPPORTS)
        session.add(ev_link)
        await session.commit()

        # 4. Test Knowledge Graph Service Queries
        kg_service = KnowledgeGraphService(session)

        # Related concepts query
        related_concepts = await kg_service.get_related_concepts(c1.id)
        assert len(related_concepts) == 1
        assert related_concepts[0]["concept"].name == "Pramana"
        assert related_concepts[0]["relationship_type"] == "IS_A"

        # Related sources query
        related_sources = await kg_service.get_related_sources(s2.id)
        assert len(related_sources) == 1
        assert related_sources[0]["source"].title == "Yoga Sutra"
        assert related_sources[0]["relationship_type"] == SourceRelationshipType.COMMENTARY_ON

        # Evidence subgraph traversal query
        subgraph = await kg_service.traverse_evidence_subgraph(claim.id)
        assert len(subgraph) == 1
        assert subgraph[0]["passage"].content == "Yoga is the restriction of the fluctuations of mind."
        assert subgraph[0]["source"].title == "Yoga Sutra"