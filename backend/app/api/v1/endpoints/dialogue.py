from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.infrastructure.database.session import get_db
from backend.app.application.use_cases.dialogue_controller import DialogueController

router = APIRouter()

class InquireRequest(BaseModel):
    user_id: str = "default_researcher"
    message: str = Field(..., min_length=3)
    user_position: Optional[str] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

class InquireResponse(BaseModel):
    inquiry_summary: str
    arguments_examined: List[Dict[str, Any]]
    critical_challenges: List[str]
    uncertainties: List[str]
    unresolved_question: Optional[str] = None

@router.post("/inquire", response_model=InquireResponse, status_code=status.HTTP_200_OK)
async def inquire_endpoint(req: InquireRequest, db: AsyncSession = Depends(get_db)):
    controller = DialogueController(db)
    res = await controller.process_user_turn(
        user_id=req.user_id,
        user_message=req.message,
        user_position=req.user_position,
        confidence=req.confidence
    )
    return InquireResponse(
        inquiry_summary=res.inquiry_summary,
        arguments_examined=res.arguments_examined,
        critical_challenges=res.critical_challenges,
        uncertainties=res.uncertainties,
        unresolved_question=res.unresolved_question
    )