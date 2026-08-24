from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, field_validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    PROJECT_NAME: str = "Anvikshiki"
    ENV: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/anvikshiki_db"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "anvikshiki_db"

    # Local AI Runtime
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "mistral"
    EMBEDDING_MODEL: str = "nomic-embed-text"

    # Storage Paths
    STORAGE_LOCAL_ROOT: str = "data/originals"
    EXTRACTED_LOCAL_ROOT: str = "data/extracted"
    OCR_LOCAL_ROOT: str = "data/ocr"
    CACHE_LOCAL_ROOT: str = "data/cached_web"

settings = Settings()
