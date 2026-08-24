import httpx
from typing import List
from backend.app.core.config import settings

class OllamaEmbeddingClient:
    def __init__(self, base_url: str = settings.OLLAMA_BASE_URL, model: str = settings.EMBEDDING_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def get_embedding(self, text: str) -> List[float]:
        try:
            async with httpx.AsyncClient(timeout=0.5) as client:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text}
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("embedding", [])
        except Exception:
            pass
        return self._generate_fallback_vector(text)

    @staticmethod
    def _generate_fallback_vector(text: str, dim: int = 64) -> List[float]:
        import hashlib
        import math
        vec = []
        for i in range(dim):
            h = hashlib.sha256(f"{text}_{i}".encode("utf-8")).hexdigest()
            val = (int(h[:8], 16) / 0xFFFFFFFF) * 2 - 1
            vec.append(val)
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]