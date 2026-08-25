from enum import Enum
from typing import Any, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class RuntimeProfile(str, Enum):
    CPU = "cpu"
    GPU = "gpu"
    DEVELOPMENT = "development"
    TEST = "test"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        env_ignore_empty=True,
    )

    # Core System
    PROJECT_NAME: str = "Anvikshiki"
    ENV: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"
    RUNTIME_PROFILE: RuntimeProfile = RuntimeProfile.DEVELOPMENT

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/anvikshiki_db"
    TEST_DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"
    
    # Storage / Filesystem
    STORAGE_LOCAL_ROOT: str = "data/originals"
    EXTRACTED_LOCAL_ROOT: str = "data/extracted"
    OCR_LOCAL_ROOT: str = "data/OCR"
    CACHE_LOCAL_ROOT: str = "data/cached_web"

    # Local AI Inference
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = Field(default="mistral")
    VLLM_BASE_URL: Optional[str] = None  # Optional advanced runtime
    
    # Embeddings & Reranking
    EMBEDDING_MODEL: str = "nomic-embed-text"
    RERANKER_MODEL: str = "bge-reranker-base"
    
    # Subsystems Toggles
    ENABLE_OCR: bool = True
    ENABLE_WEB_RETRIEVAL: bool = True
    WEB_RETRIEVAL_MAX_RESULTS: int = Field(default=5, ge=1, le=20)
    ENABLE_MCP_SERVER: bool = False
    
    # Frontend/CORS
    FRONTEND_URL: str = "http://localhost:5173"

    @field_validator("OLLAMA_MODEL", mode="after")
    @classmethod
    def validate_cpu_model_limits(cls, v: str, info) -> str:
        # Graceful degradation: if forced to CPU profile, suggest avoiding massive parameter models
        profile = info.data.get("RUNTIME_PROFILE")
        if profile == RuntimeProfile.CPU and "70b" in v.lower():
            raise ValueError("CPU profile active: 70B parameter models are not supported without GPU.")
        return v

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug_value(cls, value: Any) -> Any:
        """Accept the deployment label ``release`` as the non-debug mode.

        Some process managers expose their deployment channel through DEBUG.
        ``release`` is therefore treated explicitly as ``False``; all other
        values remain subject to Pydantic's normal boolean validation.
        """
        if isinstance(value, str) and value.strip().lower() in {"release", "production", "prod"}:
            return False
        return value

settings = Settings()
