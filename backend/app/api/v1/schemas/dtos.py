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

class ResearchQuestionSummaryResponseDTO(BaseModel):
    question_id: str
    user_id: Optional[str] = None
    main_question: str
    domain: Optional[str] = None
    research_status: str
    created_at: datetime
    run_ids: List[str] = []

class ResearchQuestionDetailResponseDTO(ResearchQuestionSummaryResponseDTO):
    subquestions: List[str] = []
    scope: Optional[str] = None
    constraints: List[str] = []
    user_position: Optional[str] = None
    open_questions: List[str] = []

# --- Public research result contracts ---
class ResearchStepResponseDTO(BaseModel):
    step_name: str
    step_type: str
    status: str
    payload: Optional[Dict[str, Any]] = None
    event_id: Optional[str] = None
    event_sequence: Optional[int] = None
    created_at: datetime

class ResearchPassageResponseDTO(BaseModel):
    passage_id: str
    source_id: Optional[str] = None
    source_title: str
    content: str
    page_number: Optional[int] = None
    source_type: Optional[str] = None
    retrieval_channels: List[str] = []

class ValidatedClaimResponseDTO(BaseModel):
    claim_id: Optional[str] = None
    statement: str
    claim_type: Optional[str] = None
    passage_id: Optional[str] = None
    source_title: Optional[str] = None
    confidence: float = 0.0
    is_verified: bool = False
    reason: Optional[str] = None

class SpecialistAnalysisResponseDTO(BaseModel):
    philosophical_arguments: List[Dict[str, Any]] = []
    source_criticisms: List[Dict[str, Any]] = []
    scientific_analyses: List[Dict[str, Any]] = []
    comparisons: List[Dict[str, Any]] = []
    challenges: List[Dict[str, Any]] = []

class ResearchResultResponseDTO(BaseModel):
    run_id: str
    query: str
    domain: Optional[str] = None
    validation_status: str
    final_response: str
    validated_claims_count: int
    retrieved_passages: List[ResearchPassageResponseDTO] = []
    claims: List[ValidatedClaimResponseDTO] = []
    specialist_analysis: SpecialistAnalysisResponseDTO = SpecialistAnalysisResponseDTO()
    validation: Dict[str, Any] = {}

class ResearchRunSummaryResponseDTO(BaseModel):
    run_id: str
    research_question_id: Optional[str] = None
    thread_id: Optional[str] = None
    user_id: Optional[str] = None
    query: str
    domain: Optional[str] = None
    depth: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None

class ResearchRunDetailResponseDTO(ResearchRunSummaryResponseDTO):
    output_references: Optional[Dict[str, Any]] = None
    steps: List[ResearchStepResponseDTO] = []
    result: Optional[ResearchResultResponseDTO] = None

class ResearchRunExecutionResponseDTO(BaseModel):
    run_id: str
    research_question_id: Optional[str] = None
    status: str
    query: str
    final_response: str
    validated_claims: List[Dict[str, Any]] = []
    retrieved_passages_count: int
    safe_events: List[Dict[str, Any]] = []
    result: ResearchResultResponseDTO

class ResearchEventResponseDTO(BaseModel):
    event_id: str
    sequence: int
    run_id: str
    event: str
    payload: Dict[str, Any]

# --- Public claim/evidence/provenance contracts ---
class EvidenceLinkResponseDTO(BaseModel):
    evidence_link_id: str
    claim_id: Optional[str] = None
    premise_id: Optional[str] = None
    passage_id: str
    relation_type: str
    confidence_weight: float

class ClaimEvidenceResponseDTO(BaseModel):
    claim_id: str
    statement: str
    claim_type: str
    provenance_id: Optional[str] = None
    confidence: float
    lifecycle_status: str
    evidence_links: List[EvidenceLinkResponseDTO] = []

class SourceProvenanceResponseDTO(BaseModel):
    source_id: str
    title: str
    author: Optional[str] = None
    historical_era: Optional[str] = None
    original_language: Optional[str] = None
    source_type: str
    reference_url: Optional[str] = None

class DocumentProvenanceResponseDTO(BaseModel):
    document_id: str
    source_id: str
    checksum_sha256: str
    mime_type: str
    original_filename: Optional[str] = None
    total_pages: Optional[int] = None

class PassageProvenanceResponseDTO(BaseModel):
    passage_id: str
    document_id: str
    page_number: Optional[int] = None
    content: str
    ocr_confidence: Optional[float] = None
    extraction_uncertainty: bool
    language: str

class EvidenceTraceResponseDTO(BaseModel):
    evidence_link_id: str
    claim_id: Optional[str] = None
    premise_id: Optional[str] = None
    relation_type: str
    confidence_weight: float
    passage: PassageProvenanceResponseDTO
    document: DocumentProvenanceResponseDTO
    source: SourceProvenanceResponseDTO
    source_lineage: List[Dict[str, Any]] = []

# --- Public document and acquisition contracts ---
class SourceResponseDTO(BaseModel):
    id: str
    title: str
    author: Optional[str] = None
    historical_era: Optional[str] = None
    original_language: Optional[str] = None
    source_type: str
    reference_url: Optional[str] = None

class DocumentResponseDTO(BaseModel):
    document_id: str
    source_id: str
    checksum_sha256: str
    mime_type: str
    original_filename: Optional[str] = None
    total_pages: Optional[int] = None
    created_at: datetime
    passages_count: int

class WebAcquisitionRequestDTO(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)
    source_title: Optional[str] = Field(default=None, max_length=512)

class WebAcquisitionResponseDTO(BaseModel):
    source: SourceResponseDTO
    document: DocumentResponseDTO

# --- Local identity lifecycle contract ---
class UserCreateDTO(BaseModel):
    username: str = Field(..., min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")

class UserResponseDTO(BaseModel):
    user_id: str
    username: str
    created_at: datetime
    access_token: Optional[str] = None
