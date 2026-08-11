"""
Reflection Engine (§6; evaluates output before completion). No
dedicated software service owns this in §5 (counterpart is "--"), so
it lives alongside Validation for now -- same placement rationale as
the Intent Analyzer in Step 8, a pure relocation later if split out.

Implements §16 Failure Behaviour exactly:
  - insufficient evidence: acknowledge the limitation, expose
    uncertainty
  - conflicting sources: preserve disagreement, avoid forced
    synthesis

"Conflicting sources" is detected via the reasoning object's own
agreement_among_sources confidence sub-score (§15) rather than a new
heuristic -- low agreement among retrieved chunks is exactly what
that sub-score already measures.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.reasoning.reasoning_engine import ReasoningObject

LOW_AGREEMENT_THRESHOLD = 0.5
_CONFLICT_ACKNOWLEDGEMENT_MARKERS = (
    "differ", "disagree", "conflict", "however", "on the other hand", "inconsistent", "contradict",
)


@dataclass
class ReflectionResult:
    passed: bool
    failure_flags: list[str] = field(default_factory=list)


def reflect(response_text: str, reasoning: ReasoningObject) -> ReflectionResult:
    flags: list[str] = []
    lowered = response_text.lower()

    insufficient_evidence = not reasoning.evidence and not reasoning.facts
    if insufficient_evidence:
        if not any(m in lowered for m in ("no evidence", "insufficient", "cannot find", "don't have")):
            flags.append("insufficient_evidence_not_acknowledged")
        if not any(m in lowered for m in ("uncertain", "not certain", "unclear", "low confidence")):
            flags.append("uncertainty_not_exposed")

    conflicting_sources = (
        reasoning.confidence is not None
        and reasoning.confidence.agreement_among_sources < LOW_AGREEMENT_THRESHOLD
        and len(reasoning.evidence) > 1
    )
    if conflicting_sources and not any(m in lowered for m in _CONFLICT_ACKNOWLEDGEMENT_MARKERS):
        flags.append("forced_synthesis_risk")

    return ReflectionResult(passed=not flags, failure_flags=flags)
