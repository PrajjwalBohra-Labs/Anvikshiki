import pytest
from backend.app.infrastructure.database.session import engine, Base
from backend.app.infrastructure.database.models import SourceModel
from backend.app.infrastructure.storage.local_storage import LocalStorageService
from backend.app.application.use_cases.ingestion import DocumentIngestionService
from backend.app.domain.models.enums import SourceType
from backend.app.core.errors import AnvikshikiDomainError

@pytest.fixture
async def setup_test_env(tmp_path, monkeypatch):
    # Setup fresh tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    # Isolate storage
    from backend.app.core.config import settings
    monkeypatch.setattr(settings, "STORAGE_LOCAL_ROOT", str(tmp_path / "originals"))
    
    yield
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_text_document_ingestion_lifecycle(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    storage = LocalStorageService()
    
    async with AsyncSessionLocal() as session:
        # 1. Setup Source
        source = SourceModel(title="Upanishad Notes", source_type=SourceType.PRIMARY)
        session.add(source)
        await session.commit()

        # 2. Ingest Document
        service = DocumentIngestionService(session, storage)
        content = b"This is the first paragraph.\n\nAnd this is the second paragraph."
        
        doc, passages = await service.ingest_file(
            source_id=source.id,
            filename="notes.txt",
            content=content
        )
        
        # 3. Verify Document and Storage
        assert doc.id is not None
        assert doc.mime_type == "text/plain"
        assert doc.total_pages == 1
        assert doc.size_bytes == len(content)
        
        # 4. Verify Passages
        assert len(passages) == 2
        assert passages[0].content == "This is the first paragraph."
        assert passages[1].content == "And this is the second paragraph."
        assert passages[0].document_id == doc.id
        
        # 5. Verify Idempotency/Duplicate Prevention
        with pytest.raises(AnvikshikiDomainError) as exc:
            await service.ingest_file(source.id, "notes.txt", content)
        assert exc.value.status_code == 409
