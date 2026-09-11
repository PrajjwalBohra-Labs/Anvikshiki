"""Publication gates for evidence-grounded, question-responsive synthesis.

Citation presence is deliberately only one input. A response can be perfectly
formatted and still fail because it answers a different question, cites
metadata instead of a passage, or silently turns an inference into a source
statement.
"""

from __future__ import annotations

import re
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.application.use_cases.research_reasoning import is_substantive_passage
from backend.app.infrastructure.database.models import PassageModel

logger = structlog.get_logger(__name__)

_STOPWORDS = {
    "about", "after", "also", "and", "are", "been", "being", "between", "but", "could", "does", "for", "from",
    "how", "the", "with",
    "have", "into", "more", "only", "that", "their", "there", "these", "they", "this",
    "through", "what", "when", "where", "which", "while", "with", "would", "your",
    "question", "source", "sources", "passage", "evidence", "answer", "according",
}
_METADATA_MARKERS = (
    "retrieved passages", "passages are from", "publication", "published", "published in", "url", "pipeline", "metadata",
    "search failed", "content type", "retrieval warning", "discovered", "source count",
)


def _tokens(value: str) -> set[str]:
    return {
        token[:7] if len(token) > 7 else token
        for token in re.findall(r"[a-z][a-z'-]{2,}", (value or "").casefold())
        if token not in _STOPWORDS
    }


def _anchors(question_understanding: dict[str, Any]) -> set[str]:
    concepts = question_understanding.get("key_concepts") or question_understanding.get("concepts") or []
    anchors: set[str] = set()
    for item in concepts:
        value = item.get("label") or item.get("concept") if isinstance(item, dict) else item
        if value:
            anchors.add(str(value).casefold())
            anchors.update(_tokens(str(value)))
    for relationship in question_understanding.get("relationships") or []:
        if isinstance(relationship, dict):
            anchors.update(
                str(relationship.get(key) or "").casefold()
                for key in ("source", "target")
                if relationship.get(key)
            )
    requirements = question_understanding.get("answerability_requirements") or question_understanding.get("research_requirements") or []
    for requirement in requirements:
        for anchor in requirement.get("anchors") or []:
            if anchor:
                anchors.add(str(anchor).casefold())
    return {item[:7] if len(item) > 7 else item for item in anchors}


