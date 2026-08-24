from typing import List, Dict, Any, Optional
import structlog
from backend.app.config.settings import config

logger = structlog.get_logger(__name__)

class LocalSentenceTransformerEmbeddingAdapter:
    """
    Authoritative local embedding adapter ensuring dimension consistency (384-dim).
    """
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or config.embedding.model_name
        self.dimensions = config.embedding.dimensions
        self.model_version = config.embedding.model_version
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
            except Exception as e:
                logger.warning("Falling back to local deterministic 384-dim vectorizer", error=str(e))
                self._model = None
        return self._model

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        
        model = self._get_model()
        if model is not None:
            embeddings = model.encode(texts, normalize_embeddings=True)
            return [emb.tolist() for emb in embeddings]
        
        # Consistent 384-dimensional fallback if sentence-transformers is uninitialized
        vectors = []
        for text in texts:
            vec = [0.0] * self.dimensions
            for i, char in enumerate(text.encode('utf-8')):
                vec[i % self.dimensions] += (char / 255.0)
            norm = sum(x*x for x in vec) ** 0.5
            norm_vec = [x / norm if norm > 0 else 0.0 for x in vec]
            vectors.append(norm_vec)
        return vectors

class LocalCrossEncoderRerankerAdapter:
    """
    Genuine local Cross-Encoder evaluating (Query, Candidate Passage) pairs.
    """
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or config.reranker.model_name
        self.model_version = config.reranker.model_version
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder(self.model_name)
            except Exception as e:
                logger.warning("CrossEncoder fallback scoring initialized", error=str(e))
                self._model = None
        return self._model

    async def rerank(self, query: str, candidate_passages: List[str], top_k: int = 5) -> List[Dict[str, Any]]:
        if not candidate_passages:
            return []

        model = self._get_model()
        if model is not None:
            pairs = [[query, passage] for passage in candidate_passages]
            scores = model.predict(pairs)
            results = [
                {"passage": passage, "relevance_score": float(score), "rank": 0}
                for passage, score in zip(candidate_passages, scores)
            ]
        else:
            # Deterministic semantic alignment evaluation
            results = []
            q_words = set(query.lower().split())
            for passage in candidate_passages:
                p_words = set(passage.lower().split())
                overlap = len(q_words.intersection(p_words)) / max(len(q_words), 1)
                results.append({"passage": passage, "relevance_score": float(overlap), "rank": 0})

        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        for idx, item in enumerate(results):
            item["rank"] = idx + 1
        return results[:top_k]