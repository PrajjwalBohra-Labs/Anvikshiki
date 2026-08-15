"""
Conversation Controller (§6; §5 Conversation Service). Wires the
complete §18 canonical flow end to end and implements the §11
Dialogue Model states.

§17 hard rule: handle_message() is the one sanctioned entry point.

Graceful Degradation (§4/§29): everything from RETRIEVE through
PERSIST runs inside one try/except. Retrieval failures already
degrade to empty evidence at the retrieval layer itself (Step 18);
this outer guard catches anything else -- a genuine bug in Reasoning,
Generation, Validation, Reflection, Memory, or Persistence -- and
converts it into a safe, honest, non-fabricated response with
delivered=False rather than an unhandled exception reaching the API
layer as a 500. From the API's perspective this looks exactly like a
validation failure already does -- no new response shape needed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from app.infrastructure.errors import EngineFailureError
from app.infrastructure.event_bus import EventBus, EventName, get_event_bus
from app.infrastructure.llm_adapter import LLMAdapter, get_llm_adapter
from app.infrastructure.observability import (
    get_current_trace_id,
    new_trace_id,
    record_event,
    set_current_trace_id,
    trace_stage,
)
from app.persistence import relational_db
from app.services.context.context_builder import build_context
from app.services.conversation.session_engine import get_or_create_session
from app.services.generation.generation_engine import generate_response_text
from app.services.memory.memory_engine import MemoryEngine, get_memory_engine
from app.services.planning.planning_engine import ExecutionPlan, build_plan
from app.services.reasoning.intent_analyzer import IntentDecision, analyze_intent
from app.services.reasoning.reasoning_engine import ReasoningObject, reason
from app.services.validation.reflection_engine import ReflectionResult, reflect
from app.services.validation.validation_engine import ValidationResult, validate

CLARIFICATION_RESPONSE = "Could you say a bit more about what you're asking? I want to make sure I answer the right question."
INTERNAL_ERROR_RESPONSE = "I ran into an internal problem while processing this and stopped safely rather than guess or continue with a broken result. Please try again."

logger = logging.getLogger("anvikshiki")


class DialogueState(str, Enum):
    INITIALIZE = "initialize"
    INTERPRET = "interpret"
    CLARIFY = "clarify"
    RETRIEVE = "retrieve"
    REASON = "reason"
    GENERATE = "generate"
    VERIFY = "verify"
    REFLECT = "reflect"
    RESPOND = "respond"
    PERSIST = "persist"
    TERMINATE = "terminate"


@dataclass
class ConversationTurnResult:
    session_id: str
    query: str
    response: str | None
    delivered: bool
    trace_id: str = ""
    state_trace: list[DialogueState] = field(default_factory=list)
    intent: IntentDecision | None = None
    plan: ExecutionPlan | None = None
    reasoning: ReasoningObject | None = None
    validation: ValidationResult | None = None
    reflection: ReflectionResult | None = None
    question_id: str | None = None
    answer_id: str | None = None


def handle_message(
    query: str,
    session_id: str | None = None,
    conversation_history: list[dict] | None = None,
    project_id: str | None = None,
    use_web_search: bool = False,
    llm_adapter: LLMAdapter | None = None,
    memory_engine: MemoryEngine | None = None,
    event_bus: EventBus | None = None,
) -> ConversationTurnResult:
    llm_adapter = llm_adapter or get_llm_adapter()
    memory_engine = memory_engine or get_memory_engine()
    event_bus = event_bus or get_event_bus()

    trace_id = get_current_trace_id()
    if trace_id is None:
        trace_id = new_trace_id()
        set_current_trace_id(trace_id)

    with trace_stage("conversation_turn", query_length=len(query)):
        trace: list[DialogueState] = [DialogueState.INITIALIZE]
        session_id, was_created = get_or_create_session(session_id)
        if was_created:
            event_bus.publish(EventName.CONVERSATION_STARTED, {"session_id": session_id})

        trace.append(DialogueState.INTERPRET)
        with trace_stage("interpret"):
            initial_intent = analyze_intent(query)

        if initial_intent.clarification_required:
            with trace_stage("clarify"):
                trace.append(DialogueState.CLARIFY)
                response_text = CLARIFICATION_RESPONSE

                trace.append(DialogueState.RESPOND)
                question_id = relational_db.create_question(session_id, query)
                answer_id = relational_db.create_answer(question_id, response_text)
                memory_engine.remember(
                    {"content": f"Q: {query}\nA: {response_text}", "tier": "dialogue", "scope_id": session_id}
                )

                trace.append(DialogueState.PERSIST)
                trace.append(DialogueState.TERMINATE)

            return ConversationTurnResult(
                session_id=session_id, query=query, response=response_text, delivered=True,
                trace_id=trace_id, state_trace=trace, intent=initial_intent,
                question_id=question_id, answer_id=answer_id,
            )

        try:
            trace.append(DialogueState.RETRIEVE)
            with trace_stage("retrieve"):
                context = build_context(
                    query, conversation_history=conversation_history, project_id=project_id,
                    llm_adapter=llm_adapter, use_web_search=use_web_search,
                )
                final_intent = analyze_intent(query, context=context)
                plan = build_plan(final_intent)

            trace.append(DialogueState.REASON)
            with trace_stage("reason"):
                reasoning = reason(query, context)
                event_bus.publish(
                    EventName.REASONING_COMPLETED,
                    {"session_id": session_id, "confidence": reasoning.confidence.overall if reasoning.confidence else None},
                )

            trace.append(DialogueState.GENERATE)
            with trace_stage("generate"):
                response_text = generate_response_text(reasoning, query, conversation_history, llm_adapter)

            trace.append(DialogueState.VERIFY)
            with trace_stage("verify"):
                validation_result = validate(response_text, reasoning)
                if not validation_result.passed:
                    record_event("verify", "failure", violations=validation_result.all_violations)

            trace.append(DialogueState.REFLECT)
            with trace_stage("reflect"):
                reflection_result = reflect(response_text, reasoning)
                if not reflection_result.passed:
                    record_event("reflect", "failure", flags=reflection_result.failure_flags)

            delivered = validation_result.passed and reflection_result.passed

            trace.append(DialogueState.RESPOND)
            delivered_text = response_text if delivered else None

            memory_summary = f"Q: {query}\nA: {delivered_text or '[not delivered -- failed validation/reflection]'}"
            memory_engine.remember({"content": memory_summary, "tier": "dialogue", "scope_id": session_id})
            if delivered and final_intent.should_memory_change:
                memory_engine.remember({"content": query, "tier": "research", "scope_id": project_id})

            trace.append(DialogueState.PERSIST)
            question_id = relational_db.create_question(session_id, query)
            answer_id = None
            if delivered_text is not None:
                confidence = reasoning.confidence.overall if reasoning.confidence else None
                sources = []
                seen_keys = set()
                for item in reasoning.evidence:
                    key = item.get("source_document_id") or item.get("source_url")
                    if key and key not in seen_keys:
                        seen_keys.add(key)
                        sources.append(
                            {
                                "document_id": item.get("source_document_id"),
                                "title": item.get("source_document_title"),
                                "source_type": item.get("source_type"),
                                "url": item.get("source_url"),
                                "concept_id": item.get("concept_id"),
                            }
                        )
                answer_id = relational_db.create_answer(
                    question_id, delivered_text, confidence=confidence, sources=sources
                )

            trace.append(DialogueState.TERMINATE)

        except Exception as exc:
            # Graceful degradation (§4/§29): a bug anywhere in
            # Reason/Generate/Verify/Reflect/Memory/Persist must not
            # crash the request. Log clearly, terminate this turn
            # safely, never fabricate a response.
            failure = EngineFailureError(stage="conversation_turn", original=exc)
            logger.error(str(failure))
            record_event("conversation_turn", "failure", error=str(exc), error_type=type(exc).__name__)

            question_id = relational_db.create_question(session_id, query)
            return ConversationTurnResult(
                session_id=session_id, query=query, response=INTERNAL_ERROR_RESPONSE, delivered=False,
                trace_id=trace_id, state_trace=trace, question_id=question_id,
            )

    return ConversationTurnResult(
        session_id=session_id, query=query, response=delivered_text, delivered=delivered,
        trace_id=trace_id, state_trace=trace, intent=final_intent, plan=plan, reasoning=reasoning,
        validation=validation_result, reflection=reflection_result,
        question_id=question_id, answer_id=answer_id,
    )

