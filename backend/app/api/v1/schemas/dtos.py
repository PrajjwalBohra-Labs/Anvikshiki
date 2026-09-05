from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# --- Dialogue & Conversation Schemas ---
class CitationDTO(BaseModel):
    passage_id: str
    source_title: str
    page_number: int | None = None
    extracted_text: str

class MessageCreateDTO(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., min_length=1)
    research_run_id: str | None = None
    citations: list[dict[str, Any]] | None = None

class MessageResponseDTO(BaseModel):
    message_id: str
    role: str
    content: str
    research_run_id: str | None = None
    citations: list[dict[str, Any]] = []
    created_at: datetime

class ConversationCreateDTO(BaseModel):
    user_id: str
    title: str | None = "New Research Dialogue"

class ConversationResponseDTO(BaseModel):
    conversation_id: str
    title: str | None
    created_at: datetime
    messages: list[MessageResponseDTO] = []


# --- Notebook contract ---
class NotebookCreateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=256)
    content: str = Field(default="", max_length=100_000)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Notebook title cannot be blank.")
        return cleaned


class NotebookUpdateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = Field(default=None, min_length=1, max_length=256)
    content: Optional[str] = Field(default=None, max_length=100_000)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Notebook title cannot be blank.")
        return cleaned

    @model_validator(mode="after")
    def require_change(self):
        if self.title is None and self.content is None:
            raise ValueError("At least one notebook field must be provided.")
        return self


class NotebookResponseDTO(BaseModel):
    notebook_id: str
    title: str
    content: str
    created_at: datetime
    updated_at: datetime

class DialogueTurnRequestDTO(BaseModel):
    user_utterance: str = Field(..., min_length=1)
    dialogue_mode: str = Field("socratic", description="socratic, challenge, explanation, counterexample, debate, reflective")
    evidence_passage_id: str | None = None
    user_mastery_demonstrated: bool = False

class DialogueTurnResponseDTO(BaseModel):
    response_text: str
    dialogue_mode: str
    disagrees_with_user: bool
    evidence_linked: bool
    preserves_uncertainty: bool
    source_title: str | None = None

# --- Epistemic Memory Schemas ---
class EpistemicPositionCreateDTO(BaseModel):
    user_id: str
    claim_statement: str = Field(..., min_length=5)
    position: str = Field(..., description="tentative, accepted, rejected, contested, under investigation, unresolved")
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    supporting_evidence: list[dict[str, Any]] | None = None
    counterarguments: list[dict[str, Any]] | None = None
    status: str = "tentative"

class EpistemicPositionUpdateDTO(BaseModel):
    new_status: str
    change_reason: str | None = None

class EpistemicPositionResponseDTO(BaseModel):
    position_id: str
    claim_statement: str
    position: str
    confidence: float
    status: str
    supporting_evidence: list[dict[str, Any]] | None = []
    counterarguments: list[dict[str, Any]] | None = []
    updated_at: datetime
    history: list[dict[str, Any]] = []

