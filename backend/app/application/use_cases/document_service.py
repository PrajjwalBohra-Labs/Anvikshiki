from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.app.core.config import settings
from backend.app.core.errors import AnvikshikiDomainError
from backend.app.infrastructure.database.models import DocumentModel, PassageModel


class DocumentService:
    """Provides safe, public document metadata and file resolution."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_documents(self, source_id: str | None = None) -> list[dict[str, Any]]:
        stmt = select(DocumentModel).order_by(DocumentModel.created_at.desc())
        if source_id:
            stmt = stmt.where(DocumentModel.source_id == source_id)
        result = await self.session.execute(stmt)
        documents = result.scalars().all()
        return [await self.describe_document(document) for document in documents]

    async def get_document(self, document_id: str) -> DocumentModel | None:
        return await self.session.get(DocumentModel, document_id)

    async def describe_document(self, document: DocumentModel) -> dict[str, Any]:
        count_result = await self.session.execute(
            select(func.count(PassageModel.id)).where(PassageModel.document_id == document.id)
        )
        return {
            "document_id": document.id,
            "source_id": document.source_id,
            "checksum_sha256": document.checksum_sha256,
            "mime_type": document.mime_type,
            "original_filename": document.original_filename,
            "total_pages": document.total_pages,
            "created_at": document.created_at,
            "passages_count": int(count_result.scalar_one()),
        }

    def resolve_file_path(self, document: DocumentModel) -> Path:
        if not document.storage_path:
            raise AnvikshikiDomainError("Document file is not available.", status_code=404)
        root = Path(settings.STORAGE_LOCAL_ROOT).resolve()
        path = Path(document.storage_path).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise AnvikshikiDomainError("Document file path is invalid.", status_code=500) from exc
        if not path.is_file():
            raise AnvikshikiDomainError("Document file is not available.", status_code=404)
        return path
