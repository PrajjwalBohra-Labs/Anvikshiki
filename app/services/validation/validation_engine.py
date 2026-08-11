"""
Validation Engine (§6; checks citations/consistency/confidence/
completeness per §17). Enforces "generation never bypasses
validation" and "every citation references stored knowledge" (§17):
generate_and_validate() is the only sanctioned way to turn a
ReasoningObject into a delivered response -- it always validates
before returning, and refuses to deliver output that fails.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.infrastructure.llm_adapter import LLMAdapter
from app.services.generation.generation_engine import generate_response_text
from app.services.reasoning.reasoning_engine import ReasoningObject

_CITATION_RE = re.compile(r"\[([^\]]+)\]")
_CONFIDENCE_CLAIM_RE = re.compile(r"confidence[^0-9]{0,20}([01](?:\.\d+)?)", re.IGNORECASE)
_UNCERTAINTY_MARKERS = (
    "uncertain", "may not", "not certain", "limited evidence", "insufficient",
    "unclear", "cannot confirm", "low confidence", "not confident",
)
LOW_CONFIDENCE_THRESHOLD = 0.5
CONFIDENCE_TOLERANCE = 0.1


@dataclass
class ValidationResult:
    passed: bool
    citation_violations: list[str] = field(default_factory=list)
    consistency_violations: list[str] = field(default_factory=list)
    confidence_violations: list[str] = field(default_factory=list)
    completeness_violations: list[str] = field(default_factory=list)

    @property
    def all_violations(self) -> list[str]:
        return (
            self.citation_violations
            + self.consistency_violations
            + self.confidence_violations
            + self.completeness_violations
        )


def validate(response_text: str, reasoning: ReasoningObject) -> ValidationResult:
    citation_violations = _check_citations(response_text, reasoning)
    consistency_violations = _check_consistency(response_text, reasoning)
    confidence_violations = _check_confidence_language(response_text, reasoning)
    completeness_violations = _check_completeness(response_text, reasoning)

    passed = not (
        citation_violations or consistency_violations or confidence_violations or completeness_violations
    )
    return ValidationResult(
        passed=passed,
        citation_violations=citation_violations,
        consistency_violations=consistency_violations,
        confidence_violations=confidence_violations,
        completeness_violations=completeness_violations,
    )


def _known_sources(reasoning: ReasoningObject) -> set[str]:
    sources = set()
    for item in reasoning.evidence:
        if item.get("source_document_title"):
            sources.add(item["source_document_title"])
        if item.get("source_document_id"):
            sources.add(item["source_document_id"])
    return sources


def _check_citations(response_text: str, reasoning: ReasoningObject) -> list[str]:
    known_sources = _known_sources(reasoning)
    return [
        f"citation '{citation}' does not match any retrieved source"
        for citation in _CITATION_RE.findall(response_text)
        if citation not in known_sources
    ]


def _check_consistency(response_text: str, reasoning: ReasoningObject) -> list[str]:
    if reasoning.confidence is None:
        return []
    violations = []
    for match in _CONFIDENCE_CLAIM_RE.finditer(response_text):
        claimed = float(match.group(1))
        actual = reasoning.confidence.overall
        if abs(claimed - actual) > CONFIDENCE_TOLERANCE:
            violations.append(
                f"response claims confidence {claimed:.2f} but computed confidence was {actual:.2f}"
            )
    return violations


def _check_confidence_language(response_text: str, reasoning: ReasoningObject) -> list[str]:
    if reasoning.confidence is None or reasoning.confidence.overall >= LOW_CONFIDENCE_THRESHOLD:
        return []
    lowered = response_text.lower()
    if not any(marker in lowered for marker in _UNCERTAINTY_MARKERS):
        return [
            f"computed confidence ({reasoning.confidence.overall:.2f}) is low but the response "
            "does not expose any uncertainty (§16)"
        ]
    return []


def _check_completeness(response_text: str, reasoning: ReasoningObject) -> list[str]:
    if reasoning.evidence or reasoning.facts:
        return []
    lowered = response_text.lower()
    if any(marker in lowered for marker in ("no evidence", "insufficient", "cannot find", "don't have")):
        return []
    return ["no evidence was retrieved but the response does not acknowledge this (§16)"]


def generate_and_validate(
    reasoning: ReasoningObject,
    query: str,
    conversation_history: list[dict] | None = None,
    llm_adapter: LLMAdapter | None = None,
) -> tuple[str | None, ValidationResult]:
    """The only sanctioned path from a ReasoningObject to a delivered
    response (§17 "generation never bypasses validation"). Returns
    (None, result) if validation fails -- the caller must not deliver
    that text."""

    response_text = generate_response_text(reasoning, query, conversation_history, llm_adapter)
    result = validate(response_text, reasoning)
    delivered = response_text if result.passed else None
    return delivered, result
