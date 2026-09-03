from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import (
    AuthenticatedPrincipal,
    get_current_user,
    resolve_user_id,
)
from backend.app.application.use_cases.chat_orchestrator import ChatOrchestratorService
from backend.app.infrastructure.database.session import get_db

router = APIRouter(prefix="/chat", tags=["Chat & Agent"])

class ChatQueryRequest(BaseModel):
    user_id: str
    conversation_id: str | None = None
    message: str

class ChatApiResponse(BaseModel):
    conversation_id: str
    reply: str
    citations: list[str]
    argument_summary: dict[str, Any] | None = None
    model_config = ConfigDict(from_attributes=True)

@router.post("/", response_model=ChatApiResponse, status_code=status.HTTP_200_OK)
async def chat_endpoint(
    payload: ChatQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedPrincipal | None = Depends(get_current_user),
):
    """
    Orchestrates an interactive chat turn with hybrid retrieval, 
    anti-hallucination citation validation, and argument synthesis.
    """
    orchestrator = ChatOrchestratorService(db)
    response = await orchestrator.process_chat(
        user_id=resolve_user_id(current_user, payload.user_id),
        conversation_id=payload.conversation_id,
        message=payload.message
    )
    return response
