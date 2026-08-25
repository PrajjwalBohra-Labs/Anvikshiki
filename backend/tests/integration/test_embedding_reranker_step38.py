import pytest
from backend.app.infrastructure.ai.embedding_reranker_adapters import (
    LocalSentenceTransformerEmbeddingAdapter,
    LocalCrossEncoderRerankerAdapter
)

@pytest.mark.asyncio
async def test_embedding_adapter_version_and_caching():
    adapter = LocalSentenceTransformerEmbeddingAdapter(model_name="test-embed")
    assert adapter.model_version == "test-embed@v1.0"

    texts = ["Pramana is valid means of knowledge.", "Pratyaksha is perception."]
    vectors = await adapter.embed_texts(texts)

    assert len(vectors) == 2
    assert len(vectors[0]) == 384

    # Test cache hit behavior
    cached_vectors = await adapter.embed_texts(texts)
    assert cached_vectors == vectors

@pytest.mark.asyncio
async def test_reranker_adapter_scoring():
    adapter = LocalCrossEncoderRerankerAdapter(model_name="test-rerank")
    assert adapter.model_version == "test-rerank@v1.0"

    query = "What is perception?"
    passages = [
        "Inference is secondary knowledge.",
        "Perception is direct sensory cognition.",
        "Sound is eternal."
    ]

    results = await adapter.rerank(query, passages, top_k=2)
    assert len(results) == 2
    assert "relevance_score" in results[0]
    assert results[0]["relevance_score"] >= results[1]["relevance_score"]
