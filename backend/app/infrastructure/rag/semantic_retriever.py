import math
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from backend.app.infrastructure.database.models import PassageModel, DocumentModel, SourceModel
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.rag.lexical_retriever import ScoredPassage
from backend.app.core.config import settings, RuntimeProfile

def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculates cosine similarity between two dense vectors."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)

class SemanticRetriever:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(
        self,
        query_vector: List[float],
        source_type: Optional[SourceType] = None,
        limit: int = 10
    ) -> List[ScoredPassage]:
        """
        Performs semantic vector search across passage embeddings.
        Includes provenance-aware eager loading and metadata filtering.
        """
        if not query_vector:
            return []

        stmt = select(PassageModel).join(PassageModel.document).join(DocumentModel.source)
        
        # Apply Metadata Filters
        if source_type:
            stmt = stmt.where(SourceModel.source_type == source_type)
            
        # Eager load provenance to prevent N+1 serialization delays
        stmt = stmt.options(selectinload(PassageModel.document).selectinload(DocumentModel.source))
        
        # Note: In SQLite TEST profile, we retrieve candidates and score in Python.
        # In a Postgres/pgvector deployment, we would offload this:
        # stmt = stmt.order_by(PassageModel.embedding.cosine_distance(query_vector)).limit(limit)
        
        result = await self.session.execute(stmt)
        passages = result.scalars().all()
        
        scored_results = []
        for passage in passages:
            if passage.embedding:
                # Cosine similarity ranges from -1.0 (opposite) to 1.0 (exact match)
                score = cosine_similarity(query_vector, passage.embedding)
                scored_results.append(ScoredPassage(passage=passage, score=score))
                
        # Sort descending (highest similarity first)
        scored_results.sort(key=lambda x: x.score, reverse=True)
        return scored_results[:limit]