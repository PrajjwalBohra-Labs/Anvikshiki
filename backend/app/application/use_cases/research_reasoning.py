"""Conservative provenance and structural helpers for adaptive reasoning.

Semantic interpretation belongs to the LLM-led workflow in
``adaptive_reasoning.py``. The helpers here deliberately do not classify
questions, select traditions, infer concepts, or decide that two sources
agree or conflict from shared words.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any


_STOPWORDS = {
    "about", "after", "against", "also", "and", "because", "been", "being",
    "between", "but", "could", "does", "for", "from", "have", "how", "into",
    "more", "only", "that", "the", "their", "there", "these", "they", "this",
    "through", "what", "when", "where", "which", "while", "with", "would", "your",
}


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z][a-z'-]{2,}", (value or "").casefold())
        if token not in _STOPWORDS
    }


def is_substantive_passage(passage: dict[str, Any] | None) -> bool:
    """Return true only when a candidate contains text usable as evidence."""
    if not isinstance(passage, dict) or passage.get("metadata_only"):
        return False
    content = " ".join(str(passage.get("content") or passage.get("passage_text") or "").split())
    if len(content) < 24:
        return False
    metadata = " ".join(
        str(passage.get(key) or "")
        for key in ("source_title", "author", "url", "source_reference_url")
    )
    return content.casefold() not in metadata.casefold()


def work_identity(source: dict[str, Any] | None) -> str:
    """Group versions/archives of one work without making an intellectual judgment."""
    source = source or {}
    explicit = source.get("work_id") or source.get("canonical_work_id")
    if explicit:
        return str(explicit)
    canonical = source.get("canonical_url") or source.get("source_reference_url") or source.get("url")
    title = re.sub(r"\s+", " ", str(source.get("source_title") or source.get("title") or "").casefold()).strip()
    author = re.sub(r"\s+", " ", str(source.get("author") or "").casefold()).strip()
    if canonical:
        canonical = re.sub(r"[?#].*$", "", str(canonical)).rstrip("/").casefold()
    return "|".join((canonical or title or str(source.get("source_id") or ""), author)) or "unknown-work"


def group_underlying_works(sources: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in sources:
        item = dict(source)
        item["work_id"] = work_identity(item)
        grouped[item["work_id"]].append(item)
    return dict(grouped)


def source_diversity_metrics(sources: list[dict[str, Any]]) -> dict[str, int]:
    groups = group_underlying_works(sources)
    authors = {str(item.get("author")).casefold() for item in sources if item.get("author")}
    traditions = {
        str(item.get("tradition") or item.get("school")).casefold()
        for item in sources
        if item.get("tradition") or item.get("school")
    }
    positions = {
        str(item.get("position_id") or item.get("central_position") or item.get("source_id"))
        for item in sources
    }
    return {
        "retrieved_documents": len(sources),
        "unique_works": len(groups),
        "unique_authors": len(authors),
        "unique_traditions": len(traditions),
        "unique_positions": len(positions),
        "independent_evidence_clusters": len(groups),
    }


def classify_question(query: str, domain: str | None = None, depth: str = "standard") -> dict[str, Any]:
    """Return a non-semantic compatibility representation.

    Production orchestration uses the LLM result from ``adaptive_reasoning``.
    This fallback preserves the old helper without pretending that a keyword
    scan understands the inquiry.
    """
    normalized = " ".join((query or "").split())
    return {
        "original_question": query,
        "literal_question": normalized,
        "central_problem": normalized,
        "requested_task": normalized,
        "inquiry_mode": "undetermined",
        "concepts": [],
        "relationships": [],
        "assumptions": [],
        "interpretations": [],
        "research_needed": bool(normalized),
        "research_requirements": [{
            "requirement_id": "question_scope",
            "question_component": normalized,
            "evidence_needed": "Substantive evidence that directly addresses the question.",
            "search_queries": [normalized] if normalized else [],
            "sufficiency_test": "A source must address the question itself.",
            "required": True,
        }],
        "answer_strategy": {"depth": depth, "order": ["direct answer", "evidence", "qualifications"]},
        "domain_context": domain or "",
        "analysis_status": "fallback_unavailable",
    }


def build_research_plan(question: dict[str, Any]) -> list[dict[str, Any]]:
    """Expose only research requirements already supplied by the caller/model."""
    plan = []
    for item in question.get("research_requirements", []):
        if not isinstance(item, dict):
            continue
        plan.append({
            "requirement_id": item.get("requirement_id"),
            "question": item.get("question_component"),
            "purpose": item.get("why_needed"),
            "search_terms": item.get("search_queries", []),
            "expected_evidence": item.get("evidence_needed"),
            "source_preferences": item.get("source_preferences", []),
            "sufficiency_test": item.get("sufficiency_test"),
            "required": item.get("required", True),
        })
    return plan


def extract_source_positions(passages: list[dict[str, Any]], claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create passage-linked records without reconstructing an argument."""
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for claim in claims:
        key = claim.get("source_title") or claim.get("source_id") or "Unknown source"
        by_source[key].append(claim)
    passage_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for passage in passages:
        key = passage.get("source_title") or passage.get("source_id") or "Unknown source"
        passage_by_source[key].append(passage)

    positions = []
    for source_key, source_claims in by_source.items():
        source_passages = passage_by_source[source_key]
        direct = [item.get("statement") for item in source_claims[:8] if item.get("statement")]
        positions.append({
            "source_id": source_passages[0].get("source_id") if source_passages else None,
            "work_id": work_identity(source_passages[0]) if source_passages else None,
            "source_title": source_key,
            "author": source_passages[0].get("author") if source_passages else None,
            "source_type": source_passages[0].get("source_type") if source_passages else None,
            "central_position": direct[0] if direct else "",
            "direct_statements": direct,
            "argument": "No model reconstruction was available; these are passage-linked statements only.",
            "evidence_passage_ids": [item.get("passage_id") for item in source_passages if item.get("passage_id")],
            "assumptions": [],
            "qualifications": [],
            "limitations": ["The passage may not contain the source's complete argument."],
            "statement_status": "direct_statement" if direct else "unresolved",
            "epistemic_status": "SOURCE_STATEMENT" if direct else "INSUFFICIENT_EVIDENCE",
            "interpretation_boundary": "Any argument beyond the direct statements requires model analysis.",
        })
    return positions


