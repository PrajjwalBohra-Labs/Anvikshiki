import os
from pydantic import BaseModel, Field

class EmbeddingSettings(BaseModel):
    provider: str = "sentence-transformers"
    model_name: str = "all-MiniLM-L6-v2"
    model_version: str = "all-MiniLM-L6-v2@v1.0"
    dimensions: int = 384
    distance_metric: str = "cosine"

class RerankerSettings(BaseModel):
    provider: str = "cross-encoder"
    model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    model_version: str = "ms-marco-MiniLM-L-6-v2@v1.0"

class LLMSettings(BaseModel):
    provider: str = "ollama"
    model_name: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct-q4_K_M")
    base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    timeout_seconds: float = 45.0

class DatabaseSettings(BaseModel):
    url: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/anvikshiki")
    test_url: str = os.getenv("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")

class AppConfig(BaseModel):
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    reranker: RerankerSettings = Field(default_factory=RerankerSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)

config = AppConfig()