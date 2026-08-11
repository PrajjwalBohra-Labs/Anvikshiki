"""
Intent Analyzer (§6 Cognitive Subsystems; answers the §14 Decision
Model questions). No software service in §5 owns this directly -- its
counterpart there is "--", meaning it belongs to the Conversation
Service once that exists (a later step). It lives here for now
because Step 8 groups it with Planning/Reasoning; moving it under
Conversation Service later is a pure relocation, not a redesign.

Deliberately heuristic, not LLM-driven: keeping intent analysis
LLM-free means it's fast, deterministic, and testable without a live
Ollama instance -- and it keeps this step honestly free of any
natural-language generation, the hard rule for Step 8. These
heuristics are a placeholder for smarter classification later (§17
replaceability), not a claim of real NLU.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.context.context_builder import ContextObject

_CLARIFICATION_TRIGGERS = {"it", "that", "this", "they", "them"}
_REASONING_TRIGGERS = {"why", "how", "compare", "explain", "analyze", "evaluate"}
_ACTION_TRIGGERS = {"create", "add", "delete", "update", "remove", "generate", "build"}
_QUESTION_STARTERS = ("what", "why", "how", "who", "when", "where", "is", "does", "can")


@dataclass
class IntentDecision:
    what_is_being_asked: str
    clarification_required: bool
    retrieval_should_occur: bool
    context_sufficient: bool
    should_invoke_tools: bool
    should_reason_explicitly: bool
    should_expose_uncertainty: bool
    should_memory_change: bool


def analyze_intent(query: str, context: ContextObject | None = None) -> IntentDecision:
    normalized = query.strip().lower()
    words = normalized.split()

    what_is_being_asked = _classify_task_type(normalized, words)
    clarification_required = _needs_clarification(words)
    retrieval_should_occur = len(words) > 0 and not clarification_required
    context_sufficient = bool(context and context.retrieved_chunks)

    weak_top_score = bool(
        context and context.retrieved_chunks and context.retrieved_chunks[0].score < 0.4
    )
    should_expose_uncertainty = (not context_sufficient) or weak_top_score
    should_memory_change = not normalized.endswith("?") and what_is_being_asked == "statement"

    return IntentDecision(
        what_is_being_asked=what_is_being_asked,
        clarification_required=clarification_required,
        retrieval_should_occur=retrieval_should_occur,
        context_sufficient=context_sufficient,
        should_invoke_tools=False,  # no tool engine exists yet (later step) -- always off for now
        should_reason_explicitly=any(trigger in words for trigger in _REASONING_TRIGGERS),
        should_expose_uncertainty=bool(should_expose_uncertainty),
        should_memory_change=should_memory_change,
    )


def _classify_task_type(normalized: str, words: list[str]) -> str:
    if any(trigger in words for trigger in _ACTION_TRIGGERS):
        return "action_request"
    if normalized.endswith("?") or normalized.startswith(_QUESTION_STARTERS):
        return "question"
    return "statement"


def _needs_clarification(words: list[str]) -> bool:
    if len(words) < 2:
        return True
    if words[0] in _CLARIFICATION_TRIGGERS and len(words) < 5:
        return True
    return False
