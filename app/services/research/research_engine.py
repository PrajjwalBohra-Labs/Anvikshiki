"""
Research Engine (§6; implements the §19 Research Pipeline):

    Question -> Search -> Compare -> Synthesize -> Reference

Persists to Research Memory (§10). Search now optionally includes
Web-Augmented Knowledge (post-Step-16 amendment) alongside the local
knowledge base -- opt-in per call via use_web_search, never silent.

Synthesize legitimately calls LLMAdapter.generate() (unlike the
Reasoning Engine's hard "no generation" rule, §13) -- producing a
synthesized, cited answer across sources is the point of this
pipeline. As of this amendment, Synthesize output is gated through
the same Step 10 validation/reflection engines used by Chat, via a
pseudo-ReasoningObject built from the same evidence -- this closes
the gap where Research could previously fabricate citations that
Chat would have caught.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

from app.config import get_settings
from app.services.knowledge.comparison import compare_chunks, source_key
from app.infrastructure.llm_adapter import LLMAdapter, get_llm_adapter
from app.infrastructure.web_search_adapter import WebSearchAdapter, get_web_search_adapter
from app.services.knowledge.retrieval import RetrievedChunk, retrieve
from app.services.knowledge.web_augmentation import fetch_web_evidence
from app.services.memory.memory_engine import MemoryEngine, get_memory_engine
from app.services.reasoning.reasoning_engine import ConfidenceBreakdown, ReasoningObject
from app.services.validation.reflection_engine import reflect
from app.services.validation.validation_engine import validate

_SPLIT_PATTERN = re.compile(r"\s+(?:and|vs\.?|versus|compared to)\s+", re.IGNORECASE)
_TOKEN_RE = re.compile(r"[a-z0-9]+")
DIVERGENCE_THRESHOLD = 0.3


@dataclass
class ResearchResult:
    question: str
    sub_questions: list[str] = field(default_factory=list)
    chunks: list[RetrievedChunk] = field(default_factory=list)
    comparisons: list[dict] = field(default_factory=list)
    synthesized_answer: str = ""
    references: list[dict] = field(default_factory=list)
    memory_id: str | None = None
    delivered: bool = True
    validation_violations: list[str] = field(default_factory=list)


def _decompose_question(question: str) -> list[str]:
    normalized = question.strip()
    parts = [p.strip() for p in _SPLIT_PATTERN.split(normalized) if p.strip()]
    return parts if len(parts) > 1 else [normalized]


def _search(sub_questions: list[str], top_k: int, llm_adapter: LLMAdapter) -> list[RetrievedChunk]:
    seen: dict[str, RetrievedChunk] = {}
    for sub_question in sub_questions:
        for chunk in retrieve(sub_question, top_k=top_k, llm_adapter=llm_adapter):
            existing = seen.get(chunk.chunk_id)
            if existing is None or chunk.score > existing.score:
                seen[chunk.chunk_id] = chunk
    return list(seen.values())


def _search_web(sub_questions: list[str], adapter: WebSearchAdapter, max_results: int) -> list[RetrievedChunk]:
    results: list[RetrievedChunk] = []
    for sub_question in sub_questions:
        results.extend(fetch_web_evidence(sub_question, adapter, max_results=max_results))
    return results





def _references(chunks: list[RetrievedChunk]) -> list[dict]:
    seen: dict[str, dict] = {}
    for chunk in chunks:
        key = source_key(chunk)
        if key not in seen:
            seen[key] = {
                "document_id": chunk.document_id,
                "title": chunk.document_title,
                "source_type": chunk.source_type,
                "url": chunk.metadata.get("url"),
            }
    return list(seen.values())


def _synthesize(
    question: str, chunks: list[RetrievedChunk], llm_adapter: LLMAdapter,
    confidence: ConfidenceBreakdown | None = None,
) -> str:
    if not chunks:
        return "No evidence was found in the knowledge base to research this question."

    lines = []
    for chunk in chunks:
        source = chunk.document_title or chunk.document_id or "unknown source"
        if chunk.source_type == "web":
            url = chunk.metadata.get("url") or ""
            lines.append(f"WEB (external, unverified) [{source}]: {chunk.chunk_text} (source: {url})")
        else:
            lines.append(f"LOCAL (knowledge base) [{source}]: {chunk.chunk_text}")
    evidence_block = "\n\n".join(lines)

    confidence_instruction = ""
    if confidence is not None:
        score = confidence.overall
        confidence_instruction = (
            f"\n\nYour computed confidence in this evidence is exactly {score:.2f} out of 1.0. "
            f"If you state a confidence number, it must be {score:.2f} -- never invent a "
            "different one. "
        )
        if score < 0.5:
            confidence_instruction += (
                "This confidence is LOW. You must include a hedging phrase somewhere in your "
                "answer -- e.g. \"the evidence is limited\", \"I'm not fully certain\", or "
                "\"this is unclear from the available sources\" -- rather than writing with "
                "unqualified certainty."
            )

    prompt = (
        f'You are researching the question: "{question}"\n\n'
        f"Evidence gathered from the following sources:\n\n{evidence_block}\n\n"
        "Write a synthesized answer using ONLY this evidence, explicitly noting where sources "
        "agree or differ. When citing a source, write ONLY its exact name in square brackets "
        "-- e.g. [Source Name] -- do NOT include the words WEB, LOCAL, external, unverified, or "
        "knowledge base inside the brackets, and never invent numbered references like [1] or "
        "[2]. Treat LOCAL evidence as more authoritative than WEB evidence; when a claim relies "
        "on WEB evidence, say so explicitly. If this evidence does not actually answer the "
        "question, say so plainly and stop -- do not fall back on general knowledge, even to be "
        f"helpful.{confidence_instruction}"
    )
    return llm_adapter.generate(prompt)


def _build_pseudo_reasoning(question: str, chunks: list[RetrievedChunk]) -> ReasoningObject:
    """A minimal ReasoningObject built from research's own chunks, so
    the Step 10 validation/reflection engines can gate this output
    too -- same rules Chat's responses are held to."""
    facts = [{"chunk_id": c.chunk_id, "text": c.chunk_text} for c in chunks]
    evidence = [
        {
            "chunk_id": c.chunk_id,
            "source_document_id": c.document_id,
            "source_document_title": c.document_title,
            "source_type": c.source_type,
            "score": c.score,
        }
        for c in chunks
    ]
    retrieval_quality = statistics.mean([c.score for c in chunks]) if chunks else 0.0
    confidence = ConfidenceBreakdown(
        source_availability=min(1.0, len(chunks) / 3),
        agreement_among_sources=1.0,
        reasoning_completeness=1.0 if chunks else 0.0,
        context_quality=1.0,
        retrieval_quality=retrieval_quality,
        overall=retrieval_quality,
    )
    return ReasoningObject(problem=question, facts=facts, evidence=evidence, confidence=confidence)


