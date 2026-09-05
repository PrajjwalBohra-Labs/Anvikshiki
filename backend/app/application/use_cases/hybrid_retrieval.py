from typing import Any

import structlog
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.app.domain.models.enums import EmbeddingIndexStatus, SourceType
from backend.app.infrastructure.ai.embedding_reranker_adapters import (
    LocalCrossEncoderRerankerAdapter,
    LocalSentenceTransformerEmbeddingAdapter,
)
from backend.app.infrastructure.database.models import (
    PGVECTOR_AVAILABLE,
    DocumentModel,
    PassageModel,
    SourceModel,
    Vector,
)

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
<<<<<<< HEAD
        domain: Optional[str] = None,
        source_type_filter: Optional[SourceType] = None,
        top_k: int = 5,
        owner_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
=======
        domain: str | None = None,
        source_type_filter: SourceType | None = None,
        source_id_filter: str | None = None,
        top_k: int = 5
    ) -> list[dict[str, Any]]:
>>>>>>> origin/main
        # 1. Generate Query Vector Embedding (384 dimensions)
        query_vectors = await self.embedder.embed_texts([query])
        query_vec = query_vectors[0]

        # 2. Database Retrieval: execute lexical and vector channels separately.
        base_stmt = (
            select(PassageModel, DocumentModel, SourceModel)
            .join(DocumentModel, PassageModel.document_id == DocumentModel.id)
            .join(SourceModel, DocumentModel.source_id == SourceModel.id)
        )

        if source_type_filter:
            base_stmt = base_stmt.where(SourceModel.source_type == source_type_filter)
<<<<<<< HEAD
        if owner_id:
            # Legacy/canonical sources without an owner remain shared corpus
            # material.  Private sources are still restricted to their owner.
            base_stmt = base_stmt.where(
                or_(SourceModel.user_id == owner_id, SourceModel.user_id.is_(None))
            )
=======
        if source_id_filter:
            base_stmt = base_stmt.where(SourceModel.id == source_id_filter)
>>>>>>> origin/main

        # Lexical retrieval channel
        keywords = [f"%{w}%" for w in query.split() if len(w) > 2]
        if keywords:
            lexical_conditions = [PassageModel.content.ilike(kw) for kw in keywords]
            lexical_stmt = base_stmt.where(or_(*lexical_conditions))
        else:
            lexical_stmt = base_stmt

        # Check database dialect to apply native pgvector operators on PostgreSQL
        bind = self.session.get_bind()
        is_postgres = bind.dialect.name == "postgresql" if bind else False

        lexical_stmt = lexical_stmt.limit(20)
        lexical_result = await self.session.execute(lexical_stmt)
        lexical_rows = lexical_result.all()

        vector_rows = []
        if is_postgres:
            if not PGVECTOR_AVAILABLE or Vector is None or not isinstance(PassageModel.__table__.c.embedding.type, Vector):
                raise RuntimeError(
                    "PostgreSQL retrieval requires the pgvector package and a Vector column; "
                    "refusing to continue without database vector ranking."
                )
            distance = PassageModel.embedding.cosine_distance(query_vec).label("cosine_distance")
            # Rebuild the vector statement from the original joins so the
            # ORM entities remain available for provenance assembly.
            vector_stmt = (
                select(PassageModel, DocumentModel, SourceModel, distance)
                .join(DocumentModel, PassageModel.document_id == DocumentModel.id)
                .join(SourceModel, DocumentModel.source_id == SourceModel.id)
                .where(PassageModel.embedding.is_not(None))
                .where(PassageModel.embedding_status == EmbeddingIndexStatus.INDEXED)
                .order_by(distance)
                .limit(20)
            )
            if source_type_filter:
                vector_stmt = vector_stmt.where(SourceModel.source_type == source_type_filter)
<<<<<<< HEAD
            if owner_id:
                vector_stmt = vector_stmt.where(
                    or_(SourceModel.user_id == owner_id, SourceModel.user_id.is_(None))
                )
=======
            if source_id_filter:
                vector_stmt = vector_stmt.where(SourceModel.id == source_id_filter)
>>>>>>> origin/main
            vector_result = await self.session.execute(vector_stmt)
            vector_rows = vector_result.all()
        elif not lexical_rows:
            # This path is retained only for isolated SQLite tests. The
            # PostgreSQL path never scans without vector ordering.
            fallback_result = await self.session.execute(base_stmt.limit(20))
            lexical_rows = fallback_result.all()

        # Reciprocal-rank fusion keeps lexical and semantic evidence distinct
        # before the real cross-encoder reranker runs.
        ranked_rows = {}
        rrf_scores = {}
        channels = {}
        for rank, row in enumerate(lexical_rows, start=1):
            passage = row[0]
            ranked_rows[passage.id] = row[:3]
            rrf_scores[passage.id] = rrf_scores.get(passage.id, 0.0) + 1.0 / (60 + rank)
            channels.setdefault(passage.id, set()).add("lexical")
        for rank, row in enumerate(vector_rows, start=1):
            passage = row[0]
            ranked_rows[passage.id] = row[:3]
            rrf_scores[passage.id] = rrf_scores.get(passage.id, 0.0) + 1.0 / (60 + rank)
            channels.setdefault(passage.id, set()).add("vector")
        rows = [ranked_rows[passage_id] for passage_id in sorted(rrf_scores, key=rrf_scores.get, reverse=True)]

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
                    "source_reference_url": source.reference_url,
                    "citation_string": ", ".join(
                        part for part in (
                            source.title,
                            f"by {source.author}" if source.author else None,
                            f"(Retrieved from {source.reference_url})"
                            if source.source_type == SourceType.DISCOVERY_ONLY and source.reference_url
                            else None,
                            f"p. {passage.page_number}" if passage.page_number else None,
                        ) if part
                    ),
                    "embedding_model": passage.embedding_model or self.embedder.model_version,
                    "retrieval_channels": sorted(channels.get(passage.id, set()))
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