def compare_source_positions(positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return unresolved pairs; semantic relations require the LLM judge."""
    relationships = []
    for index, left in enumerate(positions):
        for right in positions[index + 1:]:
            relationships.append({
                "source_a": left.get("source_title"),
                "source_b": right.get("source_title"),
                "relation": "unresolved",
                "explanation": "No model-based cross-source judgment was available; shared vocabulary is not treated as evidence of a relation.",
                "confidence": 0.0,
                "passage_ids": sorted(set((left.get("evidence_passage_ids") or []) + (right.get("evidence_passage_ids") or []))),
                "evidence_status": "requires_adaptive_reasoning",
            })
    return relationships


def build_reasoning_chains(
    question: dict[str, Any],
    passages: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    positions: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build only direct source-support records as a conservative fallback."""
    chains = []
    for claim in claims[:16]:
        if not claim.get("passage_id"):
            continue
        chains.append({
            "claim": claim.get("statement", ""),
            "evidence": [claim["passage_id"]],
            "sources": [claim.get("source_title")] if claim.get("source_title") else [],
            "relationship": "direct_source_support",
            "confidence": claim.get("confidence", 0.0),
            "type": claim.get("claim_type", "UNCERTAIN"),
            "analysis": "Direct statement extracted from a cited passage; no additional interpretation is asserted.",
            "conclusion": "The passage supports only the proposition stated within its scope.",
            "inference_status": "direct_statement",
        })
    gaps = []
    if not passages:
        gaps.append("No relevant substantive passage was available for an evidence-grounded answer.")
    if not positions:
        gaps.append("No source position could be reconstructed from relevant evidence.")
    if len(positions) < 2 and passages:
        gaps.append("Cross-source comparison is unresolved because fewer than two source positions were established.")
    return {
        "chains": chains,
        "gaps": gaps,
        "alternatives": [],
        "source_position_count": len(positions),
        "relationship_count": len(relationships),
        "status": "deterministic_fallback",
    }


def build_provenance_payload(
    query: str,
    question: dict[str, Any],
    plan: list[dict[str, Any]],
    passages: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    positions: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    chains: dict[str, Any],
) -> dict[str, Any]:
    """Keep the inspectable chain without exposing hidden reasoning in prose."""
    return {
        "question": query,
        "question_understanding": question,
        "research_plan": plan,
        "sources": [
            {
                "source_id": item.get("source_id"),
                "work_id": item.get("work_id"),
                "source_title": item.get("source_title"),
                "author": item.get("author"),
                "source_type": item.get("source_type"),
            }
            for item in positions
        ],
        "passages": [
            {
                "passage_id": item.get("passage_id"),
                "source_id": item.get("source_id"),
                "source_title": item.get("source_title"),
            }
            for item in passages
        ],
        "claims": [
            {
                "claim_id": item.get("claim_id"),
                "passage_id": item.get("passage_id"),
                "statement": item.get("statement"),
                "claim_type": item.get("claim_type"),
            }
            for item in claims
        ],
        "source_diversity": source_diversity_metrics(passages),
        "source_positions": positions,
        "relationships": relationships,
        "synthesis": chains,
    }
