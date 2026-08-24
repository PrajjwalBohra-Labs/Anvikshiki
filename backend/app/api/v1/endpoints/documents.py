from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from backend.app.infrastructure.database.session import get_db
from backend.app.infrastructure.storage.local_storage import LocalStorageService
from backend.app.application.use_cases.ingestion import DocumentIngestionService
from backend.app.infrastructure.database.models import DocumentModel, PassageModel, SourceModel
from backend.app.core.errors import AnvikshikiDomainError

router = APIRouter(prefix="/documents", tags=["Documents"])

class PassageResponse(BaseModel):
    id: str
    page_number: Optional[int]
    content: str
    ocr_confidence: float
    extraction_uncertainty: bool
    language: str
    model_config = ConfigDict(from_attributes=True)

class DocumentUploadResponse(BaseModel):
    document_id: str
    checksum_sha256: str
    mime_type: str
    total_pages: Optional[int]
    passages_count: int

@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    source_id: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    content = await file.read()
    storage = LocalStorageService()
    ingestion_service = DocumentIngestionService(db, storage)
    
    doc, passages = await ingestion_service.ingest_file(
        source_id=source_id,
        filename=file.filename or "document.txt",
        content=content
    )
    
    return DocumentUploadResponse(
        document_id=doc.id,
        checksum_sha256=doc.checksum_sha256,
        mime_type=doc.mime_type,
        total_pages=doc.total_pages,
        passages_count=len(passages)
    )

@router.get("/{document_id}/passages", response_model=List[PassageResponse])
async def get_document_passages(document_id: str, db: AsyncSession = Depends(get_db)):
    doc_result = await db.execute(select(DocumentModel).where(DocumentModel.id == document_id))
    doc = doc_result.scalars().first()
    if not doc:
        raise AnvikshikiDomainError(f"Document {document_id} not found.", status_code=404)
        
    passages_result = await db.execute(select(PassageModel).where(PassageModel.document_id == document_id))
    return passages_result.scalars().all()