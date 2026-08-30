"""MCP adapters for the repository's existing research capabilities.

This module deliberately exposes only the two research tools that already
exist in the repository's Step 40 history. Retrieval, citation formatting,
and provenance traversal remain application services; MCP only translates
their results into a stable public shape.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from datetime import datetime
from enum import Enum
from typing import Any, TypeVar

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.application.use_cases.citation_service import CitationService
from backend.app.application.use_cases.provenance import ProvenanceService
from backend.app.core.config import settings
from backend.app.infrastructure.database.models import (
    DocumentModel,
    DocumentVersionModel,
    PassageModel,
)
from backend.app.infrastructure.database.session import AsyncSessionLocal
from backend.app.infrastructure.mcp.server import AnvikshikiMCPServer
from backend.app.infrastructure.rag.lexical_retriever import LexicalRetriever
from backend.app.infrastructure.rag.reranker import AdvancedRetriever

logger = structlog.get_logger(__name__)

_T = TypeVar("_T")
SessionFactory = Callable[[], AsyncSession]


class PromptInjectionError(ValueError):
    """Raised when a research input attempts to address the tool boundary."""


def sanitize_and_check_injection(text: str) -> str:
    """Reject common instruction-override strings without logging the input."""

    injection_patterns = (
        r"ignore previous instructions",
        r"system prompt",
        r"reveal configuration",
        r"bypass security",
    )
    for pattern in injection_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            logger.warning("mcp_prompt_injection_blocked", pattern=pattern)
            raise PromptInjectionError("Research input was rejected by the security policy.")
    return text


def _public_value(value: Any) -> Any:
    """Convert service values into JSON-safe, deterministic public values."""

    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _public_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_public_value(item) for item in value]
    return value


async def _using_session(
    session: AsyncSession | None,
    session_factory: SessionFactory | None,
    operation: Callable[[AsyncSession], Awaitable[_T]],
) -> _T:
    if session is not None:
        return await operation(session)
    if session_factory is None:
        raise RuntimeError("MCP research tools require a database session.")
    async with session_factory() as request_session:
        return await operation(request_session)


def _retrieval_payload(item: Any, mode: str, citation: Any) -> dict[str, Any]:
    passage = item.passage
    source = passage.document.source
    return {
        "passage_id": passage.id,
        "document_id": passage.document_id,
        "document_version_id": passage.document_version_id,
        "page_id": passage.page_id,
        "source_id": source.id,
        "source_title": source.title,
        "author": source.author,
        "source_type": _public_value(source.source_type),
        "reference_url": source.reference_url,
        "content": passage.content,
        # Compatibility with the original Step 40 draft contract.
        "passage_sample": passage.content,
        "page_number": passage.page_number,
        "passage_order": passage.passage_order,
        "extraction_method": passage.extraction_method,
        "section_heading": passage.section_heading,
        "ocr_confidence": passage.ocr_confidence,
        "extraction_uncertainty": passage.extraction_uncertainty,
        "language": passage.language,
        "retrieval_method": mode,
        "relevance_score": item.score,
        "lexical_score": item.lexical_score,
        "semantic_score": item.semantic_score,
        "hybrid_score": item.hybrid_score,
        "rerank_score": item.rerank_score,
        "citation_string": citation.citation_string,
        "fabricated": False,
    }


def register_mcp_research_tools(
    server: AnvikshikiMCPServer,
    session: AsyncSession | None = None,
    *,
    session_factory: SessionFactory | None = AsyncSessionLocal,
) -> None:
    """Register the existing local retrieval and citation capabilities.

    Tests and embedded callers may provide an existing session. The stdio
    entrypoint uses the factory so each invocation receives a fresh session
    and no database connection is held by the registration layer.
    """

    async def search_local_sources(
        query: str,
        domain: str | None = None,
        top_k: int = 10,
        retrieval: str = "hybrid",
    ) -> dict[str, Any]:
        normalized_query = sanitize_and_check_injection(query).strip()
        if not normalized_query:
            raise ValueError("Research query cannot be empty.")

        async def execute(db: AsyncSession) -> dict[str, Any]:
            if retrieval == "lexical":
                scored_passages = await LexicalRetriever(db).search(
                    query=normalized_query,
                    limit=top_k,
                )
                retrieval_status = "complete"
                retrieval_warnings: list[str] = []
            elif retrieval == "semantic":
                outcome = await AdvancedRetriever(db).semantic_retrieve(
                    query=normalized_query,
                    top_k=top_k,
                )
                scored_passages = outcome.results
                retrieval_status = outcome.status
                retrieval_warnings = outcome.warnings
            else:
                outcome = await AdvancedRetriever(db).retrieve_and_rerank_with_metadata(
                    query=normalized_query,
                    top_k=top_k,
                )
                scored_passages = outcome.results
                retrieval_status = outcome.status
                retrieval_warnings = outcome.warnings

            citation_service = CitationService(db)
            sources_found = []
            for item in scored_passages:
                citation = await citation_service.generate_citation(item.passage.id)
                sources_found.append(_retrieval_payload(item, retrieval, citation))

            return {
                "query": normalized_query,
                "domain": domain or "general",
                "retrieval": retrieval,
                "retrieval_status": retrieval_status,
                "retrieval_warnings": retrieval_warnings,
                "total_results": len(sources_found),
                "sources_found": sources_found,
                "fabricated": False,
            }

        return await _using_session(session, session_factory, execute)

    async def trace_citation(citation_id: str) -> dict[str, Any]:
        normalized_id = sanitize_and_check_injection(citation_id).strip()

        async def execute(db: AsyncSession) -> dict[str, Any]:
            stmt = (
                select(PassageModel)
                .where(PassageModel.id == normalized_id)
                .options(
                    selectinload(PassageModel.document).selectinload(DocumentModel.source),
                    selectinload(PassageModel.document_version).selectinload(
                        DocumentVersionModel.pages
                    ),
                    selectinload(PassageModel.page),
                )
            )
            result = await db.execute(stmt)
            passage = result.scalar_one_or_none()
            if passage is None:
                return {
                    "citation_id": normalized_id,
                    "traceable": False,
                    "fabricated": False,
                    "provenance_graph": {"nodes": [], "edges": []},
                }

            citation = await CitationService(db).generate_citation(normalized_id)
            provenance = ProvenanceService(db)
            graph = await provenance.trace_passage(normalized_id)
            lineage = await provenance.trace_lineage(passage.document.source.id)
            source = passage.document.source
            document = passage.document
            return _public_value(
                {
                    "citation_id": normalized_id,
                    "citation_string": citation.citation_string,
                    "passage_content": passage.content,
                    # Additive compatibility fields from the original Step
                    # 40 draft contract.
                    "source_id": source.id,
                    "source_title": source.title,
                    "page_number": passage.page_number,
                    "passage": {
                        "passage_id": passage.id,
                        "document_id": passage.document_id,
                        "document_version_id": passage.document_version_id,
                        "page_id": passage.page_id,
                        "page_number": passage.page_number,
                        "passage_order": passage.passage_order,
                        "content": passage.content,
                        "extraction_method": passage.extraction_method,
                        "section_heading": passage.section_heading,
                        "ocr_confidence": passage.ocr_confidence,
                        "extraction_uncertainty": passage.extraction_uncertainty,
                        "language": passage.language,
                    },
                    "document": {
                        "document_id": document.id,
                        "source_id": document.source_id,
                        "checksum_sha256": document.checksum_sha256,
                        "mime_type": document.mime_type,
                        "original_filename": document.original_filename,
                        "total_pages": document.total_pages,
                    },
                    "source": {
                        "source_id": source.id,
                        "title": source.title,
                        "author": source.author,
                        "historical_era": source.historical_era,
                        "original_language": source.original_language,
                        "source_type": source.source_type,
                        "reference_url": source.reference_url,
                    },
                    "source_lineage": lineage,
                    "provenance_graph": graph or {"nodes": [], "edges": []},
                    "traceable": True,
                    "fabricated": False,
                }
            )

        return await _using_session(session, session_factory, execute)

    server.register_tool(
        name="search_local_sources",
        description="Searches indexed local sources and returns retrieval and passage provenance.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": settings.LEXICAL_MAX_QUERY_LENGTH,
                },
                "domain": {"type": "string", "minLength": 1, "maxLength": 128},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 20},
                "retrieval": {
                    "type": "string",
                    "enum": ["hybrid", "lexical", "semantic"],
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=search_local_sources,
    )
    server.register_tool(
        name="trace_citation",
        description="Traces a passage citation through its source and existing provenance graph.",
        input_schema={
            "type": "object",
            "properties": {
                "citation_id": {"type": "string", "minLength": 1, "maxLength": 128}
            },
            "required": ["citation_id"],
            "additionalProperties": False,
        },
        handler=trace_citation,
    )


def create_mcp_research_server(
    *,
    session_factory: SessionFactory | None = AsyncSessionLocal,
    permission_policy: Callable[[str, dict[str, Any]], bool] | None = None,
) -> AnvikshikiMCPServer:
    """Build the MCP server with the Step 40 tools registered."""

    server = AnvikshikiMCPServer(permission_policy=permission_policy)
    register_mcp_research_tools(server, session_factory=session_factory)
    return server
