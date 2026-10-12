import json
from collections.abc import AsyncGenerator
from typing import Any

import structlog
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.application.orchestration.research_workflow import ResearchWorkflowEngine
from backend.app.application.use_cases.reasoning_persistence import persist_reasoning_artifacts
from backend.app.application.use_cases.research_run_service import ResearchRunService
from backend.app.core.config import RuntimeProfile, settings
from backend.app.core.errors import AnvikshikiDomainError
from backend.app.infrastructure.ai.local_model_adapter import BaseModelAdapter
from backend.app.infrastructure.database.models import (
    ConversationModel,
    MessageModel,
    ResearchQuestionModel,
    ResearchRunModel,
)
from backend.app.infrastructure.database.session import AsyncSessionLocal

logger = structlog.get_logger(__name__)


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    citations: list[str]
    argument_summary: dict[str, Any] | None = None


class _TestInquiryAdapter(BaseModelAdapter):
    """Deterministic semantic instrument for isolated tests only."""

    def __init__(self) -> None:
        super().__init__(model_name="test-inquiry-adapter")

    @staticmethod
    def _json_after(prompt: str, marker: str) -> list[dict[str, Any]]:
        start = prompt.find(marker)
        if start < 0:
            return []
        start = prompt.find("[", start)
        end = prompt.find("\n\n", start)
        if start < 0 or end < 0:
            return []
        try:
            value = json.loads(prompt[start:end])
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        return value if isinstance(value, list) else []

    @staticmethod
    def _evidence_payload(prompt: str) -> list[dict[str, Any]]:
        marker = "Evidence JSON:\n"
        start = prompt.find(marker)
        if start < 0:
            return []
        start += len(marker)
        end = prompt.find("\nUse only verified passages", start)
        if end < 0:
            return []
        try:
            payload = json.loads(prompt[start:end])
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        return payload.get("passages", []) if isinstance(payload, dict) else []

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        if "Analyze this inquiry before any research" in prompt:
            question = prompt.split("Question:\n", 1)[-1].split("\n\nUser/application context", 1)[0].strip()
            payload = {
                "literal_question": question,
                "central_problem": question,
                "requested_task": question,
                "inquiry_mode": "direct explanation",
                "research_requirements": [{
                    "requirement_id": "question_scope",
                    "question_component": question,
                    "evidence_needed": "A substantive passage addressing the question.",
                    "search_queries": [question],
                }],
            }
            return {"content": json.dumps(payload), "model": self.model_name}
        if "Judge whether each retrieved passage" in prompt:
            passages = self._json_after(prompt, "Retrieved passages (metadata identifies a passage; it is not evidence):")
            payload = {
                "evaluations": [
                    {
                        "passage_id": item.get("passage_id"),
                        "relevance": "direct",
                        "supports_requirements": ["question_scope"],
                        "supported_proposition": item.get("content", ""),
                        "evidence_role": "direct evidence",
                        "use_for_synthesis": True,
                    }
                    for item in passages
                ],
                "sufficiency": "sufficient" if passages else "unknown",
                "satisfied_requirements": ["question_scope"] if passages else [],
                "missing_requirements": [],
            }
            return {"content": json.dumps(payload), "model": self.model_name}
        if "Reason over the relevant evidence" in prompt:
            passages = self._json_after(prompt, "Passages:")
            payload = {
                "source_positions": [
                    {
                        "source_id": item.get("source_id"),
                        "source_title": item.get("source_title"),
                        "position": item.get("content", ""),
                        "reasoning_summary": item.get("content", ""),
                        "supporting_passage_ids": [item.get("passage_id")],
                    }
                    for item in passages
                ],
                "reasoning_chains": [
                    {
                        "question_component": "question_scope",
                        "claim": item.get("content", ""),
                        "evidence_passage_ids": [item.get("passage_id")],
                        "analysis": "The passage is the source-level basis for this limited answer.",
                        "conclusion": item.get("content", ""),
                        "confidence": 0.7,
                        "inference_status": "direct",
                    }
                    for item in passages
                ],
                "relationships": [],
                "gaps": [],
                "alternatives": [],
            }
            return {"content": json.dumps(payload), "model": self.model_name}
        if "Identify the most important limitations" in prompt:
            return {"content": json.dumps({"objections": []}), "model": self.model_name}
        if "Audit this proposed answer" in prompt:
            passages = self._json_after(prompt, "Substantive passages:")
            return {
                "content": json.dumps({
                    "addresses_question": True,
                    "covered_requirements": ["question_scope"],
                    "uncovered_requirements": [],
                    "evidence_alignment": [
                        {"passage_id": item.get("passage_id"), "supports": True}
                        for item in passages
                    ],
                    "irrelevant_or_unsupported_claims": [],
                    "topic_drift": False,
                    "conclusion_follows": True,
                    "answer_is_source_summary": False,
                    "sufficient_for_answer": bool(passages),
                    "epistemic_calibration": "well-supported",
                }),
                "model": self.model_name,
            }

        passages = self._evidence_payload(prompt) or self._json_after(prompt, "Substantive evidence:")
        answer = (
            "The available source supports the following point: "
            + str(passages[0].get("content", ""))
            + " [P1]"
            if passages
            else "The available evidence is insufficient to support a substantive answer."
        )
        return {"content": answer, "model": self.model_name}

    async def stream_generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        yield ""


