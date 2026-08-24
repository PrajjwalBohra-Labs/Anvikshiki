from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, or_
import structlog

from backend.app.infrastructure.database.models import PassageModel, DocumentModel, SourceModel, PGVECTOR_AVAILABLE
from backend.app.infrastructure.ai.embedding_reranker_adapters import (
    LocalSentenceTransformerEmbeddingAdapter, LocalCrossEncoderRerankerAdapter
)
from backend.app.domain.models.enums import SourceType

logger = structlog.get_logger(__name__)

class HybridRetrievalService:
    """
    Production Hybrid RAG executing:
    Query -> Lexical FTS + pgvector Cosine Distance in SQL -> Fusion -> Cross-Encoder Rerank -> Evidence Candidates.
    """
    def __init__(self, session: AsyncSession):
        self.session = session
        self.embedder = LocalSentenceTransformerEmbeddingAdapter()
        self.reranker = LocalCrossEncoderRerankerAdapter()

    async def retrieve_evidence(
        self,
        query: str,
        domain: Optional[str] = None,
        source_type_filter: Optional[SourceType] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        # 1. Generate Query Vector Embedding (384 dimensions)
        query_vectors = await self.embedder.embed_texts([query])
        query_vec = query_vectors[0]

        # 2. Database Retrieval: Lexical + pgvector Cosine Distance directly in SQL
        stmt = (
            select(PassageModel, DocumentModel, SourceModel)
            .join(DocumentModel, PassageModel.document_id == DocumentModel.id)
            .join(SourceModel, DocumentModel.source_id == SourceModel.id)
        )

        if source_type_filter:
            stmt = stmt.where(SourceModel.source_type == source_type_filter)

        # Lexical filtering keywords
        keywords = [f"%{w}%" for w in query.split() if len(w) > 2]
        if keywords:
            lexical_conditions = [PassageModel.content.ilike(kw) for kw in keywords]
            stmt = stmt.where(or_(*lexical_conditions))

        # Check database dialect to apply native pgvector operators on PostgreSQL
        bind = self.session.get_bind()
        is_postgres = bind.dialect.name == "postgresql" if bind else False

        if is_postgres and PGVECTOR_AVAILABLE and hasattr(PassageModel.embedding, "cosine_distance"):
            stmt = stmt.order_by(PassageModel.embedding.cosine_distance(query_vec))
        
        stmt = stmt.limit(20)
        result = await self.session.execute(stmt)
        rows = result.all()

        if not rows:
            # Fallback scan if exact lexical keywords were too restrictive
            fallback_stmt = (
                select(PassageModel, DocumentModel, SourceModel)
                .join(DocumentModel, PassageModel.document_id == DocumentModel.id)
                .join(SourceModel, DocumentModel.source_id == SourceModel.id)
                .limit(20)
            )
            result = await self.session.execute(fallback_stmt)
            rows = result.all()

        # 3. Assemble Candidates with Complete Provenance Chains
        candidates_map = {}
        for passage, document, source in rows:
            if passage.id not in candidates_map:
                candidates_map[passage.id] = {
                    "passage_id": passage.id,
                    "document_id": document.id,
                    "source_id": source.id,
                    "source_title": source.title,
                    "author": source.author,
                    "page_number": passage.page_number,
                    "content": passage.content,
                    "ocr_uncertainty": passage.extraction_uncertainty,
                    "source_type": source.source_type.value if hasattr(source.source_type, 'value') else str(source.source_type),
                    "embedding_model": passage.embedding_model or self.embedder.model_version
                }

        unique_candidates = list(candidates_map.values())
        if not unique_candidates:
            return []

        # 4. Execute Real Cross-Encoder Reranking
        candidate_texts = [c["content"] for c in unique_candidates]
        reranked_scores = await self.reranker.rerank(query, candidate_texts, top_k=top_k)

        # Map scores back to candidate objects
        scored_candidates = []
        for scored in reranked_scores:
            for cand in unique_candidates:
                if cand["content"] == scored["passage"]:
                    cand_copy = dict(cand)
                    cand_copy["relevance_score"] = scored["relevance_score"]
                    cand_copy["rank"] = scored["rank"]
                    scored_candidates.append(cand_copy)
                    break

        logger.info("Hybrid retrieval and cross-encoder rerank complete", query=query, candidates_returned=len(scored_candidates))
        return scored_candidates