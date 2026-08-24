from typing import List, Optional
from pydantic import BaseModel, Field
from backend.app.domain.models.source import generate_id, utc_now
from datetime import datetime

class Concept(BaseModel):
    id: str = Field(default_factory=generate_id)
    term: str
    original_language_term: Optional[str] = None
    definitions: List[str] = Field(default_factory=list)

class ResearchQuestion(BaseModel):
    id: str = Field(default_factory=generate_id)
    user_id: str
    main_question: str
    sub_questions: List[str] = Field(default_factory=list)
    status: str = "open"
    created_at: datetime = Field(default_factory=utc_now)

class BeliefState(BaseModel):
    id: str = Field(default_factory=generate_id)
    user_id: str
    claim_id: str
    user_position: str
    confidence: float = Field(ge=0.0, le=1.0)
    status: str = "under_investigation"
    last_updated: datetime = Field(default_factory=utc_now)

class CognitiveObservation(BaseModel):
    id: str = Field(default_factory=generate_id)
    user_id: str
    pattern_name: str
    description: str
    evidence_context: str
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    observed_at: datetime = Field(default_factory=utc_now)