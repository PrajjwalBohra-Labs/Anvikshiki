import re
from typing import Any, Dict, Optional

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.infrastructure.database.models import DocumentModel, PassageModel, SourceModel
from backend.app.infrastructure.mcp.server import AnvikshikiMCPServer

logger = structlog.get_logger(__name__)


class PromptInjectionError(ValueError):
    """Raised when prompt injection patterns are detected in tool inputs."""


def sanitize_and_check_injection(text: str) -> str:
    injection_patterns = [
        r"ignore previous instructions",
        r"system prompt",
        r"reveal configuration",
        r"bypass security",
    ]
    for pattern in injection_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            logger.warning("Prompt injection detected and blocked", pattern=pattern)
            raise PromptInjectionError(
                f"Security violation: Input triggers prompt injection defense ({pattern})."
            )
    return text


def register_mcp_research_tools(server: AnvikshikiMCPServer, session: AsyncSession) -> None:
    """Register database-backed research tools at the MCP boundary."""

    async def search_local_sources(
        query: str, domain: Optional[str] = None, top_k: int = 10
    ) -> Dict[str, Any]:
        sanitize_and_check_injection(query)
        if session is None:
            raise RuntimeError("MCP research tools require a database session.")

        keywords = [word for word in query.split() if len(word) > 2]
        conditions = [PassageModel.content.ilike(f"%{word}%") for word in keywords]
        stmt = (
            select(PassageModel, DocumentModel, SourceModel)
            .join(DocumentModel, PassageModel.document_id == DocumentModel.id)
            .join(SourceModel, DocumentModel.source_id == SourceModel.id)
            .options(selectinload(PassageModel.document).selectinload(DocumentModel.source))
            .limit(max(1, min(top_k, 20)))
        )
        if conditions:
            stmt = stmt.where(or_(*conditions))
        rows = (await session.execute(stmt)).all()
        return {
            "query": query,
            "domain": domain or "general",
            "sources_found": [
                {
                    "source_id": source.id,
                    "passage_id": passage.id,
                    "title": source.title,
                    "passage_sample": passage.content,
                    "fabricated": False,
                }
                for passage, _document, source in rows
            ],
            "fabricated": False,
        }

    async def trace_citation(citation_id: str) -> Dict[str, Any]:
        sanitize_and_check_injection(citation_id)
        if session is None:
            raise RuntimeError("MCP research tools require a database session.")
        stmt = (
            select(PassageModel, DocumentModel, SourceModel)
            .join(DocumentModel, PassageModel.document_id == DocumentModel.id)
            .join(SourceModel, DocumentModel.source_id == SourceModel.id)
            .where(PassageModel.id == citation_id)
        )
        row = (await session.execute(stmt)).first()
        if row is None:
            return {"citation_id": citation_id, "traceable": False, "fabricated": False}
        passage, _document, source = row
        return {
            "citation_id": citation_id,
            "passage_content": passage.content,
            "source_id": source.id,
            "source_title": source.title,
            "page_number": passage.page_number,
            "traceable": True,
            "fabricated": False,
        }

    server.register_tool(
        name="search_local_sources",
        description="Searches indexed local sources and returns passage provenance.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "domain": {"type": "string"},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "required": ["query"],
        },
        handler=search_local_sources,
    )
    server.register_tool(
        name="trace_citation",
        description="Traces a passage citation to its indexed source.",
        input_schema={
            "type": "object",
            "properties": {"citation_id": {"type": "string"}},
            "required": ["citation_id"],
        },
        handler=trace_citation,
    )
