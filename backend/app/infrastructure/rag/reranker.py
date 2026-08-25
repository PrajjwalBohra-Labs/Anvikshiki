from typing import List, Optional

from backend.app.core.config import RuntimeProfile, settings
from backend.app.infrastructure.ai.embedding_reranker_adapters import (
    LocalCrossEncoderRerankerAdapter,
)
from backend.app.infrastructure.rag.retriever import HybridRetriever, ScoredPassage


class LocalRerankerClient:
    def __init__(self, model_name: str = settings.RERANKER_MODEL):
        self.model_name = model_name
        self.adapter = LocalCrossEncoderRerankerAdapter(model_name=model_name)

    def _compute_deterministic_rerank_score(self, query: str, content: str) -> float:
        q_terms = set(query.lower().split())
        c_terms = set(content.lower().split())
        if not q_terms:
            return 0.5
        overlap_ratio = len(q_terms.intersection(c_terms)) / len(q_terms)
        return round(0.2 + (overlap_ratio * 0.8), 4)

    async def rerank(
        self, query: str, passages: List[ScoredPassage], top_k: int = 5
    ) -> List[ScoredPassage]:
        if not passages:
            return []

        if settings.RUNTIME_PROFILE == RuntimeProfile.TEST:
            reranked = [
                ScoredPassage(
                    passage=item.passage,
                    score=self._compute_deterministic_rerank_score(query, item.passage.content),
                )
                for item in passages
            ]
        else:
            scores = await self.adapter.rerank(
                query, [item.passage.content for item in passages], top_k=len(passages)
            )
            score_by_content = {item["passage"]: item["relevance_score"] for item in scores}
            reranked = [
                ScoredPassage(
                    passage=item.passage,
                    score=float(score_by_content[item.passage.content]),
                )
                for item in passages
            ]

        reranked.sort(key=lambda x: x.score, reverse=True)
        return reranked[:top_k]


class AdvancedRetriever(HybridRetriever):
    def __init__(
        self,
        session,
        embedding_client=None,
        reranker_client: Optional[LocalRerankerClient] = None,
    ):
        super().__init__(session, embedding_client)
        self.reranker = reranker_client or LocalRerankerClient()

    async def retrieve_and_rerank(
        self,
        query: str,
        source_type=None,
        language: Optional[str] = None,
        top_k: int = 5,
    ) -> List[ScoredPassage]:
        candidates = await self.hybrid_retrieve(
            query=query,
            source_type=source_type,
            language=language,
            top_k=top_k * 2,
        )
        return await self.reranker.rerank(query=query, passages=candidates, top_k=top_k)
