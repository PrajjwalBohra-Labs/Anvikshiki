from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import AuthenticatedPrincipal, get_current_user
from backend.app.application.use_cases.citation_service import CitationService
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.database.session import get_db
from backend.app.infrastructure.rag.lexical_retriever import LexicalRetriever
from backend.app.infrastructure.rag.reranker import AdvancedRetriever

router = APIRouter(prefix="/search", tags=["Search & RAG"])


class SearchResultItem(BaseModel):
    passage_id: str
    document_id: str | None = None
    document_version_id: str | None = None
    page_id: str | None = None
    source_id: str
    source_title: str
    content: str
    page_number: int | None
    extraction_method: str | None = None
    retrieval_method: str = "hybrid"
    relevance_score: float
    lexical_score: float | None = None
    semantic_score: float | None = None
    hybrid_score: float | None = None
    rerank_score: float | None = None
    citation_string: str
    model_config = ConfigDict(from_attributes=True)


class SearchResponse(BaseModel):
    query: str
    total_results: int
    results: list[SearchResultItem]
    retrieval_status: str = "complete"
    retrieval_warnings: list[str] = []


@router.get("/", response_model=SearchResponse)
async def search_passages(
    query: str = Query(..., min_length=1, max_length=1000),
    source_type: SourceType | None = None,
    source_id: str | None = None,
    document_id: str | None = None,
    document_version_id: str | None = None,
    retrieval: Literal["hybrid", "lexical", "semantic"] = Query("hybrid"),
    top_k: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: AuthenticatedPrincipal | None = Depends(get_current_user),  # noqa: B008
):
    """Search the corpus, preserving the existing hybrid default.

    ``retrieval=lexical`` exposes the Step 11 PostgreSQL lexical branch;
    existing frontend consumers continue using the hybrid default.
    """
    # Test-profile compatibility remains isolated to get_current_user;
    # deployed profiles fail closed before any corpus access occurs.
    del current_user
    if not query.strip():
        raise HTTPException(status_code=422, detail="Search query cannot be empty.")

    retrieval_status = "complete"
    retrieval_warnings: list[str] = []
    if retrieval == "lexical":
        retriever = LexicalRetriever(db)
        scored_passages = await retriever.search(
            query=query,
            source_type=source_type,
            limit=top_k,
            source_id=source_id,
            document_id=document_id,
            document_version_id=document_version_id,
        )
    elif retrieval == "semantic":
        retriever = AdvancedRetriever(db)
        outcome = await retriever.semantic_retrieve(
            query=query,
            source_type=source_type,
            top_k=top_k,
            source_id=source_id,
            document_id=document_id,
            document_version_id=document_version_id,
        )
        scored_passages = outcome.results
        retrieval_status = outcome.status
        retrieval_warnings = outcome.warnings
    else:
        retriever = AdvancedRetriever(db)
        outcome = await retriever.retrieve_and_rerank_with_metadata(
            query=query,
            source_type=source_type,
            top_k=top_k,
            source_id=source_id,
            document_id=document_id,
            document_version_id=document_version_id,
        )
        scored_passages = outcome.results
        retrieval_status = outcome.status
        retrieval_warnings = outcome.warnings
    citation_service = CitationService(db)

    citations = await citation_service.generate_citations(
        item.passage.id for item in scored_passages
    )

    results = []
    for item in scored_passages:
        passage = item.passage
        source = passage.document.source
        citation = citations.get(passage.id)
        if citation is None:
            raise HTTPException(status_code=404, detail="Search result citation unavailable.")

        results.append(
            SearchResultItem(
                passage_id=passage.id,
                document_id=passage.document_id,
                document_version_id=passage.document_version_id,
                page_id=passage.page_id,
                source_id=source.id,
                source_title=source.title,
                content=passage.content,
                page_number=passage.page_number,
                extraction_method=passage.extraction_method,
                retrieval_method=retrieval,
                relevance_score=item.score,
                lexical_score=item.lexical_score,
                semantic_score=item.semantic_score,
                hybrid_score=item.hybrid_score,
                rerank_score=item.rerank_score,
                citation_string=citation.citation_string,
            )
        )

    return SearchResponse(
        query=query,
        total_results=len(results),
        results=results,
        retrieval_status=retrieval_status,
        retrieval_warnings=retrieval_warnings,
    )
