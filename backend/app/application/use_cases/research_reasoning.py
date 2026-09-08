"""Deterministic reasoning structures used by the research workflow.

This module deliberately does not invent source content.  It turns the user
question and already-acquired passages into inspectable planning and
comparison records.  Any statement about a source is kept as a passage-level
observation; cross-source conclusions are explicitly marked as inference or
synthesis.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any


_STOPWORDS = {
    "about", "after", "against", "also", "because", "being", "between",
    "could", "from", "have", "into", "more", "only", "that", "their",
    "there", "these", "they", "this", "through", "what", "when", "where",
    "which", "while", "with", "would", "your", "does", "doesn", "remain",
}

_CONCEPT_LEXICON: dict[str, tuple[str, ...]] = {
    "perceptual_experience": ("perceptual experience",),
    "perception": ("perception", "perceptions", "perceptual"),
    "experience": ("experience", "experiences", "experiential"),
    "awareness": ("awareness", "aware"),
    "consciousness": ("consciousness", "conscious"),
    "cognition": ("cognition", "cognitive"),
    "subject": ("subject", "self", "identity", "observer"),
    "continuity": ("continuity", "continuous", "persist", "stable", "invariant"),
    "stationary": ("stationary", "unchanging", "invariant"),
    "change": ("change", "changes", "changing", "difference", "variation", "alter"),
    "time": ("time", "temporal", "duration", "moment", "sequence", "successive"),
    "memory": ("memory", "remember", "retention", "recollection"),
    "meaning": ("meaning", "sense", "interpretation", "significance"),
}

_AMBIGUOUS_CONCEPTS: dict[str, list[str]] = {
    "experience": [
        "experiential content",
        "a temporally extended stream of consciousness",
        "memory or retention of successive states",
        "the identity of a subject or object",
    ],
    "stationary": [
        "literally unchanging content",
        "continuity across temporal change",
        "a stable subject or awareness rather than stable contents",
    ],
    "continuity": [
        "numerical identity through time",
        "connectedness between successive states",
        "a construction supplied by memory or retention",
    ],
    "self": [
        "an enduring metaphysical subject",
        "a psychological or narrative identity",
        "a practical first-person point of view",
    ],
}


def _tokens(value: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z][a-z'-]{2,}", value.casefold())
        if token not in _STOPWORDS
    }


def _sentences(value: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", value.strip())
        if sentence.strip()
    ]


def is_substantive_passage(passage: dict[str, Any] | None) -> bool:
    """Return true only when a candidate contains source text usable as evidence."""
    if not isinstance(passage, dict) or passage.get("metadata_only"):
        return False
    content = " ".join(str(passage.get("content") or passage.get("passage_text") or "").split())
    if len(content) < 24:
        return False
    metadata = " ".join(str(passage.get(key) or "") for key in ("source_title", "author", "url", "source_reference_url"))
    return content.casefold() not in metadata.casefold()


def work_identity(source: dict[str, Any] | None) -> str:
    """Group versions/archives of one underlying work without conflating authors."""
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
    """Return version-aware work groups for diversity metrics and comparison."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in sources:
        item = dict(source)
        item["work_id"] = work_identity(item)
        grouped[item["work_id"]].append(item)
    return dict(grouped)


def source_diversity_metrics(sources: list[dict[str, Any]]) -> dict[str, int]:
    """Count intellectual diversity without treating archived copies as works."""
    groups = group_underlying_works(sources)
    authors = {str(item.get("author")).casefold() for item in sources if item.get("author")}
    traditions = {str(item.get("tradition") or item.get("school")).casefold() for item in sources if item.get("tradition") or item.get("school")}
    positions = {str(item.get("position_id") or item.get("central_position") or item.get("source_id")) for item in sources}
    return {
        "retrieved_documents": len(sources),
        "unique_works": len(groups),
        "unique_authors": len(authors),
        "unique_traditions": len(traditions),
        "unique_positions": len(positions),
        "independent_evidence_clusters": len(groups),
    }


