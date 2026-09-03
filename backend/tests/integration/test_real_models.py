import pytest

from backend.app.config.settings import config
from backend.app.infrastructure.ai.embedding_reranker_adapters import (
    LocalCrossEncoderRerankerAdapter,
    LocalSentenceTransformerEmbeddingAdapter,
)

pytestmark = pytest.mark.real_models


@pytest.mark.asyncio
async def test_configured_sentence_transformer_executes_and_returns_384_dimensions() -> None:
    adapter = LocalSentenceTransformerEmbeddingAdapter()
    vectors = await adapter.embed_texts(["A claim grounded in a primary source."])

    assert adapter.model_name == config.embedding.model_name
    assert adapter.model_version == config.embedding.model_version
    assert adapter._model is not None
    assert len(vectors) == 1
    assert len(vectors[0]) == 384
    assert abs(sum(value * value for value in vectors[0]) - 1.0) < 1e-5


@pytest.mark.asyncio
async def test_configured_cross_encoder_executes_relevance_scoring() -> None:
    adapter = LocalCrossEncoderRerankerAdapter()
    results = await adapter.rerank(
        "What causes direct perception?",
        [
            "Direct perception arises from contact between a sense faculty and its object.",
            "A recipe describes how to bake bread with measured ingredients.",
        ],
        top_k=2,
    )

    assert adapter.model_name == config.reranker.model_name
    assert adapter.model_version == config.reranker.model_version
    assert adapter._model is not None
    assert len(results) == 2
    assert results[0]["passage"].startswith("Direct perception")
    assert results[0]["relevance_score"] > results[1]["relevance_score"]
