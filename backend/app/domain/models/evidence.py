from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from backend.app.domain.models.enums import SourceType, ClaimType, EvidenceStatus, PramanaType

class SourceProvenance(BaseModel):
    author: Optional[str] = None
    historical_era: Optional[str] = None
    original_language: Optional[str] = None
    translator: Optional[str] = None
    translation_year: Optional[int] = None
    institutional_context: Optional[str] = None
    citation_string: str
    url: Optional[str] = None

class Passage(BaseModel):
    id: str
    document_id: str
    page_number: Optional[int] = None
    section_heading: Optional[str] = None
    content: str
    source_type: SourceType
    ocr_confidence: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    extraction_uncertainty: bool = False
    language: str = "en"

class Claim(BaseModel):
    id: str
    statement: str
    claim_type: ClaimType
    pramana_type: Optional[PramanaType] = None
    supporting_passage_ids: List[str] = Field(default_factory=list)
    contradicting_passage_ids: List[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    status: EvidenceStatus = EvidenceStatus.UNRESOLVED

class EpistemicState(BaseModel):
    claim_id: str
    user_position: str
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    counterargument_ids: List[str] = Field(default_factory=list)
    status: str = "under_investigation"
    last_updated: datetime = Field(default_factory=datetime.utcnow)
