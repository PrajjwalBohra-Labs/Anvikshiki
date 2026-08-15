"""
Reasoning Engine (§6 Cognitive Subsystems; implements the §13
Reasoning Model end to end):

    Problem -> Definitions -> Facts -> Evidence -> Assumptions ->
    Constraints -> Relationships -> Inference -> Alternatives ->
    Confidence -> Conclusion

Hard rule: no natural-language generation happens here (§13). This
module never calls LLMAdapter.generate()/.stream() -- there is no
llm_adapter parameter at all.

comparisons (added post-Step-19) reuses the exact same pairwise
agreement/divergence logic the Research Engine uses -- so a
"contradictions detected" count shown anywhere in the UI is a real,
computed signal shared across both engines, not two different
half-truths.

Confidence (§15) is computed from five sub-scores, averaged. First-
pass formula, not a claim of calibrated probability.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from app.persistence import relational_db
from app.services.context.context_builder import ContextObject
from app.services.knowledge.comparison import compare_chunks

MIN_EXPECTED_SOURCES = 3  # heuristic denominator for source_availability, not a spec number


@dataclass
class ConfidenceBreakdown:
    source_availability: float
    agreement_among_sources: float
    reasoning_completeness: float
    context_quality: float
    retrieval_quality: float
    overall: float


@dataclass
class ReasoningObject:
    problem: str
    definitions: list[dict] = field(default_factory=list)
    facts: list[dict] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    relationships: list[dict] = field(default_factory=list)
    comparisons: list[dict] = field(default_factory=list)
    inference: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)
    confidence: ConfidenceBreakdown | None = None
    conclusion: dict = field(default_factory=dict)


def reason(query: str, context: ContextObject) -> ReasoningObject:
    """Runs the full §13 pipeline. Deliberately takes no llm_adapter --
    this engine cannot call a provider even by mistake."""

    problem = query.strip()
    chunks = context.retrieved_chunks

    concept_ids = sorted(
        {chunk.metadata.get("concept_id") for chunk in chunks if chunk.metadata.get("concept_id")}
    )

    definitions = _build_definitions(concept_ids)
    facts = _build_facts(chunks)
    evidence = _build_evidence(chunks)
    assumptions = _build_assumptions(chunks)
    constraints = _build_constraints(context)
    relationships = _build_relationships(concept_ids)
    comparisons = compare_chunks(chunks)
    inference = [chunk.chunk_id for chunk in chunks]
    alternatives = [chunk.chunk_id for chunk in chunks[1:]]

    confidence = _compute_confidence(
        chunks=chunks, definitions=definitions, relationships=relationships, context=context
    )

    conclusion = {
        "primary_chunk_id": chunks[0].chunk_id if chunks else None,
        "supporting_relationship_count": len(relationships),
        "requires_generation": True,
    }

    return ReasoningObject(
        problem=problem,
        definitions=definitions,
        facts=facts,
        evidence=evidence,
        assumptions=assumptions,
        constraints=constraints,
        relationships=relationships,
        comparisons=comparisons,
        inference=inference,
        alternatives=alternatives,
        confidence=confidence,
        conclusion=conclusion,
    )


def _build_definitions(concept_ids: list[str]) -> list[dict]:
    definitions = []
    for concept_id in concept_ids:
        concept = relational_db.get_concept(concept_id)
        if concept:
            definitions.append(
                {"concept_id": concept_id, "name": concept["name"], "description": concept["description"]}
            )
    return definitions


def _build_facts(chunks) -> list[dict]:
    return [{"chunk_id": chunk.chunk_id, "text": chunk.chunk_text} for chunk in chunks]


def _build_evidence(chunks) -> list[dict]:
    return [
        {
            "chunk_id": chunk.chunk_id,
            "source_document_id": chunk.document_id,
            "source_document_title": chunk.document_title,
            "source_type": chunk.source_type,
            "source_url": chunk.metadata.get("url"),
            "concept_id": chunk.metadata.get("concept_id"),
            "score": chunk.score,
        }
        for chunk in chunks
    ]


def _build_assumptions(chunks) -> list[str]:
    if not chunks:
        return ["no_retrieved_evidence"]
    if len(chunks) < MIN_EXPECTED_SOURCES:
        return ["limited_source_coverage"]
    return []


def _build_constraints(context: ContextObject) -> list[str]:
    if context.max_tokens and context.total_estimated_tokens >= context.max_tokens:
        return ["context_token_budget_reached"]
    return []


def _build_relationships(concept_ids: list[str]) -> list[dict]:
    relationships = []
    for concept_id in concept_ids:
        relationships.extend(relational_db.get_relationships_for("concept", concept_id))
    return relationships


def _compute_confidence(chunks, definitions, relationships, context: ContextObject) -> ConfidenceBreakdown:
    source_availability = min(1.0, len(chunks) / MIN_EXPECTED_SOURCES)

    if len(chunks) <= 1:
        agreement_among_sources = 1.0 if chunks else 0.0
    else:
        scores = [chunk.score for chunk in chunks]
        mean_score = statistics.mean(scores)
        if mean_score > 0:
            coefficient_of_variation = statistics.pstdev(scores) / mean_score
            agreement_among_sources = max(0.0, 1.0 - min(1.0, coefficient_of_variation))
        else:
            agreement_among_sources = 0.0

    completeness_signals = [bool(definitions), bool(chunks), bool(relationships)]
    reasoning_completeness = sum(completeness_signals) / len(completeness_signals)

    context_quality = (
        min(1.0, context.total_estimated_tokens / context.max_tokens) if context.max_tokens else 0.0
    )

    retrieval_quality = statistics.mean([c.score for c in chunks]) if chunks else 0.0

    subscores = [
        source_availability,
        agreement_among_sources,
        reasoning_completeness,
        context_quality,
        retrieval_quality,
    ]
    overall = statistics.mean(subscores)

    return ConfidenceBreakdown(
        source_availability=source_availability,
        agreement_among_sources=agreement_among_sources,
        reasoning_completeness=reasoning_completeness,
        context_quality=context_quality,
        retrieval_quality=retrieval_quality,
        overall=overall,
    )

