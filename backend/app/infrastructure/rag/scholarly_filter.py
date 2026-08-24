import re
from typing import List, Optional
from pydantic import BaseModel
from backend.app.domain.models.enums import SourceType

class WebCandidate(BaseModel):
    url: str
    title: str
    snippet: str
    source_type: SourceType
    authority_score: float

class ScholarlySourceFilter:
    # High-value academic and scholarly repository patterns
    SCHOLARLY_PATTERNS = [
        r"\.edu",
        r"\.ac\.",
        r"plato\.stanford\.edu",
        r"iep\.utm\.edu",
        r"jstor\.org",
        r"ncbi\.nlm\.nih\.gov",
        r"frontiersin\.org",
        r"nature\.com",
        r"sciencedirect\.com",
        r"archive\.org",
        r"sacred-texts\.com",
        r"sanskritdocuments\.org"
    ]

    DISALLOWED_PATTERNS = [
        r"twitter\.com",
        r"x\.com",
        r"facebook\.com",
        r"reddit\.com",
        r"instagram\.com",
        r"medium\.com"
    ]

    @classmethod
    def evaluate_url(cls, url: str) -> Optional[SourceType]:
        for dis in cls.DISALLOWED_PATTERNS:
            if re.search(dis, url, re.IGNORECASE):
                return None  # Disallowed from authoritative evidence layer

        for sch in cls.SCHOLARLY_PATTERNS:
            if re.search(sch, url, re.IGNORECASE):
                if any(k in url for k in ["ncbi", "nature", "frontiersin", "sciencedirect"]):
                    return SourceType.SCIENTIFIC_STUDY
                if any(k in url for k in ["sanskritdocuments", "sacred-texts"]):
                    return SourceType.PRIMARY
                return SourceType.SCHOLARLY_SECONDARY

        return SourceType.DISCOVERY_ONLY