from datetime import datetime
from hashlib import sha256

import pytest
from sqlalchemy import func, select

from backend.app.application.use_cases.embedding_indexing import (
    EmbeddingIndexError,
    EmbeddingIndexService,
)
from backend.app.application.use_cases.provenance import ProvenanceService
from backend.app.core.config import settings
from backend.app.domain.models.enums import EmbeddingIndexStatus, SourceType
from backend.app.infrastructure.database.models import (
    DocumentModel,
    PassageModel,
    SourceModel,
)
from backend.app.infrastructure.database.session import AsyncSessionLocal, Base, engine


class FakeEmbedder:
    model_name = "local-test-embedder"
    model_version = "local-test-embedder@fixture-1"
    dimensions = 4

    def __init__(self, vectors=None, error=None, model_version=None):
        self.vectors = vectors
        self.error = error
        if model_version is not None:
            self.model_version = model_version
        self.calls = []

    async def embed_texts(self, texts):
        self.calls.append(list(texts))
        if self.error:
            raise self.error
        if self.vectors is not None:
            if len(self.vectors) == len(texts):
                return self.vectors
            return [self.vectors[int(text.split()[1])] for text in texts]
        return [[float(index == 0), 0.0, 0.0, 0.0] for index, _ in enumerate(texts)]


class WrongDimensionEmbedder(FakeEmbedder):
    dimensions = 4

    async def embed_texts(self, texts):
        self.calls.append(list(texts))
        return [[1.0, 0.0, 0.0] for _ in texts]


def test_embedding_configuration_is_explicit_and_bounded():
    assert settings.EMBEDDING_PROVIDER == "sentence-transformers"
    assert settings.EMBEDDING_MODEL == "all-MiniLM-L6-v2"
    assert settings.EMBEDDING_DIMENSIONS == 384
    assert settings.EMBEDDING_BATCH_SIZE > 0


@pytest.fixture
async def indexing_environment(monkeypatch):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    previous_dimensions = settings.EMBEDDING_DIMENSIONS
    monkeypatch.setattr(settings, "EMBEDDING_DIMENSIONS", 4)
    yield
    settings.EMBEDDING_DIMENSIONS = previous_dimensions
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


async def _passages(session, count=1):
    source = SourceModel(title="Indexing test source", source_type=SourceType.PRIMARY)
    session.add(source)
    await session.flush()
    document = DocumentModel(
        source_id=source.id,
        checksum_sha256=sha256(f"document-{count}".encode()).hexdigest(),
        mime_type="text/plain",
        original_filename="indexing.txt",
        size_bytes=32,
        total_pages=1,
    )
    session.add(document)
    await session.flush()
    passages = []
    for index in range(count):
        passage = PassageModel(
            document_id=document.id,
            page_number=1,
            passage_order=index,
            content=f"Passage {index} about knowledge.",
            language="en",
            embedding_status=EmbeddingIndexStatus.PENDING,
        )
        session.add(passage)
        passages.append(passage)
    await session.commit()
    return source, document, passages


@pytest.mark.asyncio
async def test_embedding_metadata_identity_and_idempotency(indexing_environment):
    async with AsyncSessionLocal() as session:
        _, _, passages = await _passages(session)
        embedder = FakeEmbedder(vectors=[[1.0, 0.0, 0.0, 0.0]])
        service = EmbeddingIndexService(session, embedder)

        first = await service.index_passage(passages[0].id)
        second = await service.index_passage(passages[0].id)

        assert first.status == EmbeddingIndexStatus.INDEXED
        assert first.reused is False
        assert second.reused is True
        assert len(embedder.calls) == 1
        assert passages[0].embedding == [1.0, 0.0, 0.0, 0.0]
        assert passages[0].embedding_dimension == 4
        assert passages[0].embedding_provider == settings.EMBEDDING_PROVIDER
        assert passages[0].embedding_model_version == embedder.model_version
        assert passages[0].embedding_content_sha256 == service.content_fingerprint(
            passages[0].content
        )
        assert len(passages[0].embedding_config_fingerprint) == 64
        assert isinstance(passages[0].embedding_generated_at, datetime)

        changed_model = await EmbeddingIndexService(
            session,
            FakeEmbedder(
                vectors=[[0.0, 0.0, 1.0, 0.0]],
                model_version="local-test-embedder@fixture-2",
            ),
        ).index_passage(passages[0].id)
        assert changed_model.reused is False
        assert changed_model.status == EmbeddingIndexStatus.INDEXED
        assert len(embedder.calls) == 1

        passages[0].content = "Changed documentary passage text."
        await session.commit()
        changed = await service.index_passage(passages[0].id)
        assert changed.reused is False
        assert len(embedder.calls) == 2
        assert passages[0].embedding_content_sha256 == service.content_fingerprint(
            passages[0].content
        )


