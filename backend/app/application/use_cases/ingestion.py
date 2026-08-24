from typing import List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.infrastructure.database.models import DocumentModel, PassageModel, SourceModel
from backend.app.infrastructure.storage.local_storage import LocalStorageService
from backend.app.domain.models.enums import SourceType
from backend.app.core.errors import AnvikshikiDomainError
from backend.app.infrastructure.document_parsers.pdf_parser import PdfDocumentParser
from backend.app.infrastructure.ocr.tesseract_service import TesseractOcrService

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
        self.ocr_service = TesseractOcrService()

    async def ingest_file(self, source_id: str, filename: str, content: bytes) -> Tuple[DocumentModel, List[PassageModel]]:
        source_result = await self.session.execute(select(SourceModel).where(SourceModel.id == source_id))
        source = source_result.scalars().first()
        if not source:
            raise AnvikshikiDomainError(f"Source {source_id} not found.", status_code=404)

        metadata = await self.storage.store_original(content, filename)

        doc_result = await self.session.execute(
            select(DocumentModel).where(
                DocumentModel.source_id == source_id,
                DocumentModel.checksum_sha256 == metadata.checksum_sha256
            )
        )
        if doc_result.scalars().first():
            raise AnvikshikiDomainError(f"Document with checksum {metadata.checksum_sha256} already ingested.", status_code=409)

        if metadata.mime_type in ["text/plain", "text/markdown"]:
            parsed_data = TextDocumentParser.parse_text(content)
            total_pages = 1
        elif metadata.mime_type == "application/pdf":
            parsed_data = PdfDocumentParser.parse_pdf(content)
            total_pages = max([p["page_number"] for p in parsed_data], default=1) if parsed_data else 1
            
            # --- OCR Pipeline Integration ---
            ocr_available = self.ocr_service.is_available()
            for p_data in parsed_data:
                if p_data.get("extraction_uncertainty") and ocr_available:
                    ocr_result = self.ocr_service.process_pdf_page(content, p_data["page_number"])
                    if ocr_result["success"] and ocr_result["content"]:
                        p_data["content"] = ocr_result["content"]
                        p_data["ocr_confidence"] = ocr_result["confidence"]
                        # Strict Threshold: If confidence is below 60%, maintain uncertainty flag
                        p_data["extraction_uncertainty"] = ocr_result["confidence"] < 0.60
        else:
            raise AnvikshikiDomainError(f"Unsupported MIME type: {metadata.mime_type}", status_code=415)

        new_doc = DocumentModel(
            source_id=source_id,
            checksum_sha256=metadata.checksum_sha256,
            mime_type=metadata.mime_type,
            total_pages=total_pages
        )
        self.session.add(new_doc)
        await self.session.flush()

        passage_models = []
        for p_data in parsed_data:
            uncertainty = p_data.get("extraction_uncertainty", False)
            passage = PassageModel(
                document_id=new_doc.id,
                content=p_data["content"],
                page_number=p_data["page_number"],
                ocr_confidence=p_data.get("ocr_confidence", 0.0 if uncertainty else 1.0),
                extraction_uncertainty=uncertainty,
                language=p_data.get("language", "en")
            )
            passage_models.append(passage)
            self.session.add(passage)

        await self.session.commit()
        return new_doc, passage_models