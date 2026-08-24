import math
import re
from typing import List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.infrastructure.database.models import PassageModel
from backend.app.infrastructure.llm.embedding_client import OllamaEmbeddingClient

class ScoredPassage:
    def __init__(self, passage: PassageModel, score: float, rank_type: str):
        self.passage = passage
        self.score = score
        self.rank_type = rank_type

class HybridRetriever:
    def __init__(
        self,
        session: AsyncSession,
        embedding_client: OllamaEmbeddingClient | None = None,
        lexical_weight: float = 0.6,
        vector_weight: float = 0.4,
    ):
        self.session = session
        self.embedding_client = embedding_client or OllamaEmbeddingClient()
        self.lexical_weight = lexical_weight
        self.vector_weight = vector_weight

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return [w.lower() for w in re.findall(r"\w+", text) if len(w) > 2]

    @staticmethod
    def cosine_similarity(v1: List[float], v2: List[float]) -> float:
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2))
        n1 = math.sqrt(sum(a * a for a in v1))
        n2 = math.sqrt(sum(b * b for b in v2))
        if n1 == 0 or n2 == 0:
            return 0.0
        return dot / (n1 * n2)

    async def lexical_search(self, query: str, limit: int = 10) -> List[Tuple[PassageModel, float]]:
        keywords = self._tokenize(query)
        if not keywords:
            return []

        result = await self.session.execute(select(PassageModel))
        all_passages = list(result.scalars().all())

        scored = []
        for p in all_passages:
            tokens = self._tokenize(p.content)
            if not tokens:
                continue
            # Term Frequency match score
            score = sum(tokens.count(kw) for kw in keywords)
            if score > 0:
                scored.append((p, float(score)))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    async def hybrid_retrieve(
        self,
        query: str,
        top_k: int = 5,
        rrf_k: int = 60
    ) -> List[ScoredPassage]:
        # 1. Lexical retrieval
        lexical_scored = await self.lexical_search(query, limit=top_k * 3)

        # 2. Vector retrieval
        query_vec = await self.embedding_client.get_embedding(query)
        result = await self.session.execute(select(PassageModel))
        all_passages = list(result.scalars().all())

        vector_scored = []
        for p in all_passages:
            p_vec = await self.embedding_client.get_embedding(p.content)
            sim = self.cosine_similarity(query_vec, p_vec)
            vector_scored.append((p, sim))

        vector_scored.sort(key=lambda x: x[1], reverse=True)

        # 3. Weighted Reciprocal Rank Fusion
        rrf_scores: Dict[str, float] = {}
        passage_map: Dict[str, PassageModel] = {}

        for rank, (p, _) in enumerate(lexical_scored):
            rrf_scores[p.id] = rrf_scores.get(p.id, 0.0) + (self.lexical_weight / (rrf_k + rank + 1))
            passage_map[p.id] = p

        for rank, (p, _) in enumerate(vector_scored[: top_k * 3]):
            rrf_scores[p.id] = rrf_scores.get(p.id, 0.0) + (self.vector_weight / (rrf_k + rank + 1))
            passage_map[p.id] = p

        sorted_rrf = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        final_results = []
        for p_id, score in sorted_rrf[:top_k]:
            final_results.append(ScoredPassage(passage=passage_map[p_id], score=score, rank_type="HYBRID_RRF"))

        return final_results