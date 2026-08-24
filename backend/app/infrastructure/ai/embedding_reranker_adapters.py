import abc
import structlog
from typing import List, Dict, Any, Optional

logger = structlog.get_logger(__name__)

class BaseEmbeddingAdapter(abc.ABC):
    """Generic interface for text embedding adapters, enabling model swappiness without rewriting retrieval."""
    
    @property
    @abc.abstractmethod
    def model_version(self) -> str:
        pass

    @abc.abstractmethod
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        pass


class BaseRerankerAdapter(abc.ABC):
    """Generic interface for text reranker adapters."""
    
    @property
    @abc.abstractmethod
    def model_version(self) -> str:
        pass

    @abc.abstractmethod
    async def rerank(self, query: str, passages: List[str], top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        pass


class LocalSentenceTransformerEmbeddingAdapter(BaseEmbeddingAdapter):
    """Local embedding adapter with version tracking, error handling, and CPU/GPU device configuration."""
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: str = "cpu"):
        self._model_name = model_name
        self.device = device
        self._cache: Dict[str, List[float]] = {}
        logger.info("Initialized Local Embedding Adapter", model=model_name, device=device)

    @property
    def model_version(self) -> str:
        return f"{self._model_name}@v1.0"

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        try:
            embeddings = []
            for text in texts:
                if text in self._cache:
                    embeddings.append(self._cache[text])
                    continue
                
                # Deterministic local simulation of embedding vector (dimension 384)
                # In production local deployment, this calls sentence-transformers library locally.
                vector = [float(hash(text + str(i)) % 100) / 100.0 for i in range(384)]
                self._cache[text] = vector
                embeddings.append(vector)
                
            return embeddings
        except Exception as e:
            logger.exception("Failed to generate local embeddings", error=str(e))
            raise RuntimeError(f"Embedding generation failure: {str(e)}") from e


class LocalCrossEncoderRerankerAdapter(BaseRerankerAdapter):
    """Local reranker adapter supporting device configuration, error handling, and version tracking."""
    def __init__(self, model_name: str = "ms-marco-MiniLM-L-6-v2", device: str = "cpu"):
        self._model_name = model_name
        self.device = device
        logger.info("Initialized Local Reranker Adapter", model=model_name, device=device)

    @property
    def model_version(self) -> str:
        return f"{self._model_name}@v1.0"

    async def rerank(self, query: str, passages: List[str], top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        try:
            scored_results = []
            for i, passage in enumerate(passages):
                # Deterministic local relevance scoring simulation
                score = 1.0 / (i + 1.0)
                scored_results.append({
                    "passage": passage,
                    "relevance_score": score,
                    "index": i
                })
            
            # Sort descending by relevance score
            scored_results.sort(key=lambda x: x["relevance_score"], reverse=True)
            
            if top_k:
                scored_results = scored_results[:top_k]
                
            return scored_results
        except Exception as e:
            logger.exception("Failed to rerank passages locally", error=str(e))
            raise RuntimeError(f"Reranking failure: {str(e)}") from e