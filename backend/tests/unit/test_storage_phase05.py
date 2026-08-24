import pytest
from pathlib import Path
from backend.app.infrastructure.storage.local_storage import LocalStorageService
from backend.app.core.errors import AnvikshikiDomainError

@pytest.fixture
def storage_service(tmp_path, monkeypatch):
    from backend.app.core.config import settings
    # Override storage root to use a temporary directory for isolation
    monkeypatch.setattr(settings, "STORAGE_LOCAL_ROOT", str(tmp_path / "originals"))
    return LocalStorageService()

@pytest.mark.asyncio
async def test_store_and_retrieve_file(storage_service):
    content = b"This is a primary philosophical text."
    filename = "nyaya_sutra.txt"
    
    # Store
    metadata = await storage_service.store_original(content, filename)
    assert metadata.size_bytes == len(content)
    assert metadata.mime_type == "text/plain"
    
    # Retrieve
    retrieved_content = await storage_service.retrieve_file(metadata.storage_path)
    assert retrieved_content == content
    
    # Integrity check
    assert await storage_service.verify_integrity(metadata.storage_path, metadata.checksum_sha256) is True
    assert await storage_service.verify_integrity(metadata.storage_path, "invalid_checksum") is False

@pytest.mark.asyncio
async def test_prevent_overwrite_idempotency(storage_service):
    content = b"Immutable original document."
    filename = "document.pdf"
    
    # First save
    metadata_1 = await storage_service.store_original(content, filename)
    
    # Second save attempt (should succeed without error, pointing to the same file)
    metadata_2 = await storage_service.store_original(content, filename)
    
    assert metadata_1.storage_path == metadata_2.storage_path
    assert metadata_1.checksum_sha256 == metadata_2.checksum_sha256

@pytest.mark.asyncio
async def test_retrieve_missing_file_raises_error(storage_service):
    with pytest.raises(AnvikshikiDomainError) as exc:
        await storage_service.retrieve_file("nonexistent/path.pdf")
    assert exc.value.status_code == 404