class ChatOrchestratorService:
    """Routes chat turns through the same continuing inquiry as research runs."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _conversation(self, user_id: str, conversation_id: str | None, message: str) -> ConversationModel:
        if conversation_id:
            conversation = await self.session.get(ConversationModel, conversation_id)
            if not conversation:
                raise AnvikshikiDomainError(f"Conversation {conversation_id} not found.", status_code=404)
            if conversation.user_id != user_id:
                raise AnvikshikiDomainError("The authenticated user does not own this conversation.", status_code=403)
            return conversation
        conversation = ConversationModel(user_id=user_id, title=message[:50])
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def _continuity(self, messages: list[MessageModel]) -> tuple[dict[str, Any], str | None]:
        for message in reversed(messages):
            if message.research_run_id:
                run = await self.session.get(ResearchRunModel, message.research_run_id)
                if run and run.output_references:
                    return {
                        "original_question": run.query,
                        "latest_result": run.output_references,
                        "research_question_id": run.research_question_id,
                    }, run.research_question_id
        return {}, None

    async def process_chat(self, user_id: str, conversation_id: str | None, message: str) -> ChatResponse:
        conversation = await self._conversation(user_id, conversation_id, message)
        prior_result = await self.session.execute(
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation.id)
            .order_by(MessageModel.created_at.asc())
        )
        prior_messages = list(prior_result.scalars().all())
        inquiry_context, question_id = await self._continuity(prior_messages)
        history = [{"role": item.role, "content": item.content} for item in prior_messages]

        self.session.add(MessageModel(conversation_id=conversation.id, role="user", content=message))
        await self.session.flush()

        question = await self.session.get(ResearchQuestionModel, question_id) if question_id else None
        if question is None:
            question = ResearchQuestionModel(
                user_id=user_id,
                main_question=message,
                domain="Epistemology",
                research_status="ACTIVE",
                research_history=[],
            )
            self.session.add(question)
            await self.session.flush()

        run = await ResearchRunService(self.session).create_run(
            query=message,
            user_id=user_id,
            research_question_id=question.id,
            domain=question.domain,
            depth="standard",
        )
        adapter = _TestInquiryAdapter() if settings.RUNTIME_PROFILE == RuntimeProfile.TEST else None
        engine = ResearchWorkflowEngine(session_or_factory=AsyncSessionLocal, llm_adapter=adapter)
        try:
            result_state = await engine.execute_research(
                query=message,
                user_id=user_id,
                domain=question.domain or "Epistemology",
                thread_id=run.thread_id or run.id,
                run_id=run.id,
                inquiry_context=inquiry_context,
                conversation_history=history,
            )
            result = engine._result_payload(result_state)
            await persist_reasoning_artifacts(self.session, run, question, result)
            await ResearchRunService(self.session).complete_run(run.id, output_references=result)
        except Exception as exc:
            await self.session.rollback()
            await ResearchRunService(self.session).fail_run(run.id, str(exc))
            logger.error("Chat inquiry failed", run_id=run.id, error_type=type(exc).__name__)
            raise

        reply = result.get("final_response") or "The inquiry could not be grounded in available evidence."
        citations = [
            str(item.get("citation") or "")
            for item in result.get("citations", [])
            if item.get("citation")
        ]
        self.session.add(MessageModel(
            conversation_id=conversation.id,
            role="assistant",
            content=reply,
            research_run_id=run.id,
            citations_payload=result.get("citations", []),
        ))
        await self.session.commit()
        approved = result.get("validation_status") == "APPROVED"
        return ChatResponse(
            conversation_id=conversation.id,
            reply=reply,
            citations=citations,
            argument_summary={
                "conclusion": reply,
                "pramana": "anumana",
                "status": "supported" if approved else "insufficient_evidence",
            },
        )
