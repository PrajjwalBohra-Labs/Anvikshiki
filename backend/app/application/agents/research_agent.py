from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.application.use_cases.web_source_filtering import WebSourceFilteringService
import structlog

logger = structlog.get_logger(__name__)

class ResearchAgent:
    """
    Responsible for source discovery, query expansion, retrieval execution,
    source deduplication, provenance capture, and strict output validation.
    """
    def __init__(self, session: AsyncSession, max_results: int = 5):
        self.session = session
        self.max_results = max_results
        self.filter_service = WebSourceFilteringService()

    def expand_query(self, query: str) -> List[str]:
        """Expands a search query with semantic synonyms or traditional terminology variants."""
        cleaned = query.strip()
        expansions = [cleaned]
        if "perception" in cleaned.lower():
            expansions.append("Pratyaksha sense-object contact")
        if "inference" in cleaned.lower():
            expansions.append("Anumana logical deduction")
        return expansions

    def deduplicate_sources(self, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicates retrieved sources based on unique URL or title fingerprints."""
        seen = set()
        unique_sources = []
        for src in sources:
            fingerprint = src.get("reference_url") or src.get("title")
            if fingerprint and fingerprint not in seen:
                seen.add(fingerprint)
                unique_sources.append(src)
        return unique_sources[:self.max_results]

    async def execute_discovery(self, query: str, candidate_urls: List[str]) -> List[Dict[str, Any]]:
        """
        Discovers and filters sources, enforcing provenance and rejecting unverified material.
        """
        expanded_queries = self.expand_query(query)
        logger.info("Executing research agent discovery", original_query=query, expansions=expanded_queries)

        raw_sources = []
        for url in candidate_urls:
            evaluation = self.filter_service.evaluate_source(url)
            # Guardrail: Never admit rejected sources (e.g., social media / unverified)
            if evaluation["classification"] != "REJECTED":
                raw_sources.append({
                    "title": f"Source from {url}",
                    "reference_url": url,
                    "source_type": evaluation["source_type"],
                    "classification": evaluation["classification"],
                    "provenance_reason": evaluation["reason"]
                })
            else:
                logger.warning("Agent rejected unverified source", url=url, reason=evaluation["reason"])

        deduplicated = self.deduplicate_sources(raw_sources)

        # Output Validation: Ensure every source possesses strict provenance
        for src in deduplicated:
            if not src.get("reference_url") or not src.get("provenance_reason"):
                raise ValueError("Output validation failed: Source lacks required provenance metadata.")

        return deduplicated