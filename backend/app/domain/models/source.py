from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field
from uuid import uuid4

from backend.app.domain.models.enums import SourceType

def generate_id() -> str:
    return str(uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class Source(BaseModel):
    id: str = Field(default_factory=generate_id)
    title: str
    author: Optional[str] = None
    historical_era: Optional[str] = None
    original_language: Optional[str] = None
    source_type: SourceType = SourceType.UNVERIFIED
    created_at: datetime = Field(default_factory=utc_now)

class Document(BaseModel):
    id: str = Field(default_factory=generate_id)
    source_id: str
    checksum_sha256: str
    mime_type: str
    total_pages: Optional[int] = None
    created_at: datetime = Field(default_factory=utc_now)

class Passage(BaseModel):
    id: str = Field(default_factory=generate_id)
    document_id: str
    page_number: Optional[int] = None
    content: str
    ocr_confidence: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    extraction_uncertainty: bool = False
    language: str = "en"

class Citation(BaseModel):
    id: str = Field(default_factory=generate_id)
    passage_id: str
    source_id: str
    citation_string: str