"""Orchestrate web discovery and acquisition for a research run.

Discovery metadata is retained separately from acquired evidence.  A search
result is never presented as evidence until the URL has passed acquisition,
ingestion, and indexing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.application.use_cases.web_acquisition import WebAcquisitionService
from backend.app.application.use_cases.web_search import WebSearchService
from backend.app.core.config import settings
from backend.app.core.errors import AnvikshikiDomainError
from backend.app.infrastructure.storage.local_storage import LocalStorageService

logger = structlog.get_logger(__name__)


class WebResearchService:
    """Discover candidate URLs, acquire safe sources, and expose provenance."""

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        storage_factory: Callable[[], LocalStorageService] = LocalStorageService,
    ):
        self.session_factory = session_factory
        self.storage_factory = storage_factory

    async def discover_and_acquire(
        self,
        query: str,
        owner_id: str,
        max_results: int | None = None,
    ) -> dict[str, Any]:
        limit = min(max_results or settings.WEB_RETRIEVAL_MAX_RESULTS, 3)
        try:
            discovered = await WebSearchService().search(query, limit)
        except AnvikshikiDomainError as exc:
            return {
                "requested": True,
                "status": "unavailable",
                "error": str(exc),
                "discoveries": [],
                "acquisitions": [],
            }

        discoveries = [
            {
                "title": item.title,
                "url": item.url,
                "canonical_url": item.canonical_url,
                "snippet": item.snippet,
                "rank": item.rank,
                "domain": item.domain,
            }
            for item in discovered
        ]
        acquisitions: list[dict[str, Any]] = []
        for item in discovered:
            try:
                async with self.session_factory() as session:
                    source, document, passages = await WebAcquisitionService(
                        session, self.storage_factory()
                    ).acquire_url(
                        url=item.canonical_url,
                        source_title=item.title,
                        owner_id=owner_id,
                    )
                acquisitions.append(
                    {
                        "status": "acquired",
                        "url": item.canonical_url,
                        "source_id": source.id,
                        "document_id": document.id,
                        "passages_count": len(passages),
                    }
                )
            except AnvikshikiDomainError as exc:
                acquisitions.append(
                    {
                        "status": "failed",
                        "url": item.canonical_url,
                        "error": str(exc),
                    }
                )
            except Exception as exc:  # noqa: BLE001 - isolate one web source.
                logger.warning(
                    "web_source_acquisition_failed",
                    error_type=type(exc).__name__,
                )
                acquisitions.append(
                    {
                        "status": "failed",
                        "url": item.canonical_url,
                        "error": "The web source could not be acquired.",
                    }
                )

        acquired_count = sum(item["status"] == "acquired" for item in acquisitions)
        status = "acquired" if acquired_count == len(acquisitions) and acquisitions else "partial"
        if not acquisitions:
            status = "unavailable"
        return {
            "requested": True,
            "status": status,
            "error": None if acquired_count else "No discovered web source was acquired.",
            "discoveries": discoveries,
            "acquisitions": acquisitions,
        }
