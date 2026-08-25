from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

# --- Dialogue & Conversation Schemas ---
class CitationDTO(BaseModel):
    passage_id: str
    source_title: str
    page_number: Optional[int] = None
    extracted_text: str

class MessageCreateDTO(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., min_length=1)
    research_run_id: Optional[str] = None
    citations: Optional[List[Dict[str, Any]]] = None

class MessageResponseDTO(BaseModel):
    message_id: str
    role: str
    content: str
    research_run_id: Optional[str] = None
    citations: List[Dict[str, Any]] = []
    created_at: datetime

class ConversationCreateDTO(BaseModel):
    user_id: str
    title: Optional[str] = "New Research Dialogue"

class ConversationResponseDTO(BaseModel):
    conversation_id: str
    title: Optional[str]
    created_at: datetime
    messages: List[MessageResponseDTO] = []

class DialogueTurnRequestDTO(BaseModel):
    user_utterance: str = Field(..., min_length=1)
    dialogue_mode: str = Field("socratic", description="socratic, challenge, explanation, counterexample, debate, reflective")
    evidence_passage_id: Optional[str] = None
    user_mastery_demonstrated: bool = False

class DialogueTurnResponseDTO(BaseModel):
    response_text: str
    dialogue_mode: str
    disagrees_with_user: bool
    evidence_linked: bool
    preserves_uncertainty: bool
    source_title: Optional[str] = None

# --- Epistemic Memory Schemas ---
class EpistemicPositionCreateDTO(BaseModel):
    user_id: str
    claim_statement: str = Field(..., min_length=5)
    position: str = Field(..., description="tentative, accepted, rejected, contested, under investigation, unresolved")
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    supporting_evidence: Optional[List[Dict[str, Any]]] = None
    counterarguments: Optional[List[Dict[str, Any]]] = None
    status: str = "tentative"

class EpistemicPositionUpdateDTO(BaseModel):
    new_status: str
    change_reason: Optional[str] = None

class EpistemicPositionResponseDTO(BaseModel):
    position_id: str
    claim_statement: str
    position: str
    confidence: float
    status: str
    supporting_evidence: Optional[List[Dict[str, Any]]] = []
    counterarguments: Optional[List[Dict[str, Any]]] = []
    updated_at: datetime
    history: List[Dict[str, Any]] = []

# --- Research & Continuity Schemas ---
class ResearchRunRequestDTO(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    query: str = Field(..., min_length=3, max_length=10_000)
    domain: Optional[str] = Field("Philosophy & Empirical Epistemology", max_length=128)
    depth: Optional[str] = "standard"

class ResearchResumeRequestDTO(BaseModel):
    research_question_id: str = Field(..., min_length=1, max_length=128)
    user_id: str = Field(..., min_length=1, max_length=128)

class ResearchContinuityResponseDTO(BaseModel):
    research_question_id: str
    main_question: str
    subquestions: List[str]
    scope: Optional[str]
    domain: Optional[str]
    research_status: str
    established_findings: List[str]
    unresolved_questions: List[str]
    user_positions: List[Dict[str, Any]]
    evidence_trail: List[Dict[str, Any]]
    research_timeline: List[Dict[str, Any]]
    suggested_next_step: str
