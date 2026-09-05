from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.app.domain.models.enums import SourceType


def generate_id() -> str:
    return str(uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class Source(BaseModel):
    id: str = Field(default_factory=generate_id)
    title: str
    author: str | None = None
    historical_era: str | None = None
    original_language: str | None = None
    source_type: SourceType = SourceType.UNVERIFIED
    created_at: datetime = Field(default_factory=utc_now)

class Document(BaseModel):
    id: str = Field(default_factory=generate_id)
    source_id: str
    checksum_sha256: str
    mime_type: str
    total_pages: int | None = None
    created_at: datetime = Field(default_factory=utc_now)

class Passage(BaseModel):
    id: str = Field(default_factory=generate_id)
    document_id: str
    page_number: int | None = None
    content: str
    ocr_confidence: float | None = Field(default=1.0, ge=0.0, le=1.0)
    extraction_uncertainty: bool = False
    language: str = "en"

class Citation(BaseModel):
    id: str = Field(default_factory=generate_id)
    passage_id: str
    source_id: str
    citation_string: str