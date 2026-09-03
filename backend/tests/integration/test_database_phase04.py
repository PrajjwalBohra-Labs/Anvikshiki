import pytest
from sqlalchemy.future import select

from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.database.models import (
    DocumentModel,
    PassageModel,
    SourceModel,
)
from backend.app.infrastructure.database.session import Base, engine


@pytest.fixture(autouse=True)
async def setup_test_db():
    # Setup fresh tables in memory before each test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_database_crud_lifecycle():
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        # Create
        source = SourceModel(title="Tarka Samgraha", source_type=SourceType.PRIMARY)
        session.add(source)
        await session.commit()
        await session.refresh(source)
        
        assert source.id is not None
        assert source.created_at is not None

        doc = DocumentModel(source_id=source.id, checksum_sha256="test_hash_1", mime_type="application/pdf")
        session.add(doc)
        await session.flush()

        passage = PassageModel(document_id=doc.id, content="Inference is the instrumental cause of inferential knowledge.", page_number=12)
        session.add(passage)
        await session.commit()

        # Read
        result = await session.execute(select(PassageModel).where(PassageModel.id == passage.id))
        fetched_passage = result.scalars().first()
        
        assert fetched_passage is not None
        assert fetched_passage.content == "Inference is the instrumental cause of inferential knowledge."
        assert fetched_passage.document.source.title == "Tarka Samgraha"

        # Cascade Delete (Deleting source should delete doc and passage)
        await session.delete(source)
        await session.commit()

        passages_remaining = await session.execute(select(PassageModel))
        assert passages_remaining.scalars().first() is None