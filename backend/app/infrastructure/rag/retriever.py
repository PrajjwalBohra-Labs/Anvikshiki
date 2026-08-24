from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.infrastructure.rag.lexical_retriever import LexicalRetriever, ScoredPassage
from backend.app.infrastructure.rag.semantic_retriever import SemanticRetriever
from backend.app.infrastructure.llm.embedding_client import LocalEmbeddingClient
from backend.app.domain.models.enums import SourceType

class HybridRetriever:
    def __init__(self, session: AsyncSession, embedding_client: Optional[LocalEmbeddingClient] = None):
        self.session = session
        self.lexical = LexicalRetriever(session)
        self.semantic = SemanticRetriever(session)
        self.embed_client = embedding_client or LocalEmbeddingClient()

    async def hybrid_retrieve(
        self,
        query: str,
        source_type: Optional[SourceType] = None,
        language: Optional[str] = None,
        top_k: int = 5,
        rrf_k: int = 60
    ) -> List[ScoredPassage]:
        """
        Executes hybrid retrieval combining Lexical and Semantic searches,
        merged via Reciprocal Rank Fusion (RRF).
        """
        # 1. Execute Lexical Retrieval
        lexical_results = await self.lexical.search(
            query=query,
            source_type=source_type,
            language=language,
            limit=top_k * 3
        )

        # 2. Execute Semantic Retrieval
        query_vector = await self.embed_client.get_embedding(query)
        semantic_results = await self.semantic.search(
            query_vector=query_vector,
            source_type=source_type,
            limit=top_k * 3
        )

        # 3. Reciprocal Rank Fusion (RRF) Calculation
        # RRF score = sum(1.0 / (k + rank)) across all lists where the item appears
        passage_map: Dict[str, Any] = {}
        rrf_scores: Dict[str, float] = {}

        # Process Lexical Ranks (1-indexed)
        for rank, item in enumerate(lexical_results, start=1):
            p_id = item.passage.id
            passage_map[p_id] = item.passage
            rrf_scores[p_id] = rrf_scores.get(p_id, 0.0) + (1.0 / (rrf_k + rank))

        # Process Semantic Ranks (1-indexed)
        for rank, item in enumerate(semantic_results, start=1):
            p_id = item.passage.id
            passage_map[p_id] = item.passage
            rrf_scores[p_id] = rrf_scores.get(p_id, 0.0) + (1.0 / (rrf_k + rank))

        # 4. Construct final sorted list based on RRF aggregate score
        fused_results = []
        for p_id, score in rrf_scores.items():
            fused_results.append(ScoredPassage(passage=passage_map[p_id], score=score))

        # Sort descending by RRF fusion score
        fused_results.sort(key=lambda x: x.score, reverse=True)
        return fused_results[:top_k]