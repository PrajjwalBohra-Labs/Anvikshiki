from typing import List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.infrastructure.database.models import DocumentModel, PassageModel, SourceModel
from backend.app.infrastructure.storage.local_storage import LocalStorageService
from backend.app.domain.models.enums import SourceType
from backend.app.core.errors import AnvikshikiDomainError
from backend.app.infrastructure.document_parsers.pdf_parser import PdfDocumentParser

class TextDocumentParser:
    @staticmethod
    def parse_text(content: bytes) -> List[dict]:
        text = content.decode("utf-8", errors="replace")
        raw_chunks = text.split("\n\n")
        passages = []
        for chunk in raw_chunks:
            cleaned = chunk.strip()
            if cleaned:
                passages.append({
                    "content": cleaned,
                    "page_number": 1,
                    "extraction_uncertainty": False,
                    "language": "en"
                })
        return passages

class DocumentIngestionService:
    def __init__(self, session: AsyncSession, storage_service: LocalStorageService):
        self.session = session
        self.storage = storage_service

    async def ingest_file(self, source_id: str, filename: str, content: bytes) -> Tuple[DocumentModel, List[PassageModel]]:
        # 1. Verify source
        source_result = await self.session.execute(select(SourceModel).where(SourceModel.id == source_id))
        source = source_result.scalars().first()
        if not source:
            raise AnvikshikiDomainError(f"Source {source_id} not found.", status_code=404)

        # 2. Store original immutably
        metadata = await self.storage.store_original(content, filename)

        # 3. Check for duplicates
        doc_result = await self.session.execute(
            select(DocumentModel).where(
                DocumentModel.source_id == source_id,
                DocumentModel.checksum_sha256 == metadata.checksum_sha256
            )
        )
        if doc_result.scalars().first():
            raise AnvikshikiDomainError(f"Document with checksum {metadata.checksum_sha256} already ingested.", status_code=409)

        # 4. Route Parser
        if metadata.mime_type in ["text/plain", "text/markdown"]:
            parsed_data = TextDocumentParser.parse_text(content)
            total_pages = 1
        elif metadata.mime_type == "application/pdf":
            parsed_data = PdfDocumentParser.parse_pdf(content)
            total_pages = max([p["page_number"] for p in parsed_data], default=1) if parsed_data else 1
        else:
            raise AnvikshikiDomainError(f"Unsupported MIME type: {metadata.mime_type}", status_code=415)

        # 5. Save Document Record
        new_doc = DocumentModel(
            source_id=source_id,
            checksum_sha256=metadata.checksum_sha256,
            mime_type=metadata.mime_type,
            total_pages=total_pages
        )
        self.session.add(new_doc)
        await self.session.flush()

        # 6. Save Passages
        passage_models = []
        for p_data in parsed_data:
            uncertainty = p_data.get("extraction_uncertainty", False)
            passage = PassageModel(
                document_id=new_doc.id,
                content=p_data["content"],
                page_number=p_data["page_number"],
                ocr_confidence=0.0 if uncertainty else 1.0,
                extraction_uncertainty=uncertainty,
                language=p_data.get("language", "en")
            )
            passage_models.append(passage)
            self.session.add(passage)

        await self.session.commit()
        return new_doc, passage_models