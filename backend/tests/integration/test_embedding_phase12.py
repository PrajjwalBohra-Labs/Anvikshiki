import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.infrastructure.database.session import engine, Base
from backend.app.infrastructure.database.models import SourceModel, DocumentModel, PassageModel
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.llm.embedding_client import LocalEmbeddingClient

@pytest.fixture
async def setup_test_env():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_embedding_generation_and_persistence(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    # 1. Initialize the adapter (Operating in TEST profile, meaning synthetic deterministic vectors)
    client = LocalEmbeddingClient()
    text = "The nature of consciousness."
    
    vector = await client.get_embedding(text)
    
    assert isinstance(vector, list)
    assert len(vector) > 0
    assert all(isinstance(x, float) for x in vector)
    
    # Prove determinism (same text = same vector)
    vector2 = await client.get_embedding(text)
    assert vector == vector2
    
    async with AsyncSessionLocal() as session:
        # 2. Setup mock document
        source = SourceModel(title="Test", source_type=SourceType.SCHOLARLY_SECONDARY)
        session.add(source)
        await session.flush()
        
        doc = DocumentModel(source_id=source.id, checksum_sha256="test_embed", mime_type="text/plain")
        session.add(doc)
        await session.flush()
        
        # 3. Persist the embedding and the model identifier
        passage = PassageModel(
            document_id=doc.id, 
            content=text,
            embedding_model=client.model,
            embedding=vector
        )
        session.add(passage)
        await session.commit()
        await session.refresh(passage)
        
        # 4. Verify Database Retrieval
        assert passage.embedding_model == "nomic-embed-text"
        assert len(passage.embedding) == len(vector)
        # Verify L2 normalization boundary on the synthetic vector
        import math
        norm = math.sqrt(sum(x * x for x in passage.embedding))
        assert math.isclose(norm, 1.0, rel_tol=1e-5)