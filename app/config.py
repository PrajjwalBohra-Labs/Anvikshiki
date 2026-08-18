"""
Central configuration. All values come from environment variables /
.env — nothing here is hard-coded per §30. Individual services should
depend on this Settings object, never read os.environ directly.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    app_name: str = "anvikshiki"
    environment: str = "development"
    log_level: str = "INFO"

    # --- LLM / embeddings (Ollama) ---
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_generation_model: str = "llama3.1"
    ollama_embedding_model: str = "nomic-embed-text"

    # --- Relational store ---
    database_path: str = "./data/anvikshiki.db"

    # --- Vector store (plain SQLite table, no Chroma) ---
    vector_store_path: str = "./data/vectors.db"

    # --- File store ---
    file_store_path: str = "./data/files"

    # --- Cache ---
    cache_ttl_seconds: int = 300

    # --- Security (§27) ---
    secret_key: str = "dev-only-change-me"
    api_key: str = "change-me-local-dev-key"
    rate_limit_requests_per_minute: int = 60

    # --- Document ingestion ---
    max_document_bytes: int = 500 * 1024 * 1024  # 500 MB

    # --- Web search (post-Step-16 amendment: Web-Augmented Knowledge) ---
    web_search_enabled: bool = False
    tavily_api_key: str = ""
    web_search_max_results: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()


