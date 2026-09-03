from typing import Any

import structlog
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.app.application.use_cases.citation_service import CitationService
from backend.app.application.use_cases.reasoning_engine import ReasoningEngineService
from backend.app.core.errors import AnvikshikiDomainError
from backend.app.infrastructure.database.models import ConversationModel, MessageModel
from backend.app.infrastructure.rag.reranker import AdvancedRetriever

logger = structlog.get_logger(__name__)

class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    citations: list[str]
    argument_summary: dict[str, Any] | None = None

class ChatOrchestratorService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.retriever = AdvancedRetriever(session)
        self.citation_service = CitationService(session)
        self.reasoning_engine = ReasoningEngineService(session)

    async def process_chat(self, user_id: str, conversation_id: str | None, message: str) -> ChatResponse:
        """
        Orchestrates a chat turn:
        1. Ensures conversation exists.
        2. Persists user message.
        3. Retrieves and reranks relevant evidence.
        4. Synthesizes formal argument and verified citations.
        5. Persists assistant reply and returns structured response.
        """
        # 1. Resolve or create conversation
        if conversation_id:
            conv_result = await self.session.execute(select(ConversationModel).where(ConversationModel.id == conversation_id))
            conversation = conv_result.scalars().first()
            if not conversation:
                raise AnvikshikiDomainError(f"Conversation {conversation_id} not found.", status_code=404)
        else:
            conversation = ConversationModel(user_id=user_id, title=message[:50])
            self.session.add(conversation)
            await self.session.flush()

        # 2. Save user message
        user_msg = MessageModel(conversation_id=conversation.id, role="user", content=message)
        self.session.add(user_msg)
        await self.session.flush()

        # 3. Retrieve verified evidence passages via Advanced Retriever
        scored_passages = await self.retriever.retrieve_and_rerank(query=message, top_k=3)

        # 4. Generate and validate canonical citations
        citations = []
        for item in scored_passages:
            citation = await self.citation_service.generate_citation(item.passage.id)
            # Guardrail check
            is_valid = await self.citation_service.validate_ai_citation(item.passage.id, citation.source_id)
            if is_valid:
                citations.append(citation.citation_string)

        # 5. Synthesize argument structure via Reasoning Engine
        argument = await self.reasoning_engine.synthesize_argument(query=message)

        # 6. Construct reply text
        reply_parts = [f"Based on our epistemological corpus analysis for query '{message}':"]
        for item in scored_passages:
            reply_parts.append(f"- Passage: {item.passage.content[:150]}...")
            
        if citations:
            reply_parts.append("\nVerified Citations:")
            for cit in citations:
                reply_parts.append(f"• {cit}")

        reply_text = "\n".join(reply_parts)

        # 7. Save assistant message
        assistant_msg = MessageModel(conversation_id=conversation.id, role="assistant", content=reply_text)
        self.session.add(assistant_msg)
        await self.session.commit()

        return ChatResponse(
            conversation_id=conversation.id,
            reply=reply_text,
            citations=citations,
            argument_summary={
                "conclusion": argument.conclusion.statement,
                "pramana": argument.pramana_type,
                "status": argument.overall_status
            }
        )