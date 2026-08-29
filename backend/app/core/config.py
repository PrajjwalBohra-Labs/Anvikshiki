from enum import Enum
from typing import Any, Literal, Optional
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
    TEST_DATABASE_URL: str = "sqlite+aiosqlite:///./data/test.sqlite3"
    
    # Storage / Filesystem
    STORAGE_LOCAL_ROOT: str = "data/originals"
    EXTRACTED_LOCAL_ROOT: str = "data/extracted"
    OCR_LOCAL_ROOT: str = "data/OCR"
    CACHE_LOCAL_ROOT: str = "data/cached_web"
    EXPORTS_LOCAL_ROOT: str = "data/exports"
    TEMPORARY_LOCAL_ROOT: str = "data/temporary"

    # Local AI Inference
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = Field(default="mistral")
    VLLM_BASE_URL: Optional[str] = None  # Optional advanced runtime
    
    # Embeddings & Reranking
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_PROVIDER: str = "sentence-transformers"
    EMBEDDING_DIMENSIONS: int = Field(default=384, ge=1, le=4096)
    EMBEDDING_BATCH_SIZE: int = Field(default=32, ge=1, le=512)
    # Conservative PostgreSQL parser for scholarly terminology. ``simple``
    # tokenizes without English stemming or stop words.
    LEXICAL_SEARCH_CONFIG: Literal["simple"] = "simple"
    LEXICAL_MAX_QUERY_LENGTH: int = Field(default=1000, ge=1, le=10_000)
    LEXICAL_DEFAULT_LIMIT: int = Field(default=10, ge=1, le=100)
    LEXICAL_MAX_RESULTS: int = Field(default=100, ge=1, le=1000)
    # Hybrid retrieval uses rank-aware fusion because lexical rank and vector
    # similarity are not comparable raw scores.  The candidate limits are
    # intentionally separate from the public top_k result limit.
    HYBRID_LEXICAL_WEIGHT: float = Field(default=1.0, ge=0, le=10)
    HYBRID_SEMANTIC_WEIGHT: float = Field(default=1.0, ge=0, le=10)
    HYBRID_LEXICAL_CANDIDATE_LIMIT: int = Field(default=30, ge=1, le=500)
    HYBRID_SEMANTIC_CANDIDATE_LIMIT: int = Field(default=30, ge=1, le=500)
    HYBRID_RRF_K: int = Field(default=60, ge=1, le=1000)
    RERANKER_ENABLED: bool = True
    RERANKER_CANDIDATE_MULTIPLIER: int = Field(default=2, ge=1, le=10)
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    
    # Subsystems Toggles
    ENABLE_OCR: bool = True
    OCR_TESSERACT_CMD: Optional[str] = None
    OCR_LANGUAGES: str = "eng"
    OCR_DPI: int = Field(default=300, ge=72, le=600)
    OCR_TIMEOUT_SECONDS: float = Field(default=120.0, gt=0, le=600)
    ENABLE_WEB_RETRIEVAL: bool = True
    WEB_RETRIEVAL_MAX_RESULTS: int = Field(default=5, ge=1, le=20)
    WEB_MAX_RESPONSE_BYTES: int = Field(default=5_000_000, ge=1_024, le=50_000_000)
    WEB_REQUEST_TIMEOUT_SECONDS: float = Field(default=20.0, gt=0, le=120)
    ENABLE_MCP_SERVER: bool = False
    
    # Frontend/CORS
    FRONTEND_URL: str = "http://localhost:5173"

    # Authentication is mandatory outside the explicit test profile. The
    # test harness may opt into AUTH_MODE=test for isolated legacy tests.
    AUTH_MODE: Literal["required", "test"] = "required"
    AUTH_TOKEN_TTL_MINUTES: int = Field(default=1_440, ge=5, le=43_200)

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
