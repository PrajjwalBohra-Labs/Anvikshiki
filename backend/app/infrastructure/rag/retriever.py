"""Independent lexical/vector retrieval and deterministic hybrid fusion.

Passage rows remain authoritative. The values carried by ``ScoredPassage``
are retrieval metadata only and are never used as documentary evidence.
"""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.llm.embedding_client import LocalEmbeddingClient
from backend.app.infrastructure.rag.lexical_retriever import (
    LexicalRetriever,
    ScoredPassage,
)
from backend.app.infrastructure.rag.semantic_retriever import SemanticRetriever


@dataclass
class RetrievalOutcome:
    """Results plus explicit branch health for a retrieval operation."""

    results: list[ScoredPassage] = field(default_factory=list)
    status: str = "complete"
    warnings: list[str] = field(default_factory=list)
    lexical_count: int = 0
    semantic_count: int = 0


class HybridRetriever:
    """Execute lexical/vector retrieval independently, then fuse candidates.

    Hybrid fusion uses weighted Reciprocal Rank Fusion. Raw lexical scores
    and cosine similarities are retained as branch metadata, while each
    branch's rank contribution is normalized against its rank-one value before
    applying the configured weight. This keeps the two score scales separate
    and makes the final ordering reproducible.
    """

    def __init__(
        self,
        session: AsyncSession,
        embedding_client: LocalEmbeddingClient | None = None,
    ):
        self.session = session
        self.lexical = LexicalRetriever(session)
        self.semantic = SemanticRetriever(session)
        self.embed_client = embedding_client or LocalEmbeddingClient()

    @staticmethod
    def _warning(branch: str, exc: Exception) -> str:
        return f"{branch} retrieval unavailable ({type(exc).__name__})."

    async def lexical_retrieve(
        self,
        query: str,
        source_type: SourceType | None = None,
        language: str | None = None,
        top_k: int = 5,
        source_id: str | None = None,
        document_id: str | None = None,
        document_version_id: str | None = None,
    ) -> RetrievalOutcome:
        results = await self.lexical.search(
            query=query,
            source_type=source_type,
            language=language,
            limit=top_k,
            source_id=source_id,
            document_id=document_id,
            document_version_id=document_version_id,
        )
        return RetrievalOutcome(results=results, lexical_count=len(results))

    async def semantic_retrieve(
        self,
        query: str,
        source_type: SourceType | None = None,
        top_k: int = 5,
        source_id: str | None = None,
        document_id: str | None = None,
        document_version_id: str | None = None,
    ) -> RetrievalOutcome:
        try:
            query_vector = await self.embed_client.get_embedding(query)
            results = await self.semantic.search(
                query_vector=query_vector,
                source_type=source_type,
                limit=top_k,
                source_id=source_id,
                document_id=document_id,
                document_version_id=document_version_id,
            )
            return RetrievalOutcome(results=results, semantic_count=len(results))
        except ValueError:
            raise
        except Exception as exc:
            return RetrievalOutcome(
                status="failed",
                warnings=[self._warning("semantic", exc)],
            )

    async def hybrid_retrieve_with_metadata(
        self,
        query: str,
        source_type: SourceType | None = None,
        language: str | None = None,
        top_k: int = 5,
        rrf_k: int | None = None,
        source_id: str | None = None,
        document_id: str | None = None,
        document_version_id: str | None = None,
        lexical_weight: float | None = None,
        semantic_weight: float | None = None,
        lexical_candidate_limit: int | None = None,
        semantic_candidate_limit: int | None = None,
    ) -> RetrievalOutcome:
        if top_k < 1:
            raise ValueError("top_k must be positive.")
        fusion_k = settings.HYBRID_RRF_K if rrf_k is None else rrf_k
        if fusion_k < 1:
            raise ValueError("rrf_k must be positive.")
        lexical_limit = (
            settings.HYBRID_LEXICAL_CANDIDATE_LIMIT
            if lexical_candidate_limit is None
            else lexical_candidate_limit
        )
        semantic_limit = (
            settings.HYBRID_SEMANTIC_CANDIDATE_LIMIT
            if semantic_candidate_limit is None
            else semantic_candidate_limit
        )
        if lexical_limit < 1 or semantic_limit < 1:
            raise ValueError("Hybrid candidate limits must be positive.")
        lexical_fusion_weight = (
            settings.HYBRID_LEXICAL_WEIGHT
            if lexical_weight is None
            else lexical_weight
        )
        semantic_fusion_weight = (
            settings.HYBRID_SEMANTIC_WEIGHT
            if semantic_weight is None
            else semantic_weight
        )
        if lexical_fusion_weight < 0 or semantic_fusion_weight < 0:
            raise ValueError("Hybrid weights cannot be negative.")

        lexical_outcome = RetrievalOutcome()
        warnings: list[str] = []
        try:
            lexical_outcome = await self.lexical_retrieve(
                query=query,
                source_type=source_type,
                language=language,
                top_k=lexical_limit,
                source_id=source_id,
                document_id=document_id,
                document_version_id=document_version_id,
            )
        except ValueError:
            raise
        except Exception as exc:
            warnings.append(self._warning("lexical", exc))

        try:
            semantic_outcome = await self.semantic_retrieve(
                query=query,
                source_type=source_type,
                top_k=semantic_limit,
                source_id=source_id,
                document_id=document_id,
                document_version_id=document_version_id,
            )
        except ValueError:
            raise
        except Exception as exc:
            warnings.append(self._warning("semantic", exc))
            semantic_outcome = RetrievalOutcome()
        warnings.extend(semantic_outcome.warnings)

        # Stable passage identity is the only union key. A passage present in
        # both branches appears once while retaining both contributions.
        candidates: dict[str, dict[str, Any]] = {}

        def add_branch(items: list[ScoredPassage], branch: str) -> None:
            rank_one = 1.0 / (fusion_k + 1)
            for rank, item in enumerate(items, start=1):
                passage_id = item.passage.id
                candidate = candidates.setdefault(
                    passage_id,
                    {
                        "passage": item.passage,
                        "lexical_score": None,
                        "semantic_score": None,
                        "lexical_rank": None,
                        "semantic_rank": None,
                        "normalized_lexical_score": None,
                        "normalized_semantic_score": None,
                    },
                )
                normalized = (1.0 / (fusion_k + rank)) / rank_one
                candidate[f"{branch}_score"] = float(item.score)
                candidate[f"{branch}_rank"] = rank
                candidate[f"normalized_{branch}_score"] = normalized

        add_branch(lexical_outcome.results, "lexical")
        add_branch(semantic_outcome.results, "semantic")

        fused: list[ScoredPassage] = []
        for candidate in candidates.values():
            lexical_contribution = candidate["normalized_lexical_score"]
            semantic_contribution = candidate["normalized_semantic_score"]
            hybrid_score = (
                lexical_fusion_weight * (lexical_contribution or 0.0)
                + semantic_fusion_weight * (semantic_contribution or 0.0)
            )
            fused.append(
                ScoredPassage(
                    passage=candidate["passage"],
                    score=hybrid_score,
                    retrieval_method="hybrid",
                    lexical_score=candidate["lexical_score"],
                    semantic_score=candidate["semantic_score"],
                    lexical_rank=candidate["lexical_rank"],
                    semantic_rank=candidate["semantic_rank"],
                    normalized_lexical_score=lexical_contribution,
                    normalized_semantic_score=semantic_contribution,
                    hybrid_score=hybrid_score,
                )
            )

        fused.sort(
            key=lambda item: (
                -item.score,
                item.passage.passage_order is None,
                item.passage.passage_order
                if item.passage.passage_order is not None
                else 0,
                item.passage.id,
            )
        )
        status = "failed" if warnings and not fused else "degraded" if warnings else "complete"
        return RetrievalOutcome(
            results=fused[:top_k],
            status=status,
            warnings=warnings,
            lexical_count=len(lexical_outcome.results),
            semantic_count=len(semantic_outcome.results),
        )

    async def hybrid_retrieve(
        self,
        query: str,
        source_type: SourceType | None = None,
        language: str | None = None,
        top_k: int = 5,
        rrf_k: int | None = None,
        source_id: str | None = None,
        document_id: str | None = None,
        document_version_id: str | None = None,
    ) -> list[ScoredPassage]:
        """Backward-compatible list API for existing application callers."""
        outcome = await self.hybrid_retrieve_with_metadata(
            query=query,
            source_type=source_type,
            language=language,
            top_k=top_k,
            rrf_k=rrf_k,
            source_id=source_id,
            document_id=document_id,
            document_version_id=document_version_id,
        )
        return outcome.results