@pytest.mark.asyncio
async def test_dimension_mismatch_fails_without_changing_authoritative_text(
    indexing_environment,
):
    async with AsyncSessionLocal() as session:
        _, _, passages = await _passages(session)
        original = passages[0].content
        with pytest.raises(EmbeddingIndexError, match="expected 4"):
            await EmbeddingIndexService(session, WrongDimensionEmbedder()).index_passage(
                passages[0].id
            )

        await session.refresh(passages[0])
        assert passages[0].content == original
        assert passages[0].embedding is None
        assert passages[0].embedding_status == EmbeddingIndexStatus.FAILED
        assert "dimension 3" in passages[0].embedding_error


@pytest.mark.asyncio
async def test_failure_is_recorded_and_retry_succeeds(indexing_environment):
    async with AsyncSessionLocal() as session:
        _, _, passages = await _passages(session)
        failed_embedder = FakeEmbedder(error=RuntimeError("model unavailable"))
        failed = await EmbeddingIndexService(session, failed_embedder).index_passages(
            passage_ids=[passages[0].id]
        )
        assert failed[0].status == EmbeddingIndexStatus.FAILED
        await session.refresh(passages[0])
        assert passages[0].embedding_status == EmbeddingIndexStatus.FAILED
        assert passages[0].embedding is None
        assert "model unavailable" in passages[0].embedding_error

        retried = await EmbeddingIndexService(
            session, FakeEmbedder(vectors=[[0.0, 1.0, 0.0, 0.0]])
        ).index_passage(passages[0].id)
        assert retried.status == EmbeddingIndexStatus.INDEXED
        await session.refresh(passages[0])
        assert passages[0].embedding == [0.0, 1.0, 0.0, 0.0]


@pytest.mark.asyncio
async def test_batch_order_search_filters_and_provenance(indexing_environment):
    async with AsyncSessionLocal() as session:
        source, document, passages = await _passages(session, count=3)
        vectors = [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
        ]
        results = await EmbeddingIndexService(
            session, FakeEmbedder(vectors=vectors)
        ).index_passages(document_id=document.id, batch_size=2)
        assert [result.passage_id for result in results] == [
            passage.id for passage in passages
        ]
        assert all(result.status == EmbeddingIndexStatus.INDEXED for result in results)

        search_results = await EmbeddingIndexService(session, FakeEmbedder()).search(
            query_vector=[0.0, 1.0, 0.0, 0.0], document_id=document.id, limit=2
        )
        assert search_results[0].passage.id == passages[1].id
        assert search_results[0].score == pytest.approx(1.0)
        assert all(result.passage.document.source.id == source.id for result in search_results)

        graph = await ProvenanceService(session).trace_passage(passages[1].id)
        passage_node = next(node for node in graph["nodes"] if node["entity_id"] == passages[1].id)
        assert passage_node["metadata"]["embedding_status"] == "INDEXED"
        assert passage_node["metadata"]["embedding_dimension"] == 4

        indexed_count = await session.scalar(
            select(func.count(PassageModel.id)).where(
                PassageModel.embedding_status == EmbeddingIndexStatus.INDEXED
            )
        )
        assert indexed_count == 3
