import httpx
import math
import hashlib
from typing import List
from backend.app.core.config import settings, RuntimeProfile
from backend.app.core.errors import AnvikshikiDomainError
import structlog

logger = structlog.get_logger(__name__)

class LocalEmbeddingClient:
    def __init__(self, base_url: str = settings.OLLAMA_BASE_URL, model: str = settings.EMBEDDING_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def _generate_synthetic_vector(self, text: str, dim: int = 64) -> List[float]:
        """
        Generates a deterministic pseudo-random vector for isolated CI testing.
        Ensures tests pass even if Ollama is entirely offline.
        """
        vec = []
        for i in range(dim):
            h = hashlib.sha256(f"{text}_{i}".encode("utf-8")).hexdigest()
            # Normalize hash to a float between -1 and 1
            val = (int(h[:8], 16) / 0xFFFFFFFF) * 2 - 1
            vec.append(val)
            
        # L2 Normalize
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    async def get_embedding(self, text: str) -> List[float]:
        """Fetches the dense vector embedding for a given string."""
        if not text.strip():
            return []

        # Graceful CI degradation
        if settings.RUNTIME_PROFILE == RuntimeProfile.TEST:
            return self._generate_synthetic_vector(text)

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text}
                )
                response.raise_for_status()
                data = response.json()
                return data.get("embedding", [])
        except httpx.RequestError as e:
            logger.error("Failed to connect to local embedding model", error=str(e))
            raise AnvikshikiDomainError("Embedding service unavailable.", status_code=503)