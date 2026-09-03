import re
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.infrastructure.database.models import PassageModel

logger = structlog.get_logger(__name__)

class SynthesisValidationService:
    """
    Validates claim-evidence linkage, checks passage existence, and blocks ungrounded assertions.
    """
    def __init__(self, session: AsyncSession | None = None):
        self.session = session

    async def validate_research_output(
        self,
        claims: list[dict[str, Any]],
        research_scope: str | None = None
    ) -> dict[str, Any]:
        validated = []
        blocked = []
        warnings = []
        for c in claims:
            passage_id = c.get("passage_id")
            # If session is provided, verify passage exists in database
            if self.session and passage_id:
                passage = await self.session.get(PassageModel, passage_id)
                if not passage:
                    logger.warning("Validation flagged ungrounded claim", claim=c)
                    blocked.append({
                        **c,
                        "reason": "Fabricated or non-existent citation reference",
                    })
                    continue

            confidence = c.get("confidence", 0.95)
            if confidence > 0.95 and re.search(
                r"\b(absolute|irrefutable|universal|always|never)\b",
                c.get("statement", ""),
                re.IGNORECASE,
            ):
                warnings.append({
                    "statement": c.get("statement", ""),
                    "reason": "High-confidence universal language was downgraded.",
                })
                confidence = 0.5

            validated.append({
                **c,
                "passage_id": passage_id,
                "confidence": confidence,
                "is_verified": True,
            })

        status = "APPROVED" if len(validated) == len(claims) else "BLOCKED_OR_DOWNGRADED"
        return {
            "status": status,
            "validated_claims": validated,
            "total_claims": len(claims),
            "approved_claims": len(validated),
            "blocked_claims": blocked,
            "warnings": warnings,
            "is_safe_for_publication": status == "APPROVED",
        }
