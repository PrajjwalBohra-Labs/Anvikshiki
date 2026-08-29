import re
import unicodedata
from typing import List, Optional

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.config import settings
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.database.models import (
    DocumentModel,
    PassageModel,
    SourceModel,
)


class ScoredPassage:
    """A passage plus retrieval scores; documentary content stays on passage."""

    def __init__(
        self,
        passage: PassageModel,
        score: float,
        retrieval_method: str = "unknown",
        lexical_score: Optional[float] = None,
        semantic_score: Optional[float] = None,
        lexical_rank: Optional[int] = None,
        semantic_rank: Optional[int] = None,
        normalized_lexical_score: Optional[float] = None,
        normalized_semantic_score: Optional[float] = None,
        hybrid_score: Optional[float] = None,
        rerank_score: Optional[float] = None,
    ):
        self.passage = passage
        self.score = float(score)
        self.retrieval_method = retrieval_method
        self.lexical_score = lexical_score
        self.semantic_score = semantic_score
        self.lexical_rank = lexical_rank
        self.semantic_rank = semantic_rank
        self.normalized_lexical_score = normalized_lexical_score
        self.normalized_semantic_score = normalized_semantic_score
        self.hybrid_score = hybrid_score
        self.rerank_score = rerank_score


class LexicalRetriever:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(
        self,
        query: str,
        source_type: Optional[SourceType] = None,
        language: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        source_id: Optional[str] = None,
        document_id: Optional[str] = None,
        document_version_id: Optional[str] = None,
    ) -> List[ScoredPassage]:
        """Search authoritative passage text with lexical ranking.

        PostgreSQL uses the trigger-maintained ``search_vector`` and
        ``websearch_to_tsquery`` with the conservative ``simple`` parser.
        The parser preserves terminology instead of applying English stemming
        or stop words. SQLite is retained only for isolated tests and uses a
        deterministic substring/term-frequency compatibility path.

        Scores express lexical relevance, not probability or confidence.
        Equal scores are resolved by passage order and stable passage ID.
        """
        normalized_query = unicodedata.normalize("NFC", query or "").strip()
        if not normalized_query:
            return []
        if len(normalized_query) > settings.LEXICAL_MAX_QUERY_LENGTH:
            raise ValueError(
                f"Lexical query exceeds {settings.LEXICAL_MAX_QUERY_LENGTH} characters."
            )
        resolved_limit = settings.LEXICAL_DEFAULT_LIMIT if limit is None else limit
        if resolved_limit < 1 or resolved_limit > settings.LEXICAL_MAX_RESULTS:
            raise ValueError(
                f"Lexical result limit must be between 1 and {settings.LEXICAL_MAX_RESULTS}."
            )
        if offset < 0:
            raise ValueError("Lexical result offset cannot be negative.")

        bind = self.session.get_bind()
        is_postgres = bind.dialect.name == "postgresql" if bind else False
        if is_postgres:
            query_ts = func.websearch_to_tsquery(
                settings.LEXICAL_SEARCH_CONFIG, normalized_query
            )
            rank = func.ts_rank_cd(PassageModel.search_vector, query_ts).label("rank")
            stmt = (
                select(PassageModel, rank)
                .join(PassageModel.document)
                .join(DocumentModel.source)
                .where(PassageModel.search_vector.op("@@")(query_ts))
            )
            if source_type:
                stmt = stmt.where(SourceModel.source_type == source_type)
            if language:
                stmt = stmt.where(PassageModel.language == language)
            if source_id:
                stmt = stmt.where(DocumentModel.source_id == source_id)
            if document_id:
                stmt = stmt.where(PassageModel.document_id == document_id)
            if document_version_id:
                stmt = stmt.where(PassageModel.document_version_id == document_version_id)
            stmt = (
                stmt.options(selectinload(PassageModel.document).selectinload(DocumentModel.source))
                .order_by(
                    desc(rank),
                    PassageModel.passage_order.asc().nulls_last(),
                    PassageModel.id.asc(),
                )
                .offset(offset)
                .limit(resolved_limit)
            )
            result = await self.session.execute(stmt)
            return [
                ScoredPassage(
                    passage=passage,
                    score=float(score or 0.0),
                    retrieval_method="lexical",
                    lexical_score=float(score or 0.0),
                )
                for passage, score in result.all()
            ]

        # SQLite test databases do not provide tsvector or GIN. This path
        # does not alter the authoritative content or public result shape.
        terms = [
            term.lower()
            for term in re.findall(r"\w+", normalized_query, flags=re.UNICODE)
            if len(term) > 2
        ]
        if not terms:
            return []

        conditions = [PassageModel.content.ilike(f"%{term}%") for term in terms]
        stmt = select(PassageModel).join(PassageModel.document).join(DocumentModel.source)
        stmt = stmt.where(or_(*conditions))
        if source_type:
            stmt = stmt.where(SourceModel.source_type == source_type)
        if language:
            stmt = stmt.where(PassageModel.language == language)
        if source_id:
            stmt = stmt.where(DocumentModel.source_id == source_id)
        if document_id:
            stmt = stmt.where(PassageModel.document_id == document_id)
        if document_version_id:
            stmt = stmt.where(PassageModel.document_version_id == document_version_id)
        stmt = stmt.options(
            selectinload(PassageModel.document).selectinload(DocumentModel.source)
        )

        result = await self.session.execute(stmt)
        passages = result.scalars().all()
        scored_results = []
        for passage in passages:
            content_lower = passage.content.lower()
            score = sum(content_lower.count(term) for term in terms)
            if normalized_query.lower() in content_lower:
                score += 5.0
            scored_results.append(
                ScoredPassage(
                    passage=passage,
                    score=float(score),
                    retrieval_method="lexical",
                    lexical_score=float(score),
                )
            )

        scored_results.sort(
            key=lambda item: (
                -item.score,
                item.passage.passage_order is None,
                item.passage.passage_order
                if item.passage.passage_order is not None
                else 0,
                item.passage.id,
            )
        )
        return scored_results[offset : offset + resolved_limit]
