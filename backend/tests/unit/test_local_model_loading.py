import asyncio

from backend.app.core.config import settings
from backend.app.infrastructure.ai.embedding_reranker_adapters import (
    LocalCrossEncoderRerankerAdapter,
    LocalSentenceTransformerEmbeddingAdapter,
)


def test_local_model_adapters_do_not_start_network_downloads(monkeypatch):
    embedding_calls = []
    reranker_calls = []

    class FakeEmbeddingModel:
        def __init__(self, name, **kwargs):
            embedding_calls.append((name, kwargs))

        def encode(self, texts, normalize_embeddings):
            return [[0.0] * 384 for _ in texts]

    class FakeRerankerModel:
        def __init__(self, name, **kwargs):
            reranker_calls.append((name, kwargs))

        def predict(self, pairs):
            return [0.0] * len(pairs)

    import sentence_transformers

    monkeypatch.setattr(
        sentence_transformers, "SentenceTransformer", FakeEmbeddingModel
    )
    monkeypatch.setattr(sentence_transformers, "CrossEncoder", FakeRerankerModel)
    monkeypatch.setattr(settings, "EMBEDDING_LOCAL_FILES_ONLY", True)
    monkeypatch.setattr(settings, "RERANKER_LOCAL_FILES_ONLY", True)

    asyncio.run(LocalSentenceTransformerEmbeddingAdapter().embed_texts(["local"]))
    asyncio.run(LocalCrossEncoderRerankerAdapter().rerank("local", ["passage"]))

    assert embedding_calls[0][1]["local_files_only"] is True
    assert reranker_calls[0][1]["local_files_only"] is True
