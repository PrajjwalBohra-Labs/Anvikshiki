"""
Planning Engine (§6 Cognitive Subsystems; determines execution
strategy per §14). Purely rule-based over the Intent Analyzer's
decision -- no LLM call, consistent with Step 8's hard rule that no
natural-language generation happens in this step.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.services.reasoning.intent_analyzer import IntentDecision


class PlanStep(str, Enum):
    CLARIFY = "clarify"
    RETRIEVE = "retrieve"
    INVOKE_TOOLS = "invoke_tools"
    REASON = "reason"
    GENERATE = "generate"
    VALIDATE = "validate"
    EXPOSE_UNCERTAINTY = "expose_uncertainty"
    UPDATE_MEMORY = "update_memory"


@dataclass
class ExecutionPlan:
    steps: list[PlanStep] = field(default_factory=list)
    intent: IntentDecision | None = None


def build_plan(intent: IntentDecision) -> ExecutionPlan:
    if intent.clarification_required:
        return ExecutionPlan(steps=[PlanStep.CLARIFY], intent=intent)

    steps: list[PlanStep] = []

    if intent.retrieval_should_occur and not intent.context_sufficient:
        steps.append(PlanStep.RETRIEVE)
    if intent.should_invoke_tools:
        steps.append(PlanStep.INVOKE_TOOLS)
    if intent.should_reason_explicitly:
        steps.append(PlanStep.REASON)

    steps.append(PlanStep.GENERATE)
    steps.append(PlanStep.VALIDATE)

    if intent.should_expose_uncertainty:
        steps.append(PlanStep.EXPOSE_UNCERTAINTY)
    if intent.should_memory_change:
        steps.append(PlanStep.UPDATE_MEMORY)

    return ExecutionPlan(steps=steps, intent=intent)
