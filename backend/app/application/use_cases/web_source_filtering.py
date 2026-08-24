from typing import Optional, Dict, Any
from urllib.parse import urlparse
from backend.app.domain.models.enums import SourceType
import structlog

logger = structlog.get_logger(__name__)

class WebSourceFilteringService:
    """
    Classifies web sources into authoritative evidence tiers based on institutional
    relevance, provenance, and platform verifiability, free of ideological or national bias.
    """
    
    PREFERRED_DOMAINS = [
        "jstor.org", "archive.org", "plato.stanford.edu", 
        "suttacentral.net", "sacred-texts.com", "ncbi.nlm.nih.gov"
    ]
    
    PREFERRED_TLDS = [".edu", ".gov", ".ac.uk"]
    
    DISCOVERY_DOMAINS = [
        "wikipedia.org", "britannica.com", "medium.com", "substack.com", "blog"
    ]
    
    REJECTED_DOMAINS = [
        "twitter.com", "x.com", "facebook.com", "instagram.com", "reddit.com", "tiktok.com"
    ]

    def evaluate_source(self, url: str, content_snippet: Optional[str] = None) -> Dict[str, Any]:
        """
        Evaluates a web URL against scholarly classification rules with precise domain matching.
        """
        parsed = urlparse(url.lower())
        domain = parsed.netloc

        # 1. Reject unverified social media and user-generated social platforms
        for rej in self.REJECTED_DOMAINS:
            if rej in domain:
                logger.warning("Web source rejected from authoritative evidence", url=url, domain=domain)
                return {
                    "classification": "REJECTED",
                    "source_type": SourceType.UNVERIFIED,
                    "reason": f"Domain '{domain}' is classified as social media or unverified user-generated content."
                }

        # 2. Check discovery-only general references first (ensures wikipedia.org is caught before generic TLD rules)
        for disc in self.DISCOVERY_DOMAINS:
            if disc in domain:
                return {
                    "classification": "DISCOVERY_ONLY",
                    "source_type": SourceType.DISCOVERY_ONLY,
                    "reason": f"Domain '{domain}' is a general reference or explainer portal (Discovery Only)."
                }

        # 3. Check preferred specific scholarly and institutional archives
        for pref in self.PREFERRED_DOMAINS:
            if domain == pref or domain.endswith("." + pref):
                return {
                    "classification": "PREFERRED",
                    "source_type": SourceType.PRIMARY,
                    "reason": f"Domain '{domain}' belongs to a recognized academic, institutional, or scholarly repository."
                }

        # 4. Check preferred academic/governmental TLDs
        for tld in self.PREFERRED_TLDS:
            if domain.endswith(tld):
                return {
                    "classification": "PREFERRED",
                    "source_type": SourceType.PRIMARY,
                    "reason": f"Domain '{domain}' belongs to a recognized academic or governmental TLD."
                }

        # Default fallback for unclassified domains
        return {
            "classification": "DISCOVERY_ONLY",
            "source_type": SourceType.DISCOVERY_ONLY,
            "reason": f"Domain '{domain}' default classified as discovery-only pending manual verification."
        }