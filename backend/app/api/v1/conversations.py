import json
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.infrastructure.database.session import get_db
from backend.app.application.use_cases.conversation_service import ConversationService
from backend.app.api.v1.schemas.dtos import (
    ConversationCreateDTO, ConversationResponseDTO, MessageCreateDTO, MessageResponseDTO
)

router = APIRouter()

@router.post("", response_model=ConversationResponseDTO)
async def create_conversation(payload: ConversationCreateDTO, db: AsyncSession = Depends(get_db)):
    service = ConversationService(db)
    conv = await service.create_conversation(user_id=payload.user_id, title=payload.title)
    return ConversationResponseDTO(conversation_id=conv.id, title=conv.title, created_at=conv.created_at, messages=[])

@router.get("/{conversation_id}", response_model=ConversationResponseDTO)
async def get_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    service = ConversationService(db)
    history = await service.get_conversation_history(conversation_id)
    if not history:
        raise HTTPException(status_code=404, detail=f"Conversation '{conversation_id}' not found.")
    return ConversationResponseDTO(
        conversation_id=history["conversation_id"],
        title=history["title"],
        created_at=history["created_at"],
        messages=[
            MessageResponseDTO(
                message_id=m["message_id"],
                role=m["role"],
                content=m["content"],
                research_run_id=m["research_run_id"],
                citations=m["citations"] or [],
                created_at=m["created_at"]
            )
            for m in history["messages"]
        ]
    )

@router.post("/{conversation_id}/messages", response_model=MessageResponseDTO)
async def add_message(conversation_id: str, payload: MessageCreateDTO, db: AsyncSession = Depends(get_db)):
    service = ConversationService(db)
    msg = await service.add_message(
        conversation_id=conversation_id,
        role=payload.role,
        content=payload.content,
        research_run_id=payload.research_run_id,
        citations_payload=payload.citations
    )
    return MessageResponseDTO(
        message_id=msg.id,
        role=msg.role,
        content=msg.content,
        research_run_id=msg.research_run_id,
        citations=msg.citations_payload or [],
        created_at=msg.created_at
    )

@router.post("/{conversation_id}/messages/stream")
async def stream_message(conversation_id: str, payload: MessageCreateDTO, db: AsyncSession = Depends(get_db)):
    service = ConversationService(db)
    msg = await service.add_message(
        conversation_id=conversation_id,
        role=payload.role,
        content=payload.content,
        research_run_id=payload.research_run_id,
        citations_payload=payload.citations
    )

    async def event_generator():
        yield f"data: {json.dumps({'event': 'start', 'message_id': msg.id})}\n\n"
        async for chunk in service.stream_message_response(payload.content, chunk_size=8):
            yield f"data: {json.dumps({'event': 'chunk', 'token': chunk})}\n\n"
            await asyncio.sleep(0.01)
        yield f"data: {json.dumps({'event': 'done', 'message_id': msg.id})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")