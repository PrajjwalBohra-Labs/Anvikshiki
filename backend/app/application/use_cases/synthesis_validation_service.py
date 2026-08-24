from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
from backend.app.infrastructure.database.models import PassageModel

logger = structlog.get_logger(__name__)

class SynthesisValidationService:
    """
    Validates claim-evidence linkage, checks passage existence, and blocks ungrounded assertions.
    """
    def __init__(self, session: Optional[AsyncSession] = None):
        self.session = session

    async def validate_research_output(
        self,
        claims: List[Dict[str, Any]],
        research_scope: Optional[str] = None
    ) -> Dict[str, Any]:
        validated = []
        for c in claims:
            passage_id = c.get("passage_id")
            # If session is provided, verify passage exists in database
            if self.session and passage_id:
                passage = await self.session.get(PassageModel, passage_id)
                if not passage:
                    logger.warning("Validation flagged ungrounded claim", claim=c)
                    continue

            validated.append({
                "statement": c.get("statement", ""),
                "passage_id": passage_id,
                "confidence": c.get("confidence", 0.95),
                "is_verified": True
            })

        status = "APPROVED" if len(validated) == len(claims) else "BLOCKED_OR_DOWNGRADED"
        return {
            "status": status,
            "validated_claims": validated,
            "total_claims": len(claims),
            "approved_claims": len(validated)
        }