def _requirement_coverage(response: str, requirements: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    response_tokens = _tokens(response)
    covered = []
    for requirement in requirements:
        anchors = {str(item).casefold()[:7] for item in requirement.get("anchors") or [] if item}
        if not anchors:
            anchors = {
                token[:7]
                for token in _tokens(
                    str(requirement.get("question_component") or requirement.get("description") or "")
                )
            }
        matched = sorted(response_tokens & anchors)
        required = bool(requirement.get("required", True))
        covered.append({
            "requirement_id": requirement.get("requirement_id"),
            "description": requirement.get("description"),
            "required": required,
            "matched_anchors": matched,
            "status": "PASS" if matched else ("FAIL" if required else "UNRESOLVED"),
        })
    required_items = [item for item in covered if item["required"]]
    status = "PASS" if required_items and all(item["status"] == "PASS" for item in required_items) else "FAIL"
    if not required_items:
        status = "PASS" if response_tokens else "FAIL"
    return status, covered


class SynthesisValidationService:
    """Validate source support, relevance, coverage, and epistemic boundaries."""

    def __init__(self, session: AsyncSession | None = None):
        self.session = session

    @staticmethod
    def validate_answerability(
        query: str,
        response: str,
        question_understanding: dict[str, Any] | None = None,
        passages: list[dict[str, Any]] | None = None,
        claims: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        understanding = question_understanding or {}
        passages = passages or []
        claims = claims or []
        text = " ".join((response or "").split())
        anchors = _anchors(understanding)
        response_tokens = _tokens(text)
        relevant_overlap = response_tokens & anchors
        metadata_hits = [marker for marker in _METADATA_MARKERS if marker in text.casefold()]
        direct_response = bool(text) and bool(relevant_overlap) and not (len(metadata_hits) >= 2 and len(relevant_overlap) <= 1)

        requirements = understanding.get("answerability_requirements") or understanding.get("research_requirements") or []
        coverage_status, coverage = _requirement_coverage(text, requirements)

        cited_labels = {int(item) for item in re.findall(r"\[P(\d+)\]", text)}
        evidence_reasons: list[str] = []
        unsupported_claims: list[str] = []
        if re.search(
            r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
            text,
            re.IGNORECASE,
        ):
            evidence_reasons.append("The response exposes an internal identifier instead of a public evidence reference.")
        bracketed_references = re.findall(r"\[([^\[\]]+)\]", text)
        if any(not re.fullmatch(r"P\d+", reference.strip()) for reference in bracketed_references):
            evidence_reasons.append("The response contains an unrecognized citation marker.")
        if passages and not cited_labels:
            evidence_reasons.append("The response contains no inline references to the available substantive passages.")
        for label in sorted(cited_labels):
            passage = passages[label - 1] if 1 <= label <= len(passages) else None
            if passage is None:
                evidence_reasons.append(f"[P{label}] does not identify a retrieved passage.")
                continue
            if not is_substantive_passage(passage):
                evidence_reasons.append(f"[P{label}] is metadata-only or has no substantive passage text.")
                continue
            passage_tokens = _tokens(str(passage.get("content") or passage.get("passage_text") or ""))
            response_without_citation = re.sub(r"\[P\d+\]", "", text)
            if not (_tokens(response_without_citation) & passage_tokens):
                evidence_reasons.append(f"[P{label}] does not support the propositions stated near its citation.")
        for claim in claims:
            statement = str(claim.get("statement") or "")
            if (
                statement
                and anchors
                and not (_tokens(statement) & anchors)
                and not claim.get("relevance_to_question")
            ):
                unsupported_claims.append(statement)
        if unsupported_claims:
            evidence_reasons.append("One or more extracted claims cannot be connected to a question requirement.")
        evidence_status = "PASS" if passages and cited_labels and not evidence_reasons and not unsupported_claims else "FAIL"

        metadata_leakage = bool(metadata_hits) and len(metadata_hits) >= 2 and len(relevant_overlap) <= 1
        if metadata_leakage:
            coverage_status = "FAIL"
        epistemic_status = "PASS"
        epistemic_reasons: list[str] = []
        if re.search(r"\b(proves|proven|certainly|always|never|irrefutable)\b", text, re.IGNORECASE) and not re.search(r"\b(limited|uncertain|does not establish|cannot conclude)\b", text, re.IGNORECASE):
            epistemic_status = "FAIL"
            epistemic_reasons.append("The response uses unqualified certainty for an interpretive or evidence-bounded answer.")

        gates = {
            "answerability": "PASS" if direct_response else "FAIL",
            "relevance": "PASS" if direct_response and not metadata_leakage else "FAIL",
            "evidence_support": evidence_status,
            "synthesis": "PASS" if direct_response and coverage_status == "PASS" else "FAIL",
            "question_coverage": coverage_status,
            "epistemic_calibration": epistemic_status,
        }
        critical = all(value == "PASS" for value in gates.values())
        return {
            "status": "PASS" if critical else "FAIL",
            "is_approved": critical,
            "gates": gates,
            **gates,
            "question": query,
            "relevant_anchors": sorted(relevant_overlap),
            "question_coverage_details": coverage,
            "metadata_leakage": metadata_leakage,
            "metadata_markers": metadata_hits,
            "evidence_reasons": evidence_reasons,
            "epistemic_reasons": epistemic_reasons,
            "unsupported_claims": unsupported_claims,
            "reason": "; ".join(evidence_reasons + epistemic_reasons) or ("The response does not directly cover the represented question." if not critical else "All answerability gates passed."),
        }

    async def validate_research_output(
        self,
        claims: list[dict[str, Any]],
        research_scope: str | None = None,
        *,
        question: str = "",
        question_understanding: dict[str, Any] | None = None,
        passages: list[dict[str, Any]] | None = None,
        response: str | None = None,
        semantic_audit: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        validated = []
        blocked = []
        warnings = []
        passage_map = {item.get("passage_id"): item for item in (passages or []) if item.get("passage_id")}
        anchors = _anchors(question_understanding or {})
        for claim in claims:
            item = dict(claim)
            passage_id = item.get("passage_id")
            passage = passage_map.get(passage_id)
            if self.session and passage_id:
                passage_model = await self.session.get(PassageModel, passage_id)
                if not passage_model:
                    blocked.append({**item, "reason": "Fabricated or non-existent citation reference"})
                    continue
            if passage is not None and not is_substantive_passage(passage):
                blocked.append({**item, "reason": "Metadata-only evidence cannot support a substantive claim"})
                continue
            statement = str(item.get("statement") or "")
            if (
                anchors
                and not (_tokens(statement) & anchors)
                and not item.get("relevance_to_question")
            ):
                blocked.append({**item, "reason": "Claim is not relevant to a represented question requirement"})
                continue
            confidence = item.get("confidence", 0.95)
            if confidence > 0.95 and re.search(r"\b(absolute|irrefutable|universal|always|never)\b", statement, re.IGNORECASE):
                warnings.append({"statement": statement, "reason": "High-confidence universal language was downgraded."})
                confidence = 0.5
            validated.append({**item, "passage_id": passage_id, "confidence": confidence, "is_verified": True})

        claim_status = "PASS" if not blocked and (bool(validated) or not claims) else "FAIL"
        answerability = None
        if response is not None:
            answerability = self.validate_answerability(question, response, question_understanding, passages, validated)
            if semantic_audit is not None:
                answerability["semantic_audit"] = semantic_audit
                semantic_ok = (
                    semantic_audit.get("status") == "llm"
                    and bool(semantic_audit.get("addresses_question"))
                    and not bool(semantic_audit.get("topic_drift"))
                    and not semantic_audit.get("irrelevant_or_unsupported_claims")
                    and bool(semantic_audit.get("conclusion_follows", True))
                    and not bool(semantic_audit.get("answer_is_source_summary"))
                    and bool(semantic_audit.get("sufficient_for_answer"))
                    and not answerability.get("metadata_leakage")
                )
                cited_labels = {int(item) for item in re.findall(r"\[P(\d+)\]", response or "")}
                cited_passage_ids = {
                    passages[label - 1].get("passage_id")
                    for label in cited_labels
                    if 1 <= label <= len(passages)
                }
                audited_support = {
                    item.get("passage_id"): item.get("supports")
                    for item in semantic_audit.get("evidence_alignment", [])
                    if isinstance(item, dict)
                }
                semantic_evidence_ok = bool(cited_passage_ids) and all(
                    audited_support.get(passage_id) is True
                    for passage_id in cited_passage_ids
                )
                semantic_ok = semantic_ok and semantic_evidence_ok
                answerability["semantic_alignment"] = "PASS" if semantic_ok else "FAIL"
                answerability["gates"]["semantic_alignment"] = answerability["semantic_alignment"]
                if semantic_ok:
                    # The question-specific audit is the semantic judge. Keep
                    # structural citation and metadata checks, but do not let
                    # lexical overlap reject a compositionally valid answer.
                    answerability["answerability"] = "PASS"
                    answerability["relevance"] = "PASS"
                    answerability["question_coverage"] = "PASS"
                    answerability["synthesis"] = "PASS"
                    answerability["gates"]["question_coverage"] = answerability["question_coverage"]
                    answerability["gates"]["synthesis"] = answerability["synthesis"]
                    answerability["gates"]["answerability"] = answerability["answerability"]
                    answerability["gates"]["relevance"] = answerability["relevance"]
                    lexical_evidence_failures = [
                        reason for reason in answerability.get("evidence_reasons", [])
                        if "does not support the propositions stated near its citation" in reason
                    ]
                    structural_evidence_failures = [
                        reason for reason in answerability.get("evidence_reasons", [])
                        if reason not in lexical_evidence_failures
                    ]
                    if not structural_evidence_failures:
                        answerability["evidence_support"] = "PASS"
                        answerability["gates"]["evidence_support"] = "PASS"
                if not semantic_ok:
                    answerability["reason"] = "; ".join(
                        item for item in (
                            answerability.get("reason"),
                            semantic_audit.get("reason"),
                        ) if item
                    )
        if answerability is not None and "semantic_alignment" in answerability:
            answerability["is_approved"] = all(value == "PASS" for value in answerability["gates"].values())
            answerability["status"] = "PASS" if answerability["is_approved"] else "FAIL"
        approved = claim_status == "PASS" and (answerability is None or answerability["is_approved"])
        return {
            "status": "APPROVED" if approved else "BLOCKED_OR_DOWNGRADED",
            "validated_claims": validated,
            "total_claims": len(claims),
            "approved_claims": len(validated),
            "blocked_claims": blocked,
            "warnings": warnings,
            "answerability": answerability,
            "is_safe_for_publication": approved,
            "research_scope": research_scope,
        }
