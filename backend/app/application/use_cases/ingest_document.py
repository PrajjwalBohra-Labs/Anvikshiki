import hashlib
import shutil
from pathlib import Path
from typing import List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.config import settings
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.database.models import SourceModel, DocumentModel, PassageModel
from backend.app.infrastructure.database.repositories.source_repository import SourceRepository, PassageRepository
from backend.app.infrastructure.document_parsers.pdf_parser import PDFParser

class IngestionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.source_repo = SourceRepository(session)
        self.passage_repo = PassageRepository(session)

    @staticmethod
    def calculate_sha256(file_bytes: bytes) -> str:
        return hashlib.sha256(file_bytes).hexdigest()

    async def ingest_document(
        self,
        file_bytes: bytes,
        filename: str,
        title: str,
        source_type: SourceType,
        citation_string: str,
        author: str | None = None,
        translator: str | None = None
    ) -> Tuple[DocumentModel, List[PassageModel]]:
        checksum = self.calculate_sha256(file_bytes)

        # 1. Check for existing document by checksum
        existing_doc = await self.source_repo.get_by_checksum(checksum)
        if existing_doc:
            passages = await self.passage_repo.get_by_document(existing_doc.id)
            return existing_doc, passages

        # 2. Immutable storage
        storage_dir = Path(settings.STORAGE_LOCAL_ROOT)
        storage_dir.mkdir(parents=True, exist_ok=True)
        dest_path = storage_dir / f"{checksum}_{filename}"
        
        with open(dest_path, "wb") as f:
            f.write(file_bytes)

        # 3. Create Source Record
        source = SourceModel(
            title=title,
            author=author,
            translator=translator,
            source_type=source_type,
            citation_string=citation_string
        )
        await self.source_repo.create(source)

        # 4. Parse PDF Pages
        pages = PDFParser.extract_pages(str(dest_path))
        doc_record = DocumentModel(
            source_id=source.id,
            file_path=str(dest_path),
            checksum_sha256=checksum,
            mime_type="application/pdf",
            total_pages=len(pages),
            ocr_applied=False
        )
        self.session.add(doc_record)
        await self.session.flush()

        # 5. Segment into Passages with Page-level Provenance
        created_passages = []
        for p in pages:
            if not p.text and not p.is_uncertain:
                continue
            
            passage = PassageModel(
                document_id=doc_record.id,
                page_number=p.page_number,
                content=p.text if p.text else "[UNCERTAIN EXTRACTION - REQUIRES OCR]",
                source_type=source_type,
                ocr_confidence=0.5 if p.is_uncertain else 1.0,
                extraction_uncertainty=p.is_uncertain
            )
            await self.passage_repo.create(passage)
            created_passages.append(passage)

        await self.session.commit()
        return doc_record, created_passages