import asyncio
import hashlib
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

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
        # Resolve configured roots once and keep all file operations scoped to
        # the originals root. Other roots are created here so each storage
        # concern remains physically distinct before later pipeline steps
        # write to them.
        self.originals_dir = Path(settings.STORAGE_LOCAL_ROOT).resolve()
        self.extracted_dir = Path(settings.EXTRACTED_LOCAL_ROOT).resolve()
        self.ocr_dir = Path(settings.OCR_LOCAL_ROOT).resolve()
        self.cached_web_dir = Path(settings.CACHE_LOCAL_ROOT).resolve()
        self.exports_dir = Path(settings.EXPORTS_LOCAL_ROOT).resolve()
        self.temporary_dir = Path(settings.TEMPORARY_LOCAL_ROOT).resolve()
        for directory in (
            self.originals_dir,
            self.extracted_dir,
            self.ocr_dir,
            self.cached_web_dir,
            self.exports_dir,
            self.temporary_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _calculate_checksum(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def _safe_filename(filename: str) -> str:
        if not isinstance(filename, str) or not filename.strip():
            raise AnvikshikiDomainError("A filename is required.", status_code=400)
        safe_filename = Path(filename).name
        if safe_filename in {"", ".", ".."}:
            raise AnvikshikiDomainError("The filename is invalid.", status_code=400)
        return safe_filename

    def _resolve_original_path(self, storage_path: str) -> Path:
        if not isinstance(storage_path, str) or not storage_path.strip():
            raise AnvikshikiDomainError("The original file path is invalid.", status_code=400)

        candidate = Path(storage_path)
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        path = candidate.resolve(strict=False)
        try:
            path.relative_to(self.originals_dir)
        except ValueError as exc:
            raise AnvikshikiDomainError("The original file path is invalid.", status_code=400) from exc
        if path == self.originals_dir:
            raise AnvikshikiDomainError("The original file path is invalid.", status_code=400)
        return path

    @staticmethod
    def _create_exclusive(path: Path, content: bytes) -> None:
        # xb is the atomic overwrite guard. A concurrent writer cannot replace
        # an existing authoritative original between an exists() check and the
        # write.
        with path.open("xb") as file_handle:
            file_handle.write(content)

    async def store_original(
        self,
        content: bytes,
        filename: str,
        mime_type: str | None = None,
    ) -> StoredFileMetadata:
        if not isinstance(content, bytes):
            raise AnvikshikiDomainError("Original file content must be bytes.", status_code=400)

        safe_filename = self._safe_filename(filename)
        checksum = self._calculate_checksum(content)

        # Keep checksum-plus-extension naming while allowing only a harmless
        # filename suffix into the filesystem path.
        extension = Path(safe_filename).suffix.lower()
        if not re.fullmatch(r"\.[a-z0-9]{1,16}", extension):
            extension = ""
        storage_path = self.originals_dir / f"{checksum}{extension}"

        if mime_type is None:
            mime_type, _ = mimetypes.guess_type(safe_filename)
        if not mime_type:
            mime_type = "application/octet-stream"

        try:
            await asyncio.to_thread(self._create_exclusive, storage_path, content)
        except FileExistsError:
            existing_content = await asyncio.to_thread(storage_path.read_bytes)
            if self._calculate_checksum(existing_content) != checksum:
                raise AnvikshikiDomainError(
                    "An original file already exists with an invalid checksum.", status_code=409
                )

        stored_at = datetime.fromtimestamp(
            await asyncio.to_thread(lambda: storage_path.stat().st_mtime), tz=timezone.utc
        )

        return StoredFileMetadata(
            checksum_sha256=checksum,
            original_filename=safe_filename,
            storage_path=str(storage_path),
            mime_type=mime_type,
            size_bytes=len(content),
            stored_at=stored_at,
        )

    async def retrieve_file(self, storage_path: str) -> bytes:
        path = self._resolve_original_path(storage_path)
        if not path.exists() or not path.is_file():
            raise AnvikshikiDomainError("Original file is not available.", status_code=404)

        return await asyncio.to_thread(path.read_bytes)

    async def verify_integrity(self, storage_path: str, expected_checksum: str) -> bool:
        try:
            content = await self.retrieve_file(storage_path)
            return self._calculate_checksum(content) == expected_checksum
        except AnvikshikiDomainError:
            return False

    async def delete_file(self, storage_path: str) -> bool:
        self._resolve_original_path(storage_path)
        raise AnvikshikiDomainError(
            "Original files are immutable and cannot be deleted.", status_code=409
        )
