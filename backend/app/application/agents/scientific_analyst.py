from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

logger = structlog.get_logger(__name__)

class ScientificAnalyst:
    """
    Evaluates empirical studies, methodology, and replication metrics.
    """
    def __init__(self, session: Optional[AsyncSession] = None):
        self.session = session

    async def analyze_study(
        self, study_data: Optional[Dict[str, Any]] = None, **study_fields: Any
    ) -> Dict[str, Any]:
        """Return a structured empirical assessment without inventing study facts."""
        data = {**(study_data or {}), **study_fields}
        study_type = data.get("study_type", "EMPIRICAL")
        methodology = data.get("methodology", "NOT_REPORTED")
        observational = bool(data.get("is_observational")) or "observ" in str(study_type).lower()
        interpretation = str(data.get("author_interpretation", ""))
        causal_language = any(
            token in interpretation.lower() for token in ("causes", "causal", "proves")
        )

        result = dict(data)
        result.update(
            {
                "study_type": study_type,
                "methodology": methodology,
                "evidence_strength": 0.9 if data.get("results") else 0.5,
                "replication_status": data.get("replication_status", "NOT_REPORTED"),
                "distinguishes_correlation_from_causation": observational
                or "correlation" in str(data.get("results", "")).lower(),
                "distinguishes_observation_from_interpretation": observational
                or bool(interpretation),
                "claims_overstated": observational and causal_language,
                "independent_assessment": (
                    "Caution: Observational study design does not establish causation."
                    if observational
                    else "Assessment limited to the supplied study description."
                ),
            }
        )
        return result
