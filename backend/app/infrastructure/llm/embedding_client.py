import hashlib
import math
from typing import List

import structlog

from backend.app.core.config import RuntimeProfile, settings
from backend.app.infrastructure.ai.embedding_reranker_adapters import (
    LocalSentenceTransformerEmbeddingAdapter,
)

logger = structlog.get_logger(__name__)


class LocalEmbeddingClient:
    """Embedding client used by the legacy retrieval facade.

    Production uses the configured sentence-transformers model. The synthetic
    vector is retained only for isolated SQLite tests and is never available
    on the production profile.
    """

    def __init__(self, base_url: str = settings.OLLAMA_BASE_URL, model: str = settings.EMBEDDING_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.adapter = LocalSentenceTransformerEmbeddingAdapter(model_name=model)

    def _generate_synthetic_vector(self, text: str, dim: int = 64) -> List[float]:
        vec = []
        for i in range(dim):
            digest = hashlib.sha256(f"{text}_{i}".encode("utf-8")).hexdigest()
            value = (int(digest[:8], 16) / 0xFFFFFFFF) * 2 - 1
            vec.append(value)
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    async def get_embedding(self, text: str) -> List[float]:
        if not text.strip():
            return []
        if settings.RUNTIME_PROFILE == RuntimeProfile.TEST:
            return self._generate_synthetic_vector(text)
        return (await self.adapter.embed_texts([text]))[0]
