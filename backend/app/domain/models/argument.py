from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from backend.app.domain.models.enums import PramanaType, ClaimType, EvidenceStatus

class InferenceRelation(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    QUALIFIES = "qualifies"
    INDEPENDENT = "independent"

class HetvabhasaType(str, Enum):
    SABHYABHICARA = "savyabhicara"  # Inconclusive/irregular reason
    VIRUDDHA = "viruddha"          # Contradictory reason
    SATPRATIPAKSHA = "satpratipaksha"# Counterbalanced reason
    ASIDDHA = "asiddha"            # Unproved reason
    BADHITA = "badhita"            # Annulled/sublated reason
    NONE = "none"

class Argument(BaseModel):
    id: str
    conclusion: str
    premises: List[str]
    pramana: Optional[PramanaType] = None
    vyapti_warrant: Optional[str] = None  # Invariable concomitance
    fallacy_detected: HetvabhasaType = HetvabhasaType.NONE
    supporting_claim_ids: List[str] = Field(default_factory=list)
    counter_argument_ids: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)