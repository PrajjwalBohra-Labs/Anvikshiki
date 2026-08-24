from typing import List, Dict, Any, Optional, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.infrastructure.database.models import ConversationModel, MessageModel
import structlog

logger = structlog.get_logger(__name__)

class ConversationService:
    """
    Manages conversation persistence, retrieval, streaming message support,
    research-run attachments, and citation linking.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_conversation(self, user_id: str, title: Optional[str] = None) -> ConversationModel:
        conversation = ConversationModel(user_id=user_id, title=title or "New Research Dialogue")
        self.session.add(conversation)
        await self.session.commit()
        await self.session.refresh(conversation)
        logger.info("Conversation created", conversation_id=conversation.id, user_id=user_id)
        return conversation

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        research_run_id: Optional[str] = None,
        citations_payload: Optional[List[Dict[str, Any]]] = None
    ) -> MessageModel:
        message = MessageModel(
            conversation_id=conversation_id,
            role=role,
            content=content,
            research_run_id=research_run_id,
            citations_payload=citations_payload or []
        )
        self.session.add(message)
        await self.session.commit()
        await self.session.refresh(message)
        logger.info("Message added with context links", message_id=message.id, conversation_id=conversation_id)
        return message

    async def get_conversation_history(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        conv = await self.session.get(ConversationModel, conversation_id)
        if not conv:
            return None

        stmt = select(MessageModel).where(MessageModel.conversation_id == conversation_id).order_by(MessageModel.created_at.asc())
        result = await self.session.execute(stmt)
        messages = result.scalars().all()

        return {
            "conversation_id": conv.id,
            "title": conv.title,
            "created_at": conv.created_at,
            "messages": [
                {
                    "message_id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "research_run_id": m.research_run_id,
                    "citations": m.citations_payload,
                    "created_at": m.created_at
                }
                for m in messages
            ]
        }

    async def stream_message_response(self, text_content: str, chunk_size: int = 10) -> AsyncGenerator[str, None]:
        """Supports streaming message output for responsive frontend rendering."""
        for i in range(0, len(text_content), chunk_size):
            yield text_content[i:i + chunk_size]