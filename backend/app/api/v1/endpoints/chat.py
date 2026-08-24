from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict
from backend.app.infrastructure.database.session import get_db
from backend.app.application.use_cases.chat_orchestrator import ChatOrchestratorService

router = APIRouter(prefix="/chat", tags=["Chat & Agent"])

class ChatQueryRequest(BaseModel):
    user_id: str
    conversation_id: Optional[str] = None
    message: str

class ChatApiResponse(BaseModel):
    conversation_id: str
    reply: str
    citations: List[str]
    argument_summary: Optional[Dict[str, Any]] = None
    model_config = ConfigDict(from_attributes=True)

@router.post("/", response_model=ChatApiResponse, status_code=status.HTTP_200_OK)
async def chat_endpoint(
    payload: ChatQueryRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Orchestrates an interactive chat turn with hybrid retrieval, 
    anti-hallucination citation validation, and argument synthesis.
    """
    orchestrator = ChatOrchestratorService(db)
    response = await orchestrator.process_chat(
        user_id=payload.user_id,
        conversation_id=payload.conversation_id,
        message=payload.message
    )
    return response