"""Durable semantic indexing for authoritative document passages.

Passages remain the authoritative corpus records.  Their vector and the
metadata in this module are derived state that can be regenerated safely.
"""

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.config import settings
from backend.app.domain.models.enums import EmbeddingIndexStatus, SourceType
from backend.app.infrastructure.ai.embedding_reranker_adapters import (
    LocalSentenceTransformerEmbeddingAdapter,
)
from backend.app.infrastructure.database.models import (
    DocumentModel,
    PassageModel,
    SourceModel,
)
from backend.app.infrastructure.rag.lexical_retriever import ScoredPassage


class EmbeddingIndexError(RuntimeError):
    """Raised when a derived embedding cannot be generated or validated."""


@dataclass(frozen=True)
class EmbeddingIndexResult:
    passage_id: str
    status: EmbeddingIndexStatus
    reused: bool = False
    error: str | None = None


class EmbeddingIndexService:
    """Create, retry, and query the current embedding for each passage."""

    def __init__(
        self,
        session: AsyncSession,
        embedder: LocalSentenceTransformerEmbeddingAdapter | None = None,
    ):
        self.session = session
        self.embedder = embedder or LocalSentenceTransformerEmbeddingAdapter()
        self.provider = settings.EMBEDDING_PROVIDER
        self.model_name = getattr(self.embedder, "model_name", settings.EMBEDDING_MODEL)
        self.model_version = getattr(
            self.embedder, "model_version", settings.EMBEDDING_MODEL
        )
        self.dimension = int(
            getattr(self.embedder, "dimensions", settings.EMBEDDING_DIMENSIONS)
        )
        if self.dimension != settings.EMBEDDING_DIMENSIONS:
            raise EmbeddingIndexError(
                "Embedding configuration dimension does not match the configured index dimension."
            )
        column_dimension = getattr(PassageModel.__table__.c.embedding.type, "dim", None)
        if column_dimension is not None and column_dimension != self.dimension:
            raise EmbeddingIndexError(
                "Embedding configuration dimension does not match the pgvector column dimension."
            )
        self.config_fingerprint = self._configuration_fingerprint()

    def _configuration_fingerprint(self) -> str:
        payload = {
            "provider": self.provider,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "dimension": self.dimension,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def content_fingerprint(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _is_current(self, passage: PassageModel, content_hash: str) -> bool:
        return bool(
            passage.embedding_status == EmbeddingIndexStatus.INDEXED
            and passage.embedding is not None
            and passage.embedding_provider == self.provider
            and passage.embedding_model_version == self.model_version
            and passage.embedding_dimension == self.dimension
            and passage.embedding_config_fingerprint == self.config_fingerprint
            and passage.embedding_content_sha256 == content_hash
        )

    async def _mark_failed(self, passage_id: str, error: str) -> EmbeddingIndexResult:
        await self.session.rollback()
        passage = await self.session.get(PassageModel, passage_id)
        if passage is None:
            raise EmbeddingIndexError(f"Passage {passage_id} no longer exists.")
        passage.embedding = None
        passage.embedding_status = EmbeddingIndexStatus.FAILED
        passage.embedding_model = self.model_version
        passage.embedding_provider = self.provider
        passage.embedding_model_version = self.model_version
        passage.embedding_dimension = self.dimension
        passage.embedding_config_fingerprint = self.config_fingerprint
        passage.embedding_content_sha256 = self.content_fingerprint(passage.content)
        passage.embedding_generated_at = None
        passage.embedding_error = error[:500]
        await self.session.commit()
        return EmbeddingIndexResult(
            passage_id=passage.id,
            status=EmbeddingIndexStatus.FAILED,
            error=passage.embedding_error,
        )

    async def _index_batch(
        self, passages: list[PassageModel], raise_on_error: bool = False
    ) -> list[EmbeddingIndexResult]:
        pending: list[tuple[PassageModel, str, str, str]] = []
        results: list[EmbeddingIndexResult] = []
        for passage in passages:
            content_hash = self.content_fingerprint(passage.content)
            if self._is_current(passage, content_hash):
                results.append(
                    EmbeddingIndexResult(
                        passage_id=passage.id,
                        status=EmbeddingIndexStatus.INDEXED,
                        reused=True,
                    )
                )
                continue
            if not passage.content.strip():
                result = await self._mark_failed(passage.id, "Passage content is empty.")
                results.append(result)
                if raise_on_error:
                    raise EmbeddingIndexError(result.error)
                continue
            passage.embedding_status = EmbeddingIndexStatus.INDEXING
            passage.embedding = None
            passage.embedding_model = self.model_version
            passage.embedding_provider = self.provider
            passage.embedding_model_version = self.model_version
            passage.embedding_dimension = self.dimension
            passage.embedding_config_fingerprint = self.config_fingerprint
            passage.embedding_content_sha256 = content_hash
            passage.embedding_generated_at = None
            passage.embedding_error = None
            pending.append((passage, content_hash, passage.id, passage.content))

        if not pending:
            return results

        await self.session.commit()
        try:
            vectors = await self.embedder.embed_texts([item[3] for item in pending])
            if len(vectors) != len(pending):
                raise EmbeddingIndexError("Embedding provider returned an incomplete batch.")
            for index, (passage, _, passage_id, _) in enumerate(pending):
                vector = vectors[index]
                if not isinstance(vector, list) or len(vector) != self.dimension:
                    raise EmbeddingIndexError(
                        f"Embedding provider returned dimension {len(vector) if vector is not None else 0}; "
                        f"expected {self.dimension}."
                    )
                passage.embedding = vector
                passage.embedding_status = EmbeddingIndexStatus.INDEXED
                passage.embedding_generated_at = datetime.now(timezone.utc)
                passage.embedding_error = None
                results.append(
                    EmbeddingIndexResult(
                        passage_id=passage_id,
                        status=EmbeddingIndexStatus.INDEXED,
                    )
                )
            await self.session.commit()
        except Exception as exc:
            error = f"Embedding generation failed: {type(exc).__name__}: {str(exc)[:400]}"
            failed_results = []
            for _, _, passage_id, _ in pending:
                failed_results.append(await self._mark_failed(passage_id, error))
            results.extend(failed_results)
            if raise_on_error:
                raise EmbeddingIndexError(error) from exc
        return results

    async def index_passage(
        self, passage_id: str, force: bool = False
    ) -> EmbeddingIndexResult | None:
        passage = await self.session.get(PassageModel, passage_id)
        if passage is None:
            return None
        if force:
            passage.embedding_status = EmbeddingIndexStatus.PENDING
        results = await self._index_batch([passage], raise_on_error=True)
        return results[0]

    async def index_passages(
        self,
        passage_ids: Iterable[str] | None = None,
        document_id: str | None = None,
        document_version_id: str | None = None,
        batch_size: int | None = None,
    ) -> list[EmbeddingIndexResult]:
        """Index passages in stable batches; failed batches remain retryable."""
        if not any((passage_ids is not None, document_id, document_version_id)):
            raise ValueError("An indexing scope is required.")
        batch_limit = batch_size or settings.EMBEDDING_BATCH_SIZE
        if batch_limit < 1:
            raise ValueError("batch_size must be positive.")
        ids = list(passage_ids) if passage_ids is not None else None
        results: list[EmbeddingIndexResult] = []
        offset = 0
        while True:
            stmt = select(PassageModel)
            if ids is not None:
                if not ids:
                    break
                stmt = stmt.where(PassageModel.id.in_(ids))
            if document_id:
                stmt = stmt.where(PassageModel.document_id == document_id)
            if document_version_id:
                stmt = stmt.where(PassageModel.document_version_id == document_version_id)
            stmt = stmt.order_by(
                PassageModel.document_id,
                PassageModel.passage_order,
                PassageModel.id,
            ).offset(offset).limit(batch_limit)
            rows = (await self.session.execute(stmt)).scalars().all()
            if not rows:
                break
            results.extend(await self._index_batch(rows))
            offset += len(rows)
            if len(rows) < batch_limit:
                break
        return results

    async def search(
        self,
        query: str | None = None,
        query_vector: list[float] | None = None,
        source_type: SourceType | None = None,
        document_id: str | None = None,
        document_version_id: str | None = None,
        limit: int = 10,
    ) -> list[ScoredPassage]:
        """Search current indexed vectors while retaining passage provenance."""
        if query_vector is None:
            if not query or not query.strip():
                return []
            vectors = await self.embedder.embed_texts([query])
            if len(vectors) != 1:
                raise EmbeddingIndexError("Query embedding provider returned no vector.")
            query_vector = vectors[0]
        if len(query_vector) != self.dimension:
            raise EmbeddingIndexError(
                f"Query embedding dimension {len(query_vector)} does not match {self.dimension}."
            )
        if limit < 1:
            return []

        stmt = (
            select(PassageModel)
            .join(PassageModel.document)
            .join(DocumentModel.source)
            .where(PassageModel.embedding.is_not(None))
            .where(PassageModel.embedding_status == EmbeddingIndexStatus.INDEXED)
            .options(selectinload(PassageModel.document).selectinload(DocumentModel.source))
        )
        if source_type:
            stmt = stmt.where(SourceModel.source_type == source_type)
        if document_id:
            stmt = stmt.where(PassageModel.document_id == document_id)
        if document_version_id:
            stmt = stmt.where(PassageModel.document_version_id == document_version_id)

        bind = self.session.get_bind()
        is_postgres = bind is not None and bind.dialect.name == "postgresql"
        if is_postgres:
            distance = PassageModel.embedding.cosine_distance(query_vector).label("distance")
            result = await self.session.execute(
                select(PassageModel, distance)
                .join(PassageModel.document)
                .join(DocumentModel.source)
                .where(PassageModel.embedding.is_not(None))
                .where(PassageModel.embedding_status == EmbeddingIndexStatus.INDEXED)
                .where(
                    SourceModel.source_type == source_type if source_type else True
                )
                .where(PassageModel.document_id == document_id if document_id else True)
                .where(
                    PassageModel.document_version_id == document_version_id
                    if document_version_id
                    else True
                )
                .options(selectinload(PassageModel.document).selectinload(DocumentModel.source))
                .order_by(distance, PassageModel.id)
                .limit(limit)
            )
            return [
                ScoredPassage(passage=passage, score=1.0 - float(distance_value))
                for passage, distance_value in result.all()
            ]

        # SQLite remains a test-only fallback; production vector ranking is SQL/pgvector.
        import math

        rows = (await self.session.execute(stmt)).scalars().all()
        scored = []
        for passage in rows:
            dot = sum(a * b for a, b in zip(query_vector, passage.embedding))
            left = math.sqrt(sum(value * value for value in query_vector))
            right = math.sqrt(sum(value * value for value in passage.embedding))
            score = dot / (left * right) if left and right else 0.0
            scored.append(ScoredPassage(passage=passage, score=score))
        scored.sort(key=lambda item: (-item.score, item.passage.id))
        return scored[:limit]
