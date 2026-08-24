from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from backend.app.infrastructure.database.session import get_db
from backend.app.infrastructure.rag.reranker import AdvancedRetriever
from backend.app.application.use_cases.citation_service import CitationService
from backend.app.domain.models.enums import SourceType

router = APIRouter(prefix="/search", tags=["Search & RAG"])

class SearchResultItem(BaseModel):
    passage_id: str
    source_id: str
    source_title: str
    content: str
    page_number: Optional[int]
    relevance_score: float
    citation_string: str
    model_config = ConfigDict(from_attributes=True)

class SearchResponse(BaseModel):
    query: str
    total_results: int
    results: List[SearchResultItem]

@router.get("/", response_model=SearchResponse)
async def search_passages(
    query: str = Query(..., min_length=2),
    source_type: Optional[SourceType] = None,
    top_k: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db)
):
    """Executes hybrid retrieval (Lexical + Semantic via RRF) and cross-encoder reranking, returning canonical citations."""
    retriever = AdvancedRetriever(db)
    citation_service = CitationService(db)
    
    scored_passages = await retriever.retrieve_and_rerank(
        query=query,
        source_type=source_type,
        top_k=top_k
    )
    
    results = []
    for item in scored_passages:
        passage = item.passage
        source = passage.document.source
        citation = await citation_service.generate_citation(passage.id)
        
        results.append(SearchResultItem(
            passage_id=passage.id,
            source_id=source.id,
            source_title=source.title,
            content=passage.content,
            page_number=passage.page_number,
            relevance_score=item.score,
            citation_string=citation.citation_string
        ))
        
    return SearchResponse(
        query=query,
        total_results=len(results),
        results=results
    )