# --- Research & Continuity Schemas ---
class ResearchRunRequestDTO(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    query: str = Field(..., min_length=3, max_length=10_000)
<<<<<<< HEAD
    domain: Optional[str] = Field("Philosophy & Empirical Epistemology", max_length=128)
    depth: Optional[str] = "standard"
    include_web: bool = False
=======
    domain: str | None = Field("Philosophy & Empirical Epistemology", max_length=128)
    depth: str | None = "standard"
>>>>>>> origin/main

class ResearchResumeRequestDTO(BaseModel):
    research_question_id: str = Field(..., min_length=1, max_length=128)
    user_id: str = Field(..., min_length=1, max_length=128)

class ResearchContinuityResponseDTO(BaseModel):
    research_question_id: str
    main_question: str
    subquestions: list[str]
    scope: str | None
    domain: str | None
    research_status: str
    established_findings: list[str]
    unresolved_questions: list[str]
    user_positions: list[dict[str, Any]]
    evidence_trail: list[dict[str, Any]]
    research_timeline: list[dict[str, Any]]
    suggested_next_step: str

class ResearchQuestionSummaryResponseDTO(BaseModel):
    question_id: str
    user_id: str | None = None
    main_question: str
    domain: str | None = None
    research_status: str
    created_at: datetime
    run_ids: list[str] = []

class ResearchQuestionDetailResponseDTO(ResearchQuestionSummaryResponseDTO):
    subquestions: list[str] = []
    scope: str | None = None
    constraints: list[str] = []
    user_position: str | None = None
    open_questions: list[str] = []

# --- Public research result contracts ---
class ResearchStepResponseDTO(BaseModel):
    step_name: str
    step_type: str
    status: str
    payload: dict[str, Any] | None = None
    event_id: str | None = None
    event_sequence: int | None = None
    created_at: datetime

class ResearchPassageResponseDTO(BaseModel):
    passage_id: str
    source_id: str | None = None
    source_title: str
    content: str
    page_number: int | None = None
    source_type: str | None = None
    retrieval_channels: list[str] = []
    citation_string: str | None = None

class ValidatedClaimResponseDTO(BaseModel):
    claim_id: str | None = None
    statement: str
    claim_type: str | None = None
    passage_id: str | None = None
    source_title: str | None = None
    confidence: float = 0.0
    is_verified: bool = False
    reason: str | None = None

class SpecialistAnalysisResponseDTO(BaseModel):
    philosophical_arguments: list[dict[str, Any]] = []
    source_criticisms: list[dict[str, Any]] = []
    scientific_analyses: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    challenges: list[dict[str, Any]] = []

class ResearchResultResponseDTO(BaseModel):
    run_id: str
    query: str
    domain: str | None = None
    validation_status: str
    final_response: str
    validated_claims_count: int
    retrieved_passages: list[ResearchPassageResponseDTO] = []
    claims: list[ValidatedClaimResponseDTO] = []
    specialist_analysis: SpecialistAnalysisResponseDTO = SpecialistAnalysisResponseDTO()
<<<<<<< HEAD
    validation: Dict[str, Any] = {}
    web_research: Dict[str, Any] = {}
=======
    validation: dict[str, Any] = {}
    web_research: dict[str, Any] = {}
>>>>>>> origin/main

class ResearchRunSummaryResponseDTO(BaseModel):
    run_id: str
    research_question_id: str | None = None
    thread_id: str | None = None
    user_id: str | None = None
    query: str
    domain: str | None = None
    depth: str | None = None
    status: str
    error_message: str | None = None
    started_at: datetime
    finished_at: datetime | None = None

class ResearchRunDetailResponseDTO(ResearchRunSummaryResponseDTO):
    output_references: dict[str, Any] | None = None
    steps: list[ResearchStepResponseDTO] = []
    result: ResearchResultResponseDTO | None = None

class ResearchRunExecutionResponseDTO(BaseModel):
    run_id: str
    research_question_id: str | None = None
    status: str
    query: str
    final_response: str
    validated_claims: list[dict[str, Any]] = []
    retrieved_passages_count: int
    safe_events: list[dict[str, Any]] = []
    result: ResearchResultResponseDTO


class BackgroundResearchJobRequestDTO(BaseModel):
    """Research-only payload for durable background execution."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=3, max_length=10_000)
    domain: str | None = Field(default=None, max_length=128)
    depth: str | None = Field(default="standard", max_length=32)
    idempotency_key: str = Field(..., min_length=1, max_length=128)


class BackgroundJobResponseDTO(BaseModel):
    job_id: str
    job_type: str
    research_run_id: str | None = None
    status: str
    attempts: int
    max_attempts: int
    result: dict[str, Any] | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

class ResearchEventResponseDTO(BaseModel):
    event_id: str
    sequence: int
    run_id: str
    event: str
    payload: dict[str, Any]

# --- Public claim/evidence/provenance contracts ---
class EvidenceLinkResponseDTO(BaseModel):
    evidence_link_id: str
    claim_id: str | None = None
    premise_id: str | None = None
    passage_id: str
    relation_type: str
    confidence_weight: float

class ClaimEvidenceResponseDTO(BaseModel):
    claim_id: str
    statement: str
    claim_type: str
    provenance_id: str | None = None
    confidence: float
    lifecycle_status: str
    evidence_links: list[EvidenceLinkResponseDTO] = []

class SourceProvenanceResponseDTO(BaseModel):
    source_id: str
    title: str
    author: str | None = None
    historical_era: str | None = None
    original_language: str | None = None
    source_type: str
    reference_url: str | None = None

class DocumentProvenanceResponseDTO(BaseModel):
    document_id: str
    source_id: str
    checksum_sha256: str
    mime_type: str
    original_filename: str | None = None
    total_pages: int | None = None

class PassageProvenanceResponseDTO(BaseModel):
    passage_id: str
    document_id: str
    document_version_id: str | None = None
    page_id: str | None = None
    page_number: int | None = None
    passage_order: int | None = None
    content: str
    extraction_method: str | None = None
    section_heading: str | None = None
    ocr_confidence: float | None = None
    extraction_uncertainty: bool
    language: str

class ProvenanceNodeResponseDTO(BaseModel):
    node_id: str
    node_type: str
    entity_id: str
    label: str
    metadata: dict[str, Any] = {}
    created_at: datetime

class ProvenanceEdgeResponseDTO(BaseModel):
    edge_id: str
    from_node_id: str
    to_node_id: str
    relationship_type: str
    metadata: dict[str, Any] = {}
    created_at: datetime

class ProvenanceGraphResponseDTO(BaseModel):
    nodes: list[ProvenanceNodeResponseDTO] = []
    edges: list[ProvenanceEdgeResponseDTO] = []

class EvidenceTraceResponseDTO(BaseModel):
    evidence_link_id: str
    claim_id: str | None = None
    premise_id: str | None = None
    relation_type: str
    confidence_weight: float
    passage: PassageProvenanceResponseDTO
    document: DocumentProvenanceResponseDTO
    source: SourceProvenanceResponseDTO
    source_lineage: list[dict[str, Any]] = []
    graph_nodes: list[ProvenanceNodeResponseDTO] = []
    graph_edges: list[ProvenanceEdgeResponseDTO] = []


class ResearchExportResponseDTO(BaseModel):
    """Stable machine-readable export of one owned research record."""

    schema_version: str = "1.0"
    format: str = "json"
    research_run: ResearchRunDetailResponseDTO
    claims: list[ClaimEvidenceResponseDTO] = []
    provenance: list[EvidenceTraceResponseDTO] = []

# --- Public document and acquisition contracts ---
class SourceResponseDTO(BaseModel):
    id: str
    title: str
    author: str | None = None
    historical_era: str | None = None
    original_language: str | None = None
    source_type: str
    reference_url: str | None = None

class DocumentResponseDTO(BaseModel):
    document_id: str
    source_id: str
    checksum_sha256: str
    mime_type: str
    original_filename: str | None = None
    total_pages: int | None = None
    created_at: datetime
    passages_count: int

class WebAcquisitionRequestDTO(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)
    source_title: str | None = Field(default=None, max_length=512)

class WebSearchRequestDTO(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    max_results: int = Field(default=5, ge=1, le=20)

class WebSearchResultDTO(BaseModel):
    title: str
    url: str
    canonical_url: str
    snippet: str
    rank: int
    domain: str

class WebSearchResponseDTO(BaseModel):
    query: str
    results: list[WebSearchResultDTO]

class WebAcquisitionResponseDTO(BaseModel):
    source: SourceResponseDTO
    document: DocumentResponseDTO

# --- Local identity lifecycle contract ---
class UserCreateDTO(BaseModel):
    username: str = Field(..., min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")


class UsernameAuthenticationDTO(UserCreateDTO):
    """The username is the sole user-facing authentication input."""

class UserResponseDTO(BaseModel):
    user_id: str
    username: str
    created_at: datetime
<<<<<<< HEAD
    access_token: Optional[str] = None


class BackgroundResearchJobRequestDTO(BaseModel):
    """Research-only payload for durable background execution."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=3, max_length=10_000)
    domain: Optional[str] = Field(default=None, max_length=128)
    depth: Optional[str] = Field(default="standard", max_length=32)
    idempotency_key: str = Field(..., min_length=1, max_length=128)
    include_web: bool = False


class BackgroundJobResponseDTO(BaseModel):
    job_id: str
    job_type: str
    research_run_id: Optional[str] = None
    status: str
    attempts: int
    max_attempts: int
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
=======
    access_token: str | None = None
>>>>>>> origin/main
