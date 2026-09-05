
from backend.app.core.config import RuntimeProfile, settings
from backend.app.infrastructure.ai.embedding_reranker_adapters import (
    LocalCrossEncoderRerankerAdapter,
)
from backend.app.infrastructure.rag.retriever import (
    HybridRetriever,
    RetrievalOutcome,
    ScoredPassage,
)


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
        self, query: str, passages: list[ScoredPassage], top_k: int = 5
    ) -> list[ScoredPassage]:
        if not passages:
            return []

        if settings.RUNTIME_PROFILE == RuntimeProfile.TEST:
            reranked = [
                ScoredPassage(
                    passage=item.passage,
                    score=self._compute_deterministic_rerank_score(query, item.passage.content),
                    retrieval_method=item.retrieval_method,
                    lexical_score=item.lexical_score,
                    semantic_score=item.semantic_score,
                    lexical_rank=item.lexical_rank,
                    semantic_rank=item.semantic_rank,
                    normalized_lexical_score=item.normalized_lexical_score,
                    normalized_semantic_score=item.normalized_semantic_score,
                    hybrid_score=item.hybrid_score,
                    rerank_score=self._compute_deterministic_rerank_score(
                        query, item.passage.content
                    ),
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
                    retrieval_method=item.retrieval_method,
                    lexical_score=item.lexical_score,
                    semantic_score=item.semantic_score,
                    lexical_rank=item.lexical_rank,
                    semantic_rank=item.semantic_rank,
                    normalized_lexical_score=item.normalized_lexical_score,
                    normalized_semantic_score=item.normalized_semantic_score,
                    hybrid_score=item.hybrid_score,
                    rerank_score=float(score_by_content[item.passage.content]),
                )
                for item in passages
            ]

        reranked.sort(key=lambda x: (-x.score, x.passage.id))
        return reranked[:top_k]


class AdvancedRetriever(HybridRetriever):
    def __init__(
        self,
        session,
        embedding_client=None,
        reranker_client: LocalRerankerClient | None = None,
    ):
        super().__init__(session, embedding_client)
        self.reranker = reranker_client or LocalRerankerClient()

    async def retrieve_and_rerank(
        self,
        query: str,
        source_type=None,
        language: str | None = None,
        top_k: int = 5,
<<<<<<< HEAD
        source_id: Optional[str] = None,
        document_id: Optional[str] = None,
        document_version_id: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> List[ScoredPassage]:
=======
        source_id: str | None = None,
        document_id: str | None = None,
        document_version_id: str | None = None,
    ) -> list[ScoredPassage]:
>>>>>>> origin/main
        outcome = await self.retrieve_and_rerank_with_metadata(
            query=query,
            source_type=source_type,
            language=language,
            top_k=top_k,
            source_id=source_id,
            document_id=document_id,
            document_version_id=document_version_id,
            owner_id=owner_id,
        )
        return outcome.results

    async def retrieve_and_rerank_with_metadata(
        self,
        query: str,
        source_type=None,
        language: str | None = None,
        top_k: int = 5,
<<<<<<< HEAD
        source_id: Optional[str] = None,
        document_id: Optional[str] = None,
        document_version_id: Optional[str] = None,
        owner_id: Optional[str] = None,
=======
        source_id: str | None = None,
        document_id: str | None = None,
        document_version_id: str | None = None,
>>>>>>> origin/main
    ) -> RetrievalOutcome:
        outcome = await self.hybrid_retrieve_with_metadata(
            query=query,
            source_type=source_type,
            language=language,
            top_k=top_k * settings.RERANKER_CANDIDATE_MULTIPLIER,
            source_id=source_id,
            document_id=document_id,
            document_version_id=document_version_id,
            owner_id=owner_id,
        )
        if not outcome.results:
            return outcome
        if not settings.RERANKER_ENABLED:
            outcome.results = outcome.results[:top_k]
            return outcome
        try:
            reranked = await self.reranker.rerank(
                query=query, passages=outcome.results, top_k=top_k
            )
        except Exception as exc:
            # Reranking is derived refinement. Preserve the valid fused
            # candidates and report degradation instead of fabricating scores.
            outcome.results = outcome.results[:top_k]
            outcome.status = "degraded"
            outcome.warnings.append(self._warning("reranker", exc))
            return outcome
        outcome.results = reranked
        return outcome
