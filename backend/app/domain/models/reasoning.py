from datetime import datetime

from pydantic import BaseModel, Field

from backend.app.domain.models.enums import (
    ClaimType,
    EvidenceStatus,
    PramanaType,
    RelationType,
)
from backend.app.domain.models.source import generate_id, utc_now


class Claim(BaseModel):
    id: str = Field(default_factory=generate_id)
    statement: str
    claim_type: ClaimType
    pramana_type: PramanaType | None = None
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
    premise_claim_ids: list[str]
    pramana_type: PramanaType | None = None
    counter_argument_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)