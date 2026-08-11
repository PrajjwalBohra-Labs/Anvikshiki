from app.services.planning.planning_engine import PlanStep, build_plan
from app.services.reasoning.intent_analyzer import IntentDecision


def _decision(**overrides) -> IntentDecision:
    base = dict(
        what_is_being_asked="question",
        clarification_required=False,
        retrieval_should_occur=True,
        context_sufficient=False,
        should_invoke_tools=False,
        should_reason_explicitly=False,
        should_expose_uncertainty=False,
        should_memory_change=False,
    )
    base.update(overrides)
    return IntentDecision(**base)


def test_clarification_required_produces_clarify_only_plan():
    plan = build_plan(_decision(clarification_required=True))
    assert plan.steps == [PlanStep.CLARIFY]


def test_plan_always_includes_generate_and_validate():
    plan = build_plan(_decision())
    assert PlanStep.GENERATE in plan.steps
    assert PlanStep.VALIDATE in plan.steps


def test_plan_includes_retrieve_when_context_insufficient():
    plan = build_plan(_decision(retrieval_should_occur=True, context_sufficient=False))
    assert PlanStep.RETRIEVE in plan.steps


def test_plan_skips_retrieve_when_context_already_sufficient():
    plan = build_plan(_decision(retrieval_should_occur=True, context_sufficient=True))
    assert PlanStep.RETRIEVE not in plan.steps


def test_plan_includes_update_memory_when_flagged():
    plan = build_plan(_decision(should_memory_change=True))
    assert PlanStep.UPDATE_MEMORY in plan.steps
