from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import AuthenticatedPrincipal, get_current_user
from backend.app.api.v1.schemas.dtos import (
    DocumentResponseDTO,
    SourceResponseDTO,
    WebAcquisitionRequestDTO,
    WebAcquisitionResponseDTO,
    WebSearchRequestDTO,
    WebSearchResponseDTO,
    WebSearchResultDTO,
)
from backend.app.application.use_cases.document_service import DocumentService
from backend.app.application.use_cases.web_acquisition import WebAcquisitionService
from backend.app.application.use_cases.web_search import WebSearchService
from backend.app.core.config import settings
from backend.app.infrastructure.database.session import get_db
from backend.app.infrastructure.storage.local_storage import LocalStorageService

router = APIRouter(prefix="/web", tags=["Web Acquisition"])


@router.post("/search", response_model=WebSearchResponseDTO)
async def search_web_sources(
    payload: WebSearchRequestDTO,
    current_user: AuthenticatedPrincipal | None = Depends(get_current_user),
):
    if not settings.ENABLE_WEB_RETRIEVAL:
        raise HTTPException(status_code=503, detail="Web retrieval is disabled.")
    results = await WebSearchService().search(payload.query, payload.max_results)
    return WebSearchResponseDTO(
        query=payload.query,
        results=[WebSearchResultDTO(**result.__dict__) for result in results],
    )


@router.post("/acquire", response_model=WebAcquisitionResponseDTO, status_code=status.HTTP_201_CREATED)
async def acquire_web_source(
    payload: WebAcquisitionRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedPrincipal | None = Depends(get_current_user),
):
    if not settings.ENABLE_WEB_RETRIEVAL:
        raise HTTPException(status_code=503, detail="Web retrieval is disabled.")

    source, document, _ = await WebAcquisitionService(db, LocalStorageService()).acquire_url(
        url=payload.url,
        source_title=payload.source_title,
    )
    document_payload = await DocumentService(db).describe_document(document)
    return WebAcquisitionResponseDTO(
        source=SourceResponseDTO(
            id=source.id,
            title=source.title,
            author=source.author,
            historical_era=source.historical_era,
            original_language=source.original_language,
            source_type=source.source_type.value,
            reference_url=source.reference_url,
        ),
        document=DocumentResponseDTO(**document_payload),
    )
