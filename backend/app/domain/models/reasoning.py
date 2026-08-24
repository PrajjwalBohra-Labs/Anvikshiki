from typing import List, Optional
from pydantic import BaseModel, Field
from backend.app.domain.models.enums import ClaimType, PramanaType, RelationType, EvidenceStatus
from backend.app.domain.models.source import generate_id, utc_now
from datetime import datetime

class Claim(BaseModel):
    id: str = Field(default_factory=generate_id)
    statement: str
    claim_type: ClaimType
    pramana_type: Optional[PramanaType] = None
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    status: EvidenceStatus = EvidenceStatus.UNRESOLVED

class Evidence(BaseModel):
    id: str = Field(default_factory=generate_id)
    claim_id: str
    passage_id: str
    relation_type: RelationType
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

class Argument(BaseModel):
    id: str = Field(default_factory=generate_id)
    conclusion_claim_id: str
    premise_claim_ids: List[str]
    pramana_type: Optional[PramanaType] = None
    counter_argument_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)