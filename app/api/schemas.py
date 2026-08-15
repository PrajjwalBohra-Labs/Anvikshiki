"""API request/response schemas (§24)."""

from __future__ import annotations

from pydantic import BaseModel


class ChatRequest(BaseModel):
    query: str
    session_id: str | None = None
    project_id: str | None = None
    use_web_search: bool = False


class VerificationSummary(BaseModel):
    sources_checked: int
    evidence_count: int
    contradictions_detected: int
    agreement_score: float | None
    confidence: float | None


class ChatResponse(BaseModel):
    session_id: str
    response: str | None
    delivered: bool
    confidence: float | None
    state_trace: list[str]
    verification: VerificationSummary | None = None


class SearchResultItem(BaseModel):
    chunk_id: str
    document_id: str | None
    document_title: str | None
    chunk_text: str
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResultItem]


class ResearchRequest(BaseModel):
    question: str
    top_k: int = 5
    use_web_search: bool = False


class ResearchResponse(BaseModel):
    question: str
    sub_questions: list[str]
    synthesized_answer: str
    references: list[dict]
    delivered: bool
    validation_violations: list[str]


class DocumentIngestResponse(BaseModel):
    document_id: str
    concept_id: str
    chunk_count: int


class ProjectCreateRequest(BaseModel):
    name: str
    description: str = ""


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str | None


class ConceptResponse(BaseModel):
    id: str
    name: str
    description: str | None


class SessionResponse(BaseModel):
    id: str
    status: str


class SettingRequest(BaseModel):
    key: str
    value: str


class SettingResponse(BaseModel):
    key: str
    value: str



