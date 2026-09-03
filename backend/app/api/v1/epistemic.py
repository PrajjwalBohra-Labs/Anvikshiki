
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import (
    AuthenticatedPrincipal,
    get_current_user,
    resolve_user_id,
)
from backend.app.api.v1.schemas.dtos import (
    EpistemicPositionCreateDTO,
    EpistemicPositionResponseDTO,
    EpistemicPositionUpdateDTO,
)
from backend.app.application.memory.epistemic_memory import EpistemicMemoryService
from backend.app.infrastructure.database.models import EpistemicPositionModel
from backend.app.infrastructure.database.session import get_db

router = APIRouter()

@router.post("/positions", response_model=EpistemicPositionResponseDTO)
async def create_position(
    payload: EpistemicPositionCreateDTO,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedPrincipal | None = Depends(get_current_user),
):
    owner_id = resolve_user_id(current_user, payload.user_id)
    service = EpistemicMemoryService(db)
    pos = await service.record_position(
        user_id=owner_id,
        claim_statement=payload.claim_statement,
        position=payload.position,
        confidence=payload.confidence,
        supporting_evidence=payload.supporting_evidence,
        counterarguments=payload.counterarguments,
        status=payload.status
    )
    return EpistemicPositionResponseDTO(
        position_id=pos.id,
        claim_statement=pos.claim_statement,
        position=pos.position,
        confidence=pos.confidence,
        status=pos.status,
        supporting_evidence=pos.supporting_evidence_payload or [],
        counterarguments=pos.counterarguments_payload or [],
        updated_at=pos.updated_at,
        history=[]
    )

@router.patch("/positions/{position_id}/status", response_model=EpistemicPositionResponseDTO)
async def update_position_status(
    position_id: str,
    payload: EpistemicPositionUpdateDTO,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedPrincipal | None = Depends(get_current_user),
):
    service = EpistemicMemoryService(db)
    try:
        if current_user is not None:
            position = await db.get(EpistemicPositionModel, position_id)
            if position is None:
                raise ValueError(f"Epistemic position '{position_id}' not found.")
            if position.user_id != current_user.user_id:
                raise HTTPException(status_code=403, detail="The authenticated user does not own this resource.")
        pos = await service.update_position_status(
            position_id=position_id,
            new_status=payload.new_status,
            change_reason=payload.change_reason
        )
        return EpistemicPositionResponseDTO(
            position_id=pos.id,
            claim_statement=pos.claim_statement,
            position=pos.position,
            confidence=pos.confidence,
            status=pos.status,
            supporting_evidence=pos.supporting_evidence_payload or [],
            counterarguments=pos.counterarguments_payload or [],
            updated_at=pos.updated_at,
            history=[]
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@router.get("/user/{user_id}/positions", response_model=list[EpistemicPositionResponseDTO])
async def get_user_positions(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedPrincipal | None = Depends(get_current_user),
):
    owner_id = resolve_user_id(current_user, user_id)
    service = EpistemicMemoryService(db)
    positions = await service.get_user_positions(owner_id)
    return [
        EpistemicPositionResponseDTO(
            position_id=p["position_id"],
            claim_statement=p["claim_statement"],
            position=p["position"],
            confidence=p["confidence"],
            status=p["status"],
            supporting_evidence=p["supporting_evidence"] or [],
            counterarguments=p["counterarguments"] or [],
            updated_at=p["updated_at"],
            history=p["history"]
        )
        for p in positions
    ]
