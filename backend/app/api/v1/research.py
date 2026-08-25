import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.infrastructure.database.session import get_db, AsyncSessionLocal
from backend.app.application.orchestration.research_workflow import ResearchWorkflowEngine
from backend.app.application.use_cases.research_continuity import ResearchContinuityService
from backend.app.api.v1.schemas.dtos import (
    ResearchRunRequestDTO, ResearchResumeRequestDTO, ResearchContinuityResponseDTO
)

router = APIRouter()

@router.post("/run")
async def run_research(payload: ResearchRunRequestDTO, db: AsyncSession = Depends(get_db)):
    engine = ResearchWorkflowEngine(session_or_factory=AsyncSessionLocal)
    result = await engine.execute_research(
        query=payload.query,
        user_id=payload.user_id,
        domain=payload.domain or "Epistemology"
    )
    return {
        "status": result["validation_status"],
        "query": result["query"],
        "final_response": result["final_response"],
        "validated_claims": result["validated_claims"],
        "retrieved_passages_count": len(result.get("retrieved_passages", [])),
        "safe_events": [{
            "event": "research_completed",
            "status": result["current_step"],
            "validated_claims_count": len(result.get("validated_claims", [])),
        }],
    }

@router.post("/run/stream")
async def stream_research_events(payload: ResearchRunRequestDTO, db: AsyncSession = Depends(get_db)):
    engine = ResearchWorkflowEngine(session_or_factory=AsyncSessionLocal)

    async def sse_generator():
        async for event_data in engine.stream_research_events(
            query=payload.query,
            user_id=payload.user_id,
            domain=payload.domain or "Epistemology"
        ):
            yield f"data: {json.dumps(event_data)}\n\n"

    return StreamingResponse(sse_generator(), media_type="text/event-stream")

@router.post("/resume", response_model=ResearchContinuityResponseDTO)
async def resume_research(payload: ResearchResumeRequestDTO, db: AsyncSession = Depends(get_db)):
    service = ResearchContinuityService(db)
    resumed = await service.resume_investigation(payload.research_question_id, payload.user_id)
    if not resumed:
        raise HTTPException(status_code=404, detail=f"Research inquiry '{payload.research_question_id}' not found.")
    return ResearchContinuityResponseDTO(**resumed)
