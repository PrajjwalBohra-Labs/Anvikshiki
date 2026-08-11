"""
Context Service (§12 Context Model): "Context is assembled, never
assumed." Given a query, this pulls the sources §12 names that
actually exist -- current message, retrieved knowledge (Step 5),
concept graph (relationships table), project state -- and packages
them into one bounded, token-budgeted object.

Two §12 sources are deliberately not wired in yet:
  - dialogue history: accepted as a plain optional parameter rather
    than fetched, since the Conversation Service that will own real
    session state doesn't exist until a later step (§17
    replaceability -- this stays a clean injection point).
  - working memory / session state: belongs to the Memory Service.

Token counts are estimated with a simple len(text) // 4 heuristic,
not a real tokenizer -- accurate counts are model-specific and Ollama
models vary.

Web-Augmented Knowledge (post-Step-16 amendment): opt-in per call via
use_web_search. Default False -- with it off, behavior is unchanged
from before this amendment, 100% local.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.config import get_settings
from app.infrastructure.llm_adapter import LLMAdapter, get_llm_adapter
from app.infrastructure.web_search_adapter import WebSearchAdapter, get_web_search_adapter
from app.persistence import relational_db
from app.services.knowledge.retrieval import RetrievedChunk, retrieve
from app.services.knowledge.web_augmentation import fetch_web_evidence

DEFAULT_MAX_TOKENS = 4000
DEFAULT_TOP_K = 5

SYSTEM_POLICIES = [
    "If evidence is insufficient, acknowledge the limitation and avoid fabrication (§16).",
    "If sources conflict, preserve the disagreement rather than forcing synthesis (§16).",
    "Confidence is never equivalent to truth (§15).",
]


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


@dataclass
class ContextSection:
    name: str
    content: str
    priority: int
    estimated_tokens: int = 0


@dataclass
class ContextObject:
    query: str
    sections: list[ContextSection] = field(default_factory=list)
    retrieved_chunks: list[RetrievedChunk] = field(default_factory=list)
    total_estimated_tokens: int = 0
    max_tokens: int = DEFAULT_MAX_TOKENS

    @property
    def rendered_text(self) -> str:
        return "\n\n".join(f"### {s.name}\n{s.content}" for s in self.sections if s.content)


def _format_history(history: list[dict] | None) -> str:
    if not history:
        return ""
    return "\n".join(f"{turn.get('role', 'user')}: {turn.get('content', '')}" for turn in history)


def _format_retrieved_chunks(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return ""
    return "\n\n".join(
        f"[{chunk.document_title or chunk.document_id or 'unknown source'}] {chunk.chunk_text}"
        for chunk in chunks
    )


def _format_concept_graph(relationships: list[dict]) -> str:
    if not relationships:
        return ""
    return "\n".join(
        f"{r['source_type']}:{r['source_id']} --{r['relationship_type']}--> "
        f"{r['target_type']}:{r['target_id']}"
        for r in relationships
    )


def _format_project_state(project: dict | None) -> str:
    if not project:
        return ""
    return f"Project: {project['name']}\n{project.get('description', '')}"


def build_context(
    query: str,
    conversation_history: list[dict] | None = None,
    project_id: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    top_k: int = DEFAULT_TOP_K,
    llm_adapter: LLMAdapter | None = None,
    use_web_search: bool = False,
    web_search_adapter: WebSearchAdapter | None = None,
) -> ContextObject:
    llm_adapter = llm_adapter or get_llm_adapter()
    normalized_query = query.strip()

    retrieved_chunks = (
        retrieve(normalized_query, top_k=top_k, llm_adapter=llm_adapter) if normalized_query else []
    )

    # Web-Augmented Knowledge (post-Step-16 amendment): opt-in per request.
    if use_web_search and normalized_query:
        settings = get_settings()
        adapter = web_search_adapter or get_web_search_adapter()
        retrieved_chunks = retrieved_chunks + fetch_web_evidence(
            normalized_query, adapter, max_results=settings.web_search_max_results
        )

    concept_ids = {
        chunk.metadata.get("concept_id")
        for chunk in retrieved_chunks
        if chunk.metadata.get("concept_id")
    }
    relationships: list[dict] = []
    for concept_id in concept_ids:
        relationships.extend(relational_db.get_relationships_for("concept", concept_id))

    project = relational_db.get_project(project_id) if project_id else None

    candidate_sections = [
        ContextSection("system_policies", "\n".join(SYSTEM_POLICIES), priority=0),
        ContextSection("current_message", normalized_query, priority=0),
        ContextSection("retrieved_knowledge", _format_retrieved_chunks(retrieved_chunks), priority=1),
        ContextSection("dialogue_history", _format_history(conversation_history), priority=2),
        ContextSection("concept_graph", _format_concept_graph(relationships), priority=3),
        ContextSection("project_state", _format_project_state(project), priority=4),
    ]

    sections = [s for s in candidate_sections if s.content]
    for section in sections:
        section.estimated_tokens = _estimate_tokens(section.content)
    sections.sort(key=lambda s: s.priority)

    mandatory = [s for s in sections if s.priority == 0]
    optional = [s for s in sections if s.priority > 0]

    kept: list[ContextSection] = list(mandatory)
    total_tokens = sum(s.estimated_tokens for s in mandatory)

    for section in optional:
        if total_tokens + section.estimated_tokens <= max_tokens:
            kept.append(section)
            total_tokens += section.estimated_tokens
            continue

        remaining_budget = max_tokens - total_tokens
        if remaining_budget > 20:
            truncated = section.content[: remaining_budget * 4]
            section.content = truncated
            section.estimated_tokens = _estimate_tokens(truncated)
            kept.append(section)
            total_tokens += section.estimated_tokens
        break

    return ContextObject(
        query=normalized_query,
        sections=kept,
        retrieved_chunks=retrieved_chunks,
        total_estimated_tokens=total_tokens,
        max_tokens=max_tokens,
    )
