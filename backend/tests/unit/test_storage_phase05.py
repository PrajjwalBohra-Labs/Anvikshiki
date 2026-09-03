from pathlib import Path

import pytest

from backend.app.core.errors import AnvikshikiDomainError
from backend.app.infrastructure.storage.local_storage import LocalStorageService


@pytest.fixture
def storage_service(tmp_path, monkeypatch):
    from backend.app.core.config import settings
    # Override every storage root to use temporary directories for isolation.
    roots = {
        "STORAGE_LOCAL_ROOT": "originals",
        "EXTRACTED_LOCAL_ROOT": "extracted",
        "OCR_LOCAL_ROOT": "OCR",
        "CACHE_LOCAL_ROOT": "cached_web",
        "EXPORTS_LOCAL_ROOT": "exports",
        "TEMPORARY_LOCAL_ROOT": "temporary",
    }
    for setting_name, directory_name in roots.items():
        monkeypatch.setattr(settings, setting_name, str(tmp_path / directory_name))
    return LocalStorageService()

@pytest.mark.asyncio
async def test_store_and_retrieve_file(storage_service):
    content = b"This is a primary philosophical text."
    filename = "nyaya_sutra.txt"
    
    # Store
    metadata = await storage_service.store_original(content, filename)
    assert metadata.size_bytes == len(content)
    assert metadata.mime_type == "text/plain"
    assert metadata.checksum_sha256
    assert metadata.stored_at.tzinfo is not None
    assert Path(metadata.storage_path).parent == Path(storage_service.originals_dir)
    
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
        await storage_service.retrieve_file(
            str(Path(storage_service.originals_dir) / "nonexistent/path.pdf")
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_original_storage_rejects_path_traversal_and_deletion(storage_service, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"must remain inaccessible")

    with pytest.raises(AnvikshikiDomainError) as traversal:
        await storage_service.retrieve_file(str(outside))
    assert traversal.value.status_code == 400

    metadata = await storage_service.store_original(b"cannot be deleted", "immutable.txt")
    with pytest.raises(AnvikshikiDomainError) as deletion:
        await storage_service.delete_file(metadata.storage_path)
    assert deletion.value.status_code == 409
    assert Path(metadata.storage_path).read_bytes() == b"cannot be deleted"


@pytest.mark.asyncio
async def test_original_storage_creates_separate_configured_roots(storage_service):
    assert storage_service.originals_dir.is_dir()
    assert storage_service.extracted_dir.is_dir()
    assert storage_service.ocr_dir.is_dir()
    assert storage_service.cached_web_dir.is_dir()
    assert storage_service.exports_dir.is_dir()
    assert storage_service.temporary_dir.is_dir()
