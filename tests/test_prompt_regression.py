"""
Prompt Regression (§31). Pins the exact safety-critical instructions
that must survive any future edit to prompt_builder.py -- a silent
removal of the confidence-calibration or citation-format rule would
reopen bugs already found and fixed in this project: the model
stating a different confidence number than computed (Steps 9/11),
and fabricated numbered citations like [1][2][3] (the Research
Engine incident).
"""

from app.services.prompt.prompt_builder import build_prompt
from app.services.reasoning.reasoning_engine import ConfidenceBreakdown, ReasoningObject


def _reasoning_with_confidence(overall: float) -> ReasoningObject:
    return ReasoningObject(
        problem="q",
        facts=[{"chunk_id": "c1", "text": "fact"}],
        evidence=[{"chunk_id": "c1", "source_document_id": "d1", "source_document_title": "Doc", "score": 0.8}],
        confidence=ConfidenceBreakdown(0.5, 1.0, 0.6, 0.8, 0.9, overall),
    )


def test_confidence_calibration_instruction_is_present_and_exact():
    """Regression guard for the model stating a different confidence
    number than the one actually computed (0.95-vs-0.59 incident)."""
    prompt = build_prompt(_reasoning_with_confidence(0.73), "q")
    module_policy = dict(prompt.layers)["module_policy"]
    assert "0.73" in module_policy
    assert "never estimate, round, or invent a different number" in module_policy


def test_never_fabricate_instruction_is_present():
    prompt = build_prompt(_reasoning_with_confidence(0.8), "q")
    task_instructions = dict(prompt.layers)["task_instructions"]
    assert "speculation" in task_instructions.lower() or "insufficient" in task_instructions.lower()


def test_citation_attribution_instruction_is_present():
    prompt = build_prompt(_reasoning_with_confidence(0.8), "q")
    module_policy = dict(prompt.layers)["module_policy"]
    assert "attribute" in module_policy.lower()


def test_web_versus_local_trust_instruction_appears_only_when_web_evidence_present():
    reasoning_local_only = _reasoning_with_confidence(0.8)
    prompt_local = build_prompt(reasoning_local_only, "q")
    assert "external, unverified" not in dict(prompt_local.layers)["module_policy"]

    reasoning_with_web = _reasoning_with_confidence(0.8)
    reasoning_with_web.evidence.append(
        {"chunk_id": "c2", "source_document_id": None, "source_document_title": "Web Src",
         "source_type": "web", "score": 0.7}
    )
    prompt_web = build_prompt(reasoning_with_web, "q")
    assert "external, unverified" in dict(prompt_web.layers)["module_policy"]