def _concepts_in_question(text: str) -> list[str]:
    lower = text.casefold()
    concepts = [
        concept
        for concept, variants in _CONCEPT_LEXICON.items()
        if any(re.search(rf"\b{re.escape(variant)}\w*\b", lower) for variant in variants)
    ]
    if "perceptual_experience" in concepts and "perception" in concepts:
        concepts.remove("perception")
    return concepts


def _question_type(lower: str, philosophical: bool, comparative: bool, verification: bool, fact_like: bool, explanation: bool, source_request: bool) -> str:
    if comparative:
        return "comparative_question"
    if source_request:
        return "source_focused_response"
    if verification or fact_like:
        return "fact_verification"
    if philosophical and explanation:
        return "philosophical_analysis"
    if explanation:
        return "conceptual_explanation"
    return "direct_qa"


def _build_answerability_requirements(
    concepts: list[str],
    lower: str,
    question_type: str,
    ambiguities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []
    for concept in concepts:
        requirements.append({
            "requirement_id": f"concept_{concept}",
            "kind": "concept_clarification",
            "description": f"Clarify what '{concept}' means in this question.",
            "anchors": [concept],
            "required": True,
        })
    temporal = "time" in concepts or "continuity" in concepts
    relational = len(concepts) > 1 and any(marker in lower for marker in (" but ", " while ", " versus ", " vs ", " although ", " yet ", " remains "))
    if temporal:
        requirements.append({
            "requirement_id": "temporal_dimension",
            "kind": "temporal_analysis",
            "description": "Explain what the temporal language changes or presupposes.",
            "anchors": ["time", "temporal", "change", "continuity", "duration"],
            "required": True,
        })
    if relational:
        requirements.append({
            "requirement_id": "concept_relationship",
            "kind": "relationship_analysis",
            "description": "Explain the relation between the concepts rather than discussing them separately.",
            "anchors": concepts,
            "required": True,
        })
    if ambiguities:
        requirements.append({
            "requirement_id": "ambiguity_handling",
            "kind": "ambiguity",
            "description": "State how materially different meanings affect the answer.",
            "anchors": [item.get("concept", "") for item in ambiguities],
            "required": question_type in {"philosophical_analysis", "comparative_question"},
        })
    requirements.append({
        "requirement_id": "direct_response",
        "kind": "requested_task",
        "description": "Give a conclusion that directly responds to the user's wording.",
        "anchors": [token for token in _tokens(lower) if len(token) >= 4][:8],
        "required": True,
    })
    return requirements


def analyze_terminology(concepts: list[str], question: str) -> dict[str, Any]:
    """Keep lexical similarity separate from conceptual identity."""
    lower = question.casefold()
    terms = []
    for concept in concepts:
        meanings = _AMBIGUOUS_CONCEPTS.get(concept, [f"the context-specific sense of {concept}"])
        terms.append({
            "term": concept,
            "concept_id": concept,
            "status": "ambiguous" if concept in _AMBIGUOUS_CONCEPTS else "contextual",
            "possible_senses": meanings,
            "framework_specific": concept in {"awareness", "consciousness", "subject", "self"},
        })
    pairs = []
    for index, left in enumerate(concepts):
        for right in concepts[index + 1:]:
            if {left, right} <= {"perceptual_experience", "experience"}:
                relation = "nested"
            elif "translation" in lower or "translated" in lower:
                relation = "translation_equivalent_candidate"
            elif {left, right} <= {"awareness", "consciousness", "subject", "self"}:
                relation = "framework_specific"
            elif any(marker in lower for marker in (" versus ", " vs ", "competing", "different")):
                relation = "competing_or_contrasting"
            else:
                relation = "related_but_not_equivalent"
            pairs.append({"left": left, "right": right, "relation": relation})
    return {"terms": terms, "relations": pairs}


def classify_question(query: str, domain: str | None = None, depth: str = "standard") -> dict[str, Any]:
    """Return a compact, user-question-first interpretation.

    The rules are intentionally conservative.  They identify tensions and
    ambiguities without selecting a philosophical theory on the user's behalf.
    """
    normalized = " ".join((query or "").split())
    lower = normalized.casefold()
    philosophical = any(term in lower for term in (
        "experience", "perception", "consciousness", "awareness", "phenomen",
        "identity", "memory", "meaning", "reality", "philosoph",
    )) or "philosoph" in (domain or "").casefold()
    comparative = any(term in lower for term in ("compare", "versus", " vs ", "difference", "traditions", "schools"))
    verification = lower.startswith(("is ", "are ", "does ", "do ", "can ", "was ", "were ")) or "true" in lower
    fact_like = lower.startswith(("what is ", "who is ", "where is ", "when was ", "how many "))
    source_request = any(term in lower for term in ("sources", "citations", "literature", "references"))
    explanation = lower.startswith(("how ", "why ", "what is ", "explain ", "how does "))

    key_concepts = _concepts_in_question(normalized)
    if not key_concepts:
        key_concepts = sorted(_tokens(normalized))[:8] or ["question"]
    intent = _question_type(lower, philosophical, comparative, verification, fact_like, explanation, source_request)
    ambiguities: list[dict[str, Any]] = []
    for concept in key_concepts:
        if concept in _AMBIGUOUS_CONCEPTS:
            ambiguities.append({
                "concept": concept,
                "possible_meanings": _AMBIGUOUS_CONCEPTS[concept],
                "handling": "Keep the meanings distinct and test which one the evidence supports; do not collapse them into synonyms.",
            })

    temporal = any(item in key_concepts for item in ("time", "continuity", "change"))
    relational = len(key_concepts) > 1 and any(marker in lower for marker in (" but ", " while ", " versus ", " vs ", " although ", " yet ", " remains "))
    premise_challenges: list[str] = []
    if relational:
        premise_challenges.append("The wording may compare properties that belong to different levels of analysis; test whether the apparent tension is genuine.")
    if temporal:
        premise_challenges.append("Temporal continuity does not by itself establish identity, invariance, or an unchanging subject.")
    if verification:
        premise_challenges.append("Check whether the wording assumes more than the available evidence establishes.")

    central_problem = normalized
    underlying_question = normalized
    if relational and temporal:
        left = next((item for item in key_concepts if item in {"perception", "experience", "awareness", "consciousness", "cognition"}), key_concepts[0])
        right = next((item for item in key_concepts if item != left and item in {"experience", "awareness", "consciousness", "continuity", "change"}), key_concepts[-1])
        if left == "perception" and right == "experience":
            central_problem = "Changing perceptual content versus the claimed continuity or stability of experience"
        else:
            central_problem = f"The relation between changing {left} and the claimed continuity or stability of {right}"
        underlying_question = "How should the question's changing and stable aspects be distinguished across time, and what could explain their relation?"

    disciplines: list[str] = []
    traditions: list[str] = []
    schools: list[str] = []
    indian_signals = ("indian", "nyaya", "buddhist", "advaita", "vedanta", "pramana", "sanskrit", "darshan")
    if philosophical:
        disciplines.extend(["philosophy", "phenomenology"])
        if any(signal in lower or signal in (domain or "").casefold() for signal in indian_signals):
            traditions.extend(["Nyaya", "Buddhist philosophy", "Advaita Vedanta"])
            schools.extend(["Nyaya", "Madhyamaka", "Advaita"])
    if any(term in lower for term in ("memory", "cognitive", "brain", "neural", "perception")):
        disciplines.extend(["cognitive science", "psychology"])
    if not disciplines:
        disciplines.append(domain or "general research")

    answerability_requirements = _build_answerability_requirements(key_concepts, lower, intent, ambiguities)
    terminology_analysis = analyze_terminology(key_concepts, normalized)
    concept_relationships = []
    for index, left in enumerate(key_concepts):
        for right in key_concepts[index + 1:]:
            relation = "related"
            if {left, right} <= {"change", "continuity", "time"}:
                relation = "temporal_relation"
            elif relational and {left, right} & {"perception", "experience", "awareness", "consciousness", "cognition"}:
                relation = "potential_tension"
            concept_relationships.append({"source_concept": left, "target_concept": right, "relation": relation, "status": "contextual_not_equivalent"})

    return {
        "original_question": query,
        "normalized_question": normalized,
        "literal_question": normalized,
        "underlying_question": underlying_question,
        "central_problem": central_problem,
        "key_concepts": key_concepts,
        "concept_relationships": concept_relationships,
        "terminology_analysis": terminology_analysis,
        "assumptions": premise_challenges,
        "ambiguities": ambiguities,
        "premise_challenges": premise_challenges,
        "implicit_premises": premise_challenges,
        "possible_interpretations": [
            {"interpretation_id": "primary", "formulation": underlying_question, "confidence": 0.78 if ambiguities else 0.72},
            *[
                {"interpretation_id": f"alternative_{item['concept']}", "concept": item["concept"], "meanings": item["possible_meanings"], "confidence": 0.45}
                for item in ambiguities
            ],
        ],
        "requested_task": "explain and evaluate the relation expressed by the question" if explanation or relational else "answer the question directly",
        "required_research": bool(philosophical or intent in {"comparative_question", "source_focused_response"}),
        "answerability_requirements": answerability_requirements,
        "scope": "Question-local; use only acquired or indexed evidence returned for this run.",
        "answer_type": intent,
        "required_depth": depth if depth in {"brief", "standard", "deep"} else "standard",
        "disciplines": list(dict.fromkeys(disciplines)),
        "traditions": list(dict.fromkeys(traditions)),
        "schools": list(dict.fromkeys(schools)),
        "intellectual_tasks": [
            "clarify the concepts without treating related terms as equivalents",
            "reconstruct relevant source positions",
            "compare compatible and competing interpretations",
            "test the premise that experience is stationary",
        ] if philosophical else ["identify the question's terms and evaluate the available evidence"],
        "secondary_intents": ["comparative_interpretation", "premise_testing"] if philosophical else [],
        "interpretation_confidence": 0.78 if ambiguities else 0.72,
        "philosophical_or_interdisciplinary": philosophical,
    }


def build_research_plan(question: dict[str, Any]) -> list[dict[str, Any]]:
    """Create purposeful directions rather than a bag of keyword variants."""
    literal = question.get("literal_question", "")
    central = question.get("central_problem", literal)
    concepts = ", ".join(question.get("key_concepts", []))
    if question.get("answer_type") in {"direct_qa", "fact_verification"}:
        return [{
            "question": literal,
            "purpose": "Find the smallest set of authoritative evidence needed for a direct answer.",
            "search_terms": [literal],
            "expected_evidence": "A direct statement, measurement, or authoritative reference.",
            "disciplines_traditions": question.get("disciplines", []),
        }]

    directions = [
        {
            "question": f"What changes and what remains stable in: {central}?",
            "purpose": "Separate the properties being compared before accepting the premise.",
            "search_terms": [f"{concepts} conceptual distinction", f"{literal} definitions"],
            "expected_evidence": "Explicit definitions and distinctions between content, process, subject, and continuity.",
            "disciplines_traditions": question.get("disciplines", []),
        },
        {
            "question": f"What arguments explain continuity across changing states in: {central}?",
            "purpose": "Identify mechanisms or arguments that connect successive experiences.",
            "search_terms": [f"{concepts} temporal structure continuity", f"{concepts} memory retention"],
            "expected_evidence": "An author's position, premises, supporting passage, and qualifications.",
            "disciplines_traditions": ["phenomenology", "psychology", "cognitive science"],
        },
        {
            "question": f"Which traditions or disciplines answer {central} differently?",
            "purpose": "Compare frameworks without treating related vocabulary as equivalent theories.",
            "search_terms": [f"{concepts} philosophical traditions comparison", f"{concepts} scholarly interpretation"],
            "expected_evidence": "Primary texts where available, then scholarly commentary and empirical research.",
            "disciplines_traditions": list(dict.fromkeys(
                question.get("disciplines", [])
                + question.get("traditions", [])
                + (["Western philosophy"] if "philosophy" in question.get("disciplines", []) else [])
            )),
        },
        {
            "question": f"What evidence challenges or limits the premise in {central}?",
            "purpose": "Look for contradiction, qualification, alternative explanations, and unresolved gaps.",
            "search_terms": [f"{concepts} criticism counterargument", f"{concepts} limitations evidence"],
            "expected_evidence": "Explicit disagreement, methodological limits, or evidence that does not establish the stronger claim.",
            "disciplines_traditions": question.get("disciplines", []),
        },
    ]
    if question.get("required_depth") == "deep":
        directions.append({
            "question": f"What does the strongest evidence establish, and what does it leave unresolved about {central}?",
            "purpose": "Keep the final conclusion within the actual evidence boundary.",
            "search_terms": [f"{concepts} evidence review", f"{concepts} primary source"],
            "expected_evidence": "A source hierarchy, explicit uncertainty, and traceable synthesis.",
            "disciplines_traditions": question.get("disciplines", []),
        })
    return directions


def _qualification_markers(text: str) -> list[str]:
    lower = text.casefold()
    markers = []
    for marker in ("however", "but", "although", "yet", "may", "might", "does not", "not by itself", "only"):
        if marker in lower:
            markers.append(marker)
    return markers


def extract_source_positions(passages: list[dict[str, Any]], claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Represent what each source argues without upgrading reconstruction to quotation."""
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for claim in claims:
        key = claim.get("source_title") or claim.get("source_id") or "Unknown source"
        by_source[key].append(claim)
    passage_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for passage in passages:
        key = passage.get("source_title") or passage.get("source_id") or "Unknown source"
        passage_by_source[key].append(passage)

    positions: list[dict[str, Any]] = []
    for source_key, source_claims in by_source.items():
        source_passages = passage_by_source[source_key]
        text = " ".join(str(item.get("content", "")) for item in source_passages)
        direct = [item["statement"] for item in source_claims[:4] if item.get("statement")]
        positions.append({
            "source_id": source_passages[0].get("source_id") if source_passages else None,
            "work_id": work_identity(source_passages[0]) if source_passages else None,
            "source_title": source_key,
            "author": source_passages[0].get("author") if source_passages else None,
            "source_type": source_passages[0].get("source_type") if source_passages else None,
            "central_position": direct[0] if direct else "No source-level statement was extracted.",
            "direct_statements": direct,
            "argument": "Passage-level reconstruction from the extracted statements; not a verbatim source summary.",
            "evidence_passage_ids": [item.get("passage_id") for item in source_passages if item.get("passage_id")],
            "assumptions": [],
            "qualifications": _qualification_markers(text),
            "limitations": ["The retrieved passage may not contain the source's complete argument."],
            "statement_status": "direct_statement" if direct else "unresolved",
            "epistemic_status": "SOURCE_STATEMENT" if direct else "INSUFFICIENT_EVIDENCE",
            "interpretation_boundary": "Any argument beyond the direct statements is an interpretation or synthesis.",
        })
    return positions


def _explicit_conflict(left: str, right: str) -> bool:
    left_lower, right_lower = left.casefold(), right.casefold()
    shared = _tokens(left) & _tokens(right)
    if len(shared) < 2:
        return False
    negation_words = ("not", "never", "cannot", "doesn't", "isn't", "no ")
    left_negated = any(word in left_lower for word in negation_words)
    right_negated = any(word in right_lower for word in negation_words)
    causal_left = any(word in left_lower for word in ("causes", "causal", "proves", "establishes"))
    causal_right = any(word in right_lower for word in ("causes", "causal", "proves", "establishes"))
    if left_negated != right_negated and (causal_left or causal_right):
        return True
    return any(marker in left_lower or marker in right_lower for marker in ("contrary", "contradict", "in contrast"))


def compare_source_positions(positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Correlate source positions conservatively and explain the relation."""
    relationships: list[dict[str, Any]] = []
    for index, left in enumerate(positions):
        for right in positions[index + 1:]:
            left_text = " ".join(left.get("direct_statements", []))
            right_text = " ".join(right.get("direct_statements", []))
            shared = _tokens(left_text) & _tokens(right_text)
            if _explicit_conflict(left_text, right_text):
                relation = "contradicts"
                explanation = "The passages use overlapping terms while making incompatible or explicitly opposed assertions."
                confidence = 0.72
            elif left.get("qualifications") or right.get("qualifications"):
                relation = "qualifies"
                explanation = "At least one source narrows, conditions, or limits the assertion rather than simply repeating it."
                confidence = 0.62
            elif shared:
                relation = "complements"
                explanation = "The sources address overlapping concepts from different angles; no direct contradiction was established."
                confidence = 0.55
            else:
                relation = "unresolved"
                explanation = "The retrieved passages do not share enough terminology to establish a substantive relationship."
                confidence = 0.35
            relationships.append({
                "source_a": left.get("source_title"),
                "source_b": right.get("source_title"),
                "relation": relation,
                "shared_terms": sorted(shared)[:12],
                "explanation": explanation,
                "confidence": confidence,
                "passage_ids": sorted(set(
                    (left.get("evidence_passage_ids") or [])
                    + (right.get("evidence_passage_ids") or [])
                )),
                "evidence_status": "passage_comparison",
            })
    return relationships


def build_reasoning_chains(
    question: dict[str, Any],
    passages: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    positions: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create claim -> evidence -> analysis -> conclusion records."""
    chains: list[dict[str, Any]] = []
    for claim in claims[:12]:
        chains.append({
            "claim": claim.get("statement", ""),
            "evidence": [claim.get("passage_id")] if claim.get("passage_id") else [],
            "sources": [claim.get("source_title")] if claim.get("source_title") else [],
            "relationship": "direct_source_support",
            "confidence": claim.get("confidence", 0.0),
            "type": claim.get("claim_type", "UNCERTAIN"),
            "analysis": "This is a source-linked statement extracted from a retrieved passage; it is not yet a cross-source conclusion.",
            "conclusion": "The source supports the stated proposition only within the scope of the retrieved passage.",
            "inference_status": "direct_statement",
        })

    if len(positions) >= 2:
        relation_summary = "; ".join(
            f"{item['source_a']} {item['relation']} {item['source_b']}"
            for item in relationships[:4]
        ) or "No source relationship was established."
        chains.append({
            "claim": question.get("underlying_question", question.get("literal_question", "")),
            "evidence": [item.get("passage_id") for item in passages if item.get("passage_id")][:8],
            "sources": [item.get("source_title") for item in positions],
            "relationship": "cross_source_synthesis",
            "confidence": 0.58 if relationships else 0.35,
            "type": "SYNTHESIS",
            "analysis": (
                f"Source comparison yields: {relation_summary}. These relations may reflect different definitions or levels of analysis; "
                "they do not establish that the traditions share one theory."
            ),
            "conclusion": "A qualified synthesis is warranted only where the source relations and retrieved passages support it.",
            "inference_status": "explicit_synthesis",
        })

    gaps = []
    if not passages:
        gaps.append("No verified passage or acquired source was available; the question cannot be answered as an evidence-grounded finding.")
    if not positions:
        gaps.append("No source position could be extracted.")
    if question.get("ambiguities"):
        gaps.append("The retrieved material does not by itself resolve which meaning of the ambiguous concepts the user intends.")
    if len(positions) < 2 and passages:
        gaps.append("Cross-source agreement or disagreement cannot be established from a single represented source.")
    return {
        "chains": chains,
        "gaps": gaps,
        "alternatives": question.get("premise_challenges", []),
        "source_position_count": len(positions),
        "relationship_count": len(relationships),
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
    """Keep the complete machine-inspectable chain without exposing it in prose."""
    return {
        "question": query,
        "question_understanding": question,
        "research_plan": plan,
        "sources": [
            {"source_id": item.get("source_id"), "work_id": item.get("work_id"), "source_title": item.get("source_title"), "author": item.get("author"), "source_type": item.get("source_type")}
            for item in positions
        ],
        "passages": [
            {"passage_id": item.get("passage_id"), "source_id": item.get("source_id"), "source_title": item.get("source_title")}
            for item in passages
        ],
        "claims": [
            {"claim_id": item.get("claim_id"), "passage_id": item.get("passage_id"), "statement": item.get("statement"), "claim_type": item.get("claim_type")}
            for item in claims
        ],
        "source_diversity": source_diversity_metrics(passages),
        "source_positions": positions,
        "relationships": relationships,
        "synthesis": chains,
    }
