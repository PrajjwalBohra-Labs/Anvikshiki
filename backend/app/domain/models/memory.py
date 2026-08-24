from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class CognitiveObservation(BaseModel):
    id: str
    pattern_name: str
    description: str
    evidence_dialogue_turn: str
    confidence: float = Field(ge=0.0, le=1.0)
    observed_at: datetime = Field(default_factory=utc_now)

class LearningEvent(BaseModel):
    id: str
    concept: str
    previous_understanding: Optional[str] = None
    demonstrated_understanding: str
    evidence_passage_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=utc_now)

class MisconceptionRecord(BaseModel):
    id: str
    concept: str
    misconception_statement: str
    corrective_evidence_id: Optional[str] = None
    is_resolved: bool = False
    first_detected_at: datetime = Field(default_factory=utc_now)
    resolved_at: Optional[datetime] = None