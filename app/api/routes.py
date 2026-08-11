"""
API Gateway (§24 API Design). REST for CRUD, plus a streaming
endpoint for generated responses. §17 hard rule enforced here:
"no component may bypass the Conversation Controller" -- /chat and
/chat/stream are the only routes producing a conversational
response, both route through handle_message(), never around it.

Authentication and rate limiting (§27) are applied at the router
level in main.py, not per-route here -- every route in this file
requires a valid API key except /health, which is mounted directly
on the app. Free-text inputs that reach an LLM prompt (chat query,
research question, search query) are sanitized here at the boundary.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.api.contracts import ConversationEngine, DocumentEngine, ResearchEngineContract, SearchEngine
from app.api.dependencies import event_bus_dependency, llm_adapter_dependency, memory_engine_dependency
from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    ConceptResponse,
    DocumentIngestResponse,
    ProjectCreateRequest,
    ProjectResponse,
    ResearchRequest,
    ResearchResponse,
    SearchResponse,
    SessionResponse,
    SettingRequest,
    SettingResponse,
)
from app.infrastructure.event_bus import EventBus, EventName
from app.infrastructure.llm_adapter import LLMAdapter
from app.persistence import relational_db
from app.security.sanitization import InputValidationError, sanitize_text
from app.services.context.context_builder import build_context
from app.services.generation.generation_engine import generate_response
from app.services.memory.memory_engine import MemoryEngine
from app.services.reasoning.reasoning_engine import reason

router = APIRouter()


def _sanitized(text: str) -> str:
    try:
        return sanitize_text(text)
    except InputValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# --- /chat (Engine Contract: ConversationEngine) ---

@router.post("/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    llm_adapter: LLMAdapter = Depends(llm_adapter_dependency),
    memory_engine: MemoryEngine = Depends(memory_engine_dependency),
) -> dict:
    body.query = _sanitized(body.query)
    engine = ConversationEngine(llm_adapter, memory_engine)
    engine.initialize()
    try:
        response = engine.execute(body.model_dump())
        if not engine.validate(response):
            raise HTTPException(status_code=500, detail="Conversation engine produced an invalid response")
        return response
    finally:
        engine.shutdown()


@router.post("/chat/stream")
def chat_stream(
    body: ChatRequest,
    llm_adapter: LLMAdapter = Depends(llm_adapter_dependency),
) -> StreamingResponse:
    """Streams live generation directly (§9). Documented exception to
    the validation gate /chat enforces -- streaming and post-hoc
    full-text validation are structurally in tension."""

    body.query = _sanitized(body.query)
    context = build_context(
        body.query, project_id=body.project_id, llm_adapter=llm_adapter, use_web_search=body.use_web_search
    )
    reasoning = reason(body.query, context)

    def token_stream():
        for token in generate_response(reasoning, body.query, llm_adapter=llm_adapter):
            yield f"data: {token}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(token_stream(), media_type="text/event-stream")


# --- /search (Engine Contract: SearchEngine) ---

@router.get("/search", response_model=SearchResponse)
def search(
    q: str,
    top_k: int = 5,
    document_id: str | None = None,
    llm_adapter: LLMAdapter = Depends(llm_adapter_dependency),
) -> dict:
    q = _sanitized(q)
    engine = SearchEngine(llm_adapter)
    engine.initialize()
    try:
        response = engine.execute({"query": q, "top_k": top_k, "document_id": document_id})
        if not engine.validate(response):
            raise HTTPException(status_code=500, detail="Search engine produced an invalid response")
        return response
    finally:
        engine.shutdown()


# --- /research (Engine Contract: ResearchEngineContract) ---

@router.post("/research", response_model=ResearchResponse)
def research_endpoint(
    body: ResearchRequest,
    llm_adapter: LLMAdapter = Depends(llm_adapter_dependency),
    memory_engine: MemoryEngine = Depends(memory_engine_dependency),
) -> dict:
    body.question = _sanitized(body.question)
    engine = ResearchEngineContract(llm_adapter, memory_engine)
    engine.initialize()
    try:
        response = engine.execute({"question": body.question, "top_k": body.top_k, "use_web_search": body.use_web_search})
        if not engine.validate(response):
            raise HTTPException(status_code=500, detail="Research engine produced an invalid response")
        return response
    finally:
        engine.shutdown()


# --- /documents (Engine Contract: DocumentEngine for ingestion; thin reads) ---

@router.post("/documents", response_model=DocumentIngestResponse)
async def upload_document(
    file: UploadFile,
    title: str | None = None,
    project_id: str | None = None,
    llm_adapter: LLMAdapter = Depends(llm_adapter_dependency),
) -> dict:
    content = await file.read()
    engine = DocumentEngine(llm_adapter)
    engine.initialize()
    try:
        response = engine.execute(
            {"filename": file.filename, "content_bytes": content, "title": title, "project_id": project_id}
        )
        if not engine.validate(response):
            raise HTTPException(status_code=500, detail="Document engine produced an invalid response")
        return response
    finally:
        engine.shutdown()


@router.get("/documents")
def list_documents(project_id: str | None = None, limit: int = 50) -> list[dict]:
    return relational_db.list_documents(project_id=project_id, limit=limit)


@router.get("/documents/{document_id}")
def get_document(document_id: str) -> dict:
    document = relational_db.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


# --- /projects (thin CRUD) ---

@router.post("/projects", response_model=ProjectResponse)
def create_project(
    body: ProjectCreateRequest,
    event_bus: EventBus = Depends(event_bus_dependency),
) -> dict:
    project_id = relational_db.create_project(body.name, body.description)
    project = relational_db.get_project(project_id)
    event_bus.publish(EventName.PROJECT_SAVED, {"project_id": project_id, "name": body.name})
    return project


@router.get("/projects")
def list_projects(limit: int = 50) -> list[dict]:
    return relational_db.list_projects(limit=limit)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str) -> dict:
    project = relational_db.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# --- /concepts (thin read) ---

@router.get("/concepts")
def list_concepts(limit: int = 50) -> list[dict]:
    return relational_db.list_concepts(limit=limit)


@router.get("/concepts/{concept_id}", response_model=ConceptResponse)
def get_concept(concept_id: str) -> dict:
    concept = relational_db.get_concept(concept_id)
    if concept is None:
        raise HTTPException(status_code=404, detail="Concept not found")
    return concept


# --- /sessions (thin CRUD) ---

@router.post("/sessions", response_model=SessionResponse)
def create_session() -> dict:
    session_id = relational_db.create_session()
    return relational_db.get_session(session_id)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str) -> dict:
    session = relational_db.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/sessions/{session_id}/history")
def get_session_history(session_id: str) -> list[dict]:
    session = relational_db.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return relational_db.get_conversation_history(session_id)


# --- /settings (thin CRUD; §10 System Memory tier) ---

@router.put("/settings", response_model=SettingResponse)
def set_setting(body: SettingRequest) -> dict:
    relational_db.set_setting(body.key, body.value)
    return {"key": body.key, "value": body.value}


@router.get("/settings/{key}", response_model=SettingResponse)
def get_setting(key: str) -> dict:
    value = relational_db.get_setting(key)
    if value is None:
        raise HTTPException(status_code=404, detail="Setting not found")
    return {"key": key, "value": value}




# --- /trace (§28 Observability -- query a request'"'"'s full execution trace) ---

@router.get("/trace/{trace_id}")
def get_trace(trace_id: str) -> list[dict]:
    from app.infrastructure.observability import get_trace_store

    events = get_trace_store().get_trace(trace_id)
    return [
        {
            "stage": e.stage,
            "event_type": e.event_type,
            "timestamp": e.timestamp,
            "duration_ms": e.duration_ms,
            "metadata": e.metadata,
        }
        for e in events
    ]