def research(
    question: str,
    top_k: int = 5,
    llm_adapter: LLMAdapter | None = None,
    memory_engine: MemoryEngine | None = None,
    use_web_search: bool = False,
    web_search_adapter: WebSearchAdapter | None = None,
) -> ResearchResult:
    """Runs the full §19 Research Pipeline for one (possibly
    multi-part) question. use_web_search is opt-in per call -- with
    it False (the default), behavior is unchanged from before this
    amendment: local knowledge base only."""

    llm_adapter = llm_adapter or get_llm_adapter()
    memory_engine = memory_engine or get_memory_engine()

    sub_questions = _decompose_question(question)
    chunks = _search(sub_questions, top_k, llm_adapter)

    if use_web_search:
        settings = get_settings()
        adapter = web_search_adapter or get_web_search_adapter()
        chunks = chunks + _search_web(sub_questions, adapter, settings.web_search_max_results)

    comparisons = compare_chunks(chunks)
    references = _references(chunks)

    if chunks:
        # Compute confidence BEFORE synthesis so the prompt can tell
        # the model what hedging language it needs to use -- this is
        # what was missing: the gate required hedge words the model
        # was never told to include.
        pseudo_reasoning = _build_pseudo_reasoning(question, chunks)
        synthesized_answer = _synthesize(question, chunks, llm_adapter, pseudo_reasoning.confidence)
        validation_result = validate(synthesized_answer, pseudo_reasoning)
        reflection_result = reflect(synthesized_answer, pseudo_reasoning)
        delivered = validation_result.passed and reflection_result.passed
        violations = validation_result.all_violations + reflection_result.failure_flags
    else:
        synthesized_answer = _synthesize(question, chunks, llm_adapter)
        delivered = True
        violations = []

    if not delivered:
        synthesized_answer = (
            "I don't have enough verified evidence to answer this reliably, "
            "and I'd rather say that than guess."
        )

    memory_record = memory_engine.remember(
        {
            "content": synthesized_answer,
            "tier": "research",
            "metadata": {"question": question, "sub_questions": sub_questions, "references": references},
        }
    )

    return ResearchResult(
        question=question,
        sub_questions=sub_questions,
        chunks=chunks,
        comparisons=comparisons,
        synthesized_answer=synthesized_answer,
        references=references,
        memory_id=memory_record.id,
        delivered=delivered,
        validation_violations=violations,
    )



