import hashlib
import mimetypes
from pathlib import Path
from datetime import datetime, timezone
from pydantic import BaseModel
import aiofiles
import aiofiles.os

from backend.app.core.config import settings
from backend.app.core.errors import AnvikshikiDomainError

class StoredFileMetadata(BaseModel):
    checksum_sha256: str
    original_filename: str
    storage_path: str
    mime_type: str
    size_bytes: int
    stored_at: datetime

class LocalStorageService:
    def __init__(self):
        self.originals_dir = Path(settings.STORAGE_LOCAL_ROOT)
        self.originals_dir.mkdir(parents=True, exist_ok=True)
        
    async def _calculate_checksum(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    async def store_original(self, content: bytes, filename: str) -> StoredFileMetadata:
        checksum = await self._calculate_checksum(content)
        
        # Content-addressable storage approach prevents accidental overwrites
        extension = Path(filename).suffix
        storage_filename = f"{checksum}{extension}"
        storage_path = self.originals_dir / storage_filename
        
        mime_type, _ = mimetypes.guess_type(filename)
        if not mime_type:
            mime_type = "application/octet-stream"

        # Prevent overwrite: if file with this exact SHA-256 already exists, skip writing
        if not storage_path.exists():
            async with aiofiles.open(storage_path, 'wb') as f:
                await f.write(content)
                
        return StoredFileMetadata(
            checksum_sha256=checksum,
            original_filename=filename,
            storage_path=str(storage_path),
            mime_type=mime_type,
            size_bytes=len(content),
            stored_at=datetime.now(timezone.utc)
        )

    async def retrieve_file(self, storage_path: str) -> bytes:
        path = Path(storage_path)
        if not path.exists() or not path.is_file():
            raise AnvikshikiDomainError(f"File not found at {storage_path}", status_code=404)
        
        async with aiofiles.open(path, 'rb') as f:
            return await f.read()

    async def verify_integrity(self, storage_path: str, expected_checksum: str) -> bool:
        try:
            content = await self.retrieve_file(storage_path)
            actual_checksum = await self._calculate_checksum(content)
            return actual_checksum == expected_checksum
        except AnvikshikiDomainError:
            return False

    async def delete_file(self, storage_path: str) -> bool:
        path = Path(storage_path)
        if path.exists():
            await aiofiles.os.remove(path)
            return True
        return False