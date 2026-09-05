from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.application.use_cases.citation_service import CitationService
from backend.app.infrastructure.ai.embedding_reranker_adapters import (
    LocalCrossEncoderRerankerAdapter,
    LocalSentenceTransformerEmbeddingAdapter,
)


def _passage(passage_id: str, page_number: int):
    source = SimpleNamespace(
        id="source-1",
        title="Measured source",
        author="Author",
        source_type="PRIMARY",
        reference_url=None,
    )
    document = SimpleNamespace(source=source)
    return SimpleNamespace(id=passage_id, page_number=page_number, document=document)


@pytest.mark.asyncio
async def test_batch_citation_resolution_uses_one_database_read_and_stable_values():
    session = SimpleNamespace()
    session.execute = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        _passage("passage-2", 2),
        _passage("passage-1", 1),
    ]
    session.execute.return_value = result

    citations = await CitationService(session).generate_citations(
        ["passage-1", "passage-2", "passage-1"]
    )

    assert session.execute.await_count == 1
    assert list(citations) == ["passage-2", "passage-1"]
    assert citations["passage-1"].citation_string == "Measured source, by Author, p. 1"
    assert citations["passage-2"].citation_string == "Measured source, by Author, p. 2"


@pytest.mark.asyncio
async def test_single_citation_contract_remains_authoritative():
    session = SimpleNamespace()
    session.execute = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [_passage("p", 3)]
    session.execute.return_value = result

    citation = await CitationService(session).generate_citation("p")

    assert citation.passage_id == "p"
    assert citation.source_id == "source-1"


@pytest.mark.asyncio
async def test_model_inference_is_offloaded_without_changing_results(monkeypatch):
    class FakeVector:
        def tolist(self):
            return [0.25, 0.75] + [0.0] * 382

    class FakeEmbeddingModel:
        def encode(self, texts, normalize_embeddings):
            assert normalize_embeddings is True
            return [FakeVector()]

    class FakeRerankerModel:
        def predict(self, pairs):
            return [0.75 for _ in pairs]

    embedding = LocalSentenceTransformerEmbeddingAdapter(model_name="test")
    reranker = LocalCrossEncoderRerankerAdapter(model_name="test")
    monkeypatch.setattr(embedding, "_get_model", lambda: FakeEmbeddingModel())
    monkeypatch.setattr(reranker, "_get_model", lambda: FakeRerankerModel())

    vectors = await embedding.embed_texts(["query"])
    assert vectors[0][:2] == [0.25, 0.75]
    assert len(vectors[0]) == 384
    assert await reranker.rerank("query", ["passage"]) == [
        {"passage": "passage", "relevance_score": 0.75, "rank": 1}
    ]
