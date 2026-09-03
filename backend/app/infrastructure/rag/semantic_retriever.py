import math

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from backend.app.core.config import settings
from backend.app.domain.models.enums import EmbeddingIndexStatus, SourceType
from backend.app.infrastructure.database.models import (
    PGVECTOR_AVAILABLE,
    DocumentModel,
    PassageModel,
    SourceModel,
    Vector,
)
from backend.app.infrastructure.rag.lexical_retriever import ScoredPassage


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
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
        query_vector: list[float],
        source_type: SourceType | None = None,
        limit: int = 10,
        document_id: str | None = None,
        document_version_id: str | None = None,
        source_id: str | None = None,
    ) -> list[ScoredPassage]:
        """
        Performs semantic vector search across passage embeddings.
        Includes provenance-aware eager loading and metadata filtering.
        """
        if not query_vector:
            return []

        bind = self.session.get_bind()
        is_postgres = bind.dialect.name == "postgresql" if bind else False

        if is_postgres and (
            not PGVECTOR_AVAILABLE
            or Vector is None
            or not isinstance(PassageModel.__table__.c.embedding.type, Vector)
        ):
            raise RuntimeError(
                "PostgreSQL semantic retrieval requires a pgvector Vector column."
            )
        if is_postgres and len(query_vector) != settings.EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"Query embedding dimension {len(query_vector)} does not match "
                f"the configured {settings.EMBEDDING_DIMENSIONS}-dimensional index."
            )

        stmt = select(PassageModel).join(PassageModel.document).join(DocumentModel.source)
        
        # Apply Metadata Filters
        if source_type:
            stmt = stmt.where(SourceModel.source_type == source_type)
        if document_id:
            stmt = stmt.where(PassageModel.document_id == document_id)
        if document_version_id:
            stmt = stmt.where(PassageModel.document_version_id == document_version_id)
        if source_id:
            stmt = stmt.where(DocumentModel.source_id == source_id)
            
        # Eager load provenance to prevent N+1 serialization delays
        stmt = stmt.options(selectinload(PassageModel.document).selectinload(DocumentModel.source))
        
        if is_postgres:
            distance = PassageModel.embedding.cosine_distance(query_vector).label("cosine_distance")
            stmt = (
                select(PassageModel, distance)
                .join(PassageModel.document)
                .join(DocumentModel.source)
                .where(PassageModel.embedding.is_not(None))
                .where(PassageModel.embedding_status == EmbeddingIndexStatus.INDEXED)
                .options(selectinload(PassageModel.document).selectinload(DocumentModel.source))
                .order_by(
                    distance,
                    PassageModel.passage_order.asc().nulls_last(),
                    PassageModel.id.asc(),
                )
                .limit(limit)
            )
            if source_type:
                stmt = stmt.where(SourceModel.source_type == source_type)
            if document_id:
                stmt = stmt.where(PassageModel.document_id == document_id)
            if document_version_id:
                stmt = stmt.where(PassageModel.document_version_id == document_version_id)
            if source_id:
                stmt = stmt.where(DocumentModel.source_id == source_id)
            result = await self.session.execute(stmt)
            return [
                ScoredPassage(
                    passage=passage,
                    score=1.0 - float(distance_value),
                    retrieval_method="semantic",
                    semantic_score=1.0 - float(distance_value),
                )
                for passage, distance_value in result.all()
            ]

        # Isolated SQLite tests retain their explicit Python scoring path.
        result = await self.session.execute(stmt)
        passages = result.scalars().all()
        
        scored_results = []
        for passage in passages:
            if passage.embedding:
                # Cosine similarity ranges from -1.0 (opposite) to 1.0 (exact match)
                score = cosine_similarity(query_vector, passage.embedding)
                scored_results.append(
                    ScoredPassage(
                        passage=passage,
                        score=score,
                        retrieval_method="semantic",
                        semantic_score=score,
                    )
                )
                
        # Sort descending (highest similarity first)
        scored_results.sort(key=lambda x: (-x.score, x.passage.id))
        return scored_results[:limit]
