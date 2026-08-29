import asyncio
import json
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.v1.schemas.dtos import (
    ClaimEvidenceResponseDTO,
    EvidenceTraceResponseDTO,
    ProvenanceGraphResponseDTO,
    ResearchResultResponseDTO,
    ResearchRunDetailResponseDTO,
    ResearchRunExecutionResponseDTO,
    ResearchRunRequestDTO,
    ResearchRunSummaryResponseDTO,
    ResearchResumeRequestDTO,
    ResearchContinuityResponseDTO,
    ResearchQuestionDetailResponseDTO,
    ResearchQuestionSummaryResponseDTO,
    SpecialistAnalysisResponseDTO,
)
from backend.app.api.dependencies import AuthenticatedPrincipal, get_current_user, resolve_user_id
from backend.app.application.orchestration.research_workflow import ResearchWorkflowEngine
from backend.app.application.use_cases.claim_service import ClaimService
from backend.app.application.use_cases.provenance import ProvenanceService
from backend.app.application.use_cases.research_continuity import ResearchContinuityService
from backend.app.application.use_cases.research_run_service import ResearchRunService
from backend.app.infrastructure.database.session import AsyncSessionLocal, get_db

router = APIRouter()


def _summary(run: Any) -> ResearchRunSummaryResponseDTO:
    return ResearchRunSummaryResponseDTO(
        run_id=run.id,
        research_question_id=run.research_question_id,
        thread_id=run.thread_id,
        user_id=run.user_id,
        query=run.query,
        domain=run.domain,
        depth=run.depth,
        status=run.status,
        error_message=run.error_message,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


def _result(run: Any) -> Optional[ResearchResultResponseDTO]:
    payload = run.output_references or {}
    if not payload or "final_response" not in payload:
        return None
    payload = {**payload, "run_id": run.id, "query": run.query, "domain": run.domain}
    return ResearchResultResponseDTO.model_validate(payload)


async def _detail(service: ResearchRunService, run: Any) -> ResearchRunDetailResponseDTO:
    details = await service.get_run_details(run.id)
    return ResearchRunDetailResponseDTO(
        **_summary(run).model_dump(),
        output_references=run.output_references,
        steps=details["steps"] if details else [],
        result=_result(run),
    )


async def _owned_run(service: ResearchRunService, run_id: str, user_id: str) -> Any:
    run = await service.get_owned_run(run_id, user_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found.")
    return run


def _event_payload(run_id: str, sequence: int, event: Dict[str, Any]) -> Dict[str, Any]:
    return {"event_id": f"{run_id}:{sequence}", "sequence": sequence, "run_id": run_id, **event}


def _event_sequence(event_id: Optional[str], run_id: str) -> int:
    if not event_id:
        return 0
    prefix = f"{run_id}:"
    if not event_id.startswith(prefix):
        raise HTTPException(status_code=400, detail="Last-Event-ID does not belong to this research run.")
    try:
        return int(event_id[len(prefix):])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Last-Event-ID is invalid.") from exc


@router.get("/runs", response_model=List[ResearchRunSummaryResponseDTO])
async def list_research_runs(
    user_id: Optional[str] = Query(default=None, min_length=1, max_length=128),
    status: Optional[str] = Query(default=None, max_length=32),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[AuthenticatedPrincipal] = Depends(get_current_user),
):
    owner_id = resolve_user_id(current_user, user_id)
    runs = await ResearchRunService(db).list_runs(user_id=owner_id, status=status, limit=limit, offset=offset)
    return [_summary(run) for run in runs]


def _question_summary(question: Any, run_ids: List[str]) -> ResearchQuestionSummaryResponseDTO:
    return ResearchQuestionSummaryResponseDTO(
        question_id=question.id,
        user_id=question.user_id,
        main_question=question.main_question,
        domain=question.domain,
        research_status=question.research_status,
        created_at=question.created_at,
        run_ids=run_ids,
    )


@router.get("/questions", response_model=List[ResearchQuestionSummaryResponseDTO])
async def list_research_questions(
    user_id: Optional[str] = Query(default=None, min_length=1, max_length=128),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[AuthenticatedPrincipal] = Depends(get_current_user),
):
    owner_id = resolve_user_id(current_user, user_id)
    service = ResearchRunService(db)
    questions = await service.list_questions(owner_id, limit=limit, offset=offset)
    return [_question_summary(question, await service.list_question_run_ids(question.id, owner_id)) for question in questions]


@router.get("/questions/{question_id}", response_model=ResearchQuestionDetailResponseDTO)
async def get_research_question(
    question_id: str,
    user_id: Optional[str] = Query(default=None, min_length=1, max_length=128),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[AuthenticatedPrincipal] = Depends(get_current_user),
):
    owner_id = resolve_user_id(current_user, user_id)
    service = ResearchRunService(db)
    question = await service.get_owned_question(question_id, owner_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Research question not found.")
    summary = _question_summary(question, await service.list_question_run_ids(question.id, owner_id))
    return ResearchQuestionDetailResponseDTO(
        **summary.model_dump(),
        subquestions=question.subquestions or [],
        scope=question.scope,
        constraints=question.constraints or [],
        user_position=question.user_position,
        open_questions=question.open_questions or [],
    )


@router.get("/runs/{run_id}", response_model=ResearchRunDetailResponseDTO)
async def get_research_run(
    run_id: str,
    user_id: Optional[str] = Query(default=None, min_length=1, max_length=128),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[AuthenticatedPrincipal] = Depends(get_current_user),
):
    service = ResearchRunService(db)
    run = await _owned_run(service, run_id, resolve_user_id(current_user, user_id))
    return await _detail(service, run)


@router.get("/runs/{run_id}/events")
async def replay_research_events(
    run_id: str,
    user_id: Optional[str] = Query(default=None, min_length=1, max_length=128),
    last_event_id: Optional[str] = Header(default=None, alias="Last-Event-ID"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[AuthenticatedPrincipal] = Depends(get_current_user),
):
    service = ResearchRunService(db)
    await _owned_run(service, run_id, resolve_user_id(current_user, user_id))
    after_sequence = _event_sequence(last_event_id, run_id)
    events = await service.list_events(run_id, after_sequence=after_sequence)

    async def generator() -> AsyncGenerator[str, None]:
        for record in events:
            payload = record.payload or {}
            event_id = record.event_id or f"{run_id}:{record.event_sequence or 0}"
            yield f"id: {event_id}\ndata: {json.dumps(payload, default=str)}\n\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/run", response_model=ResearchRunExecutionResponseDTO)
async def run_research(
    payload: ResearchRunRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[AuthenticatedPrincipal] = Depends(get_current_user),
):
    owner_id = resolve_user_id(current_user, payload.user_id)
    service = ResearchRunService(db)
    question = await service.create_question(payload.query, owner_id, payload.domain)
    run = await service.create_run(
        query=payload.query,
        user_id=owner_id,
        research_question_id=question.id,
        domain=payload.domain,
        depth=payload.depth,
    )
    engine = ResearchWorkflowEngine(session_or_factory=AsyncSessionLocal)
    try:
        result_state = await engine.execute_research(
            query=payload.query,
            user_id=owner_id,
            domain=payload.domain or "Epistemology",
            thread_id=run.thread_id or run.id,
            run_id=run.id,
        )
        result_payload = engine._result_payload(result_state)
        await service.complete_run(run.id, output_references=result_payload)
    except Exception as exc:
        await service.fail_run(run.id, str(exc))
        raise

    result = ResearchResultResponseDTO.model_validate(result_payload)
    completion_event = {
        "event": "research_completed",
        "event_id": f"{run.id}:1",
        "sequence": 1,
        "run_id": run.id,
        "status": result.validation_status,
        "validated_claims_count": result.validated_claims_count,
        "result": result_payload,
    }
    await service.record_event(run.id, completion_event, 1)
    return ResearchRunExecutionResponseDTO(
        run_id=run.id,
        research_question_id=question.id,
        status=result.validation_status,
        query=payload.query,
        final_response=result.final_response,
        validated_claims=result.validation.get("validated_claims", result.claims),
        retrieved_passages_count=len(result.retrieved_passages),
        safe_events=[completion_event],
        result=result,
    )


@router.post("/run/stream")
async def stream_research_events(
    payload: ResearchRunRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[AuthenticatedPrincipal] = Depends(get_current_user),
):
    owner_id = resolve_user_id(current_user, payload.user_id)
    service = ResearchRunService(db)
    question = await service.create_question(payload.query, owner_id, payload.domain)
    run = await service.create_run(
        query=payload.query,
        user_id=owner_id,
        research_question_id=question.id,
        domain=payload.domain,
        depth=payload.depth,
    )
    engine = ResearchWorkflowEngine(session_or_factory=AsyncSessionLocal)

    async def sse_generator() -> AsyncGenerator[str, None]:
        sequence = 0
        try:
            async for event in engine.stream_research_events(
                query=payload.query,
                user_id=owner_id,
                domain=payload.domain or "Epistemology",
                thread_id=run.thread_id or run.id,
                run_id=run.id,
            ):
                sequence += 1
                public_event = _event_payload(run.id, sequence, event)
                await service.record_event(run.id, public_event, sequence)
                if event.get("event") == "research_completed":
                    await service.complete_run(run.id, output_references=event.get("result") or {})
                yield f"id: {public_event['event_id']}\ndata: {json.dumps(public_event, default=str)}\n\n"
        except asyncio.CancelledError:
            await service.cancel_run(run.id)
            raise
        except Exception as exc:
            await service.fail_run(run.id, str(exc))
            sequence += 1
            error_event = _event_payload(
                run.id,
                sequence,
                {"event": "research_error", "error": "Research execution failed."},
            )
            await service.record_event(run.id, error_event, sequence)
            yield f"id: {error_event['event_id']}\ndata: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/runs/{run_id}/claims", response_model=List[ClaimEvidenceResponseDTO])
async def get_research_claims(
    run_id: str,
    user_id: Optional[str] = Query(default=None, min_length=1, max_length=128),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[AuthenticatedPrincipal] = Depends(get_current_user),
):
    await _owned_run(ResearchRunService(db), run_id, resolve_user_id(current_user, user_id))
    return await ClaimService(db).list_claims_for_run(run_id)


@router.get("/runs/{run_id}/analysis", response_model=SpecialistAnalysisResponseDTO)
async def get_research_analysis(
    run_id: str,
    user_id: Optional[str] = Query(default=None, min_length=1, max_length=128),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[AuthenticatedPrincipal] = Depends(get_current_user),
):
    run = await _owned_run(ResearchRunService(db), run_id, resolve_user_id(current_user, user_id))
    result = _result(run)
    return result.specialist_analysis if result else SpecialistAnalysisResponseDTO()


@router.get("/runs/{run_id}/provenance", response_model=List[EvidenceTraceResponseDTO])
async def get_research_provenance(
    run_id: str,
    user_id: Optional[str] = Query(default=None, min_length=1, max_length=128),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[AuthenticatedPrincipal] = Depends(get_current_user),
):
    await _owned_run(ResearchRunService(db), run_id, resolve_user_id(current_user, user_id))
    return await ProvenanceService(db).trace_run(run_id)


@router.get("/runs/{run_id}/provenance/graph", response_model=ProvenanceGraphResponseDTO)
async def get_research_provenance_graph(
    run_id: str,
    user_id: Optional[str] = Query(default=None, min_length=1, max_length=128),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[AuthenticatedPrincipal] = Depends(get_current_user),
):
    await _owned_run(ResearchRunService(db), run_id, resolve_user_id(current_user, user_id))
    graph = await ProvenanceService(db).trace_run_graph(run_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="Research run not found.")
    return graph


@router.post("/resume", response_model=ResearchContinuityResponseDTO)
async def resume_research(
    payload: ResearchResumeRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[AuthenticatedPrincipal] = Depends(get_current_user),
):
    owner_id = resolve_user_id(current_user, payload.user_id)
    if await ResearchRunService(db).get_owned_question(payload.research_question_id, owner_id) is None:
        raise HTTPException(status_code=404, detail="Research question not found.")
    service = ResearchContinuityService(db)
    resumed = await service.resume_investigation(payload.research_question_id, owner_id)
    if not resumed:
        raise HTTPException(status_code=404, detail=f"Research inquiry '{payload.research_question_id}' not found.")
    return ResearchContinuityResponseDTO(**resumed)
