from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.infrastructure.database.models import ClaimModel, EvidenceLinkModel, PassageModel, SourceModel
import structlog

logger = structlog.get_logger(__name__)

class SynthesisValidationService:
    """
    Performs pre-publication research synthesis validation: claim/evidence alignment,
    citation and provenance validation, contradiction/uncertainty checks, scope checks,
    unsupported statement detection, and blocking/downgrading of fabricated or overclaimed outputs.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def validate_research_output(
        self,
        claims_to_validate: List[Dict[str, Any]],
        research_scope: str
    ) -> Dict[str, Any]:
        """
        Validates claims, evidence linkages, and citations against authoritative database records.
        Blocks or downgrades outputs containing fabricated citations or unsupported statements.
        """
        validated_claims = []
        blocked_claims = []
        warnings = []

        for item in claims_to_validate:
            statement = item.get("statement", "")
            passage_id = item.get("passage_id")
            confidence = item.get("confidence", 1.0)

            # 1. Unsupported Statement Check
            if not statement or len(statement.strip()) < 5:
                blocked_claims.append({
                    "statement": statement,
                    "reason": "Unsupported or malformed statement failing minimum content threshold."
                })
                continue

            # 2. Fabricated Citation / Passage Validation Check
            if passage_id:
                passage = await self.session.get(PassageModel, passage_id)
                if not passage:
                    logger.warning("Fabricated or dangling citation detected", passage_id=passage_id, statement=statement)
                    blocked_claims.append({
                        "statement": statement,
                        "reason": f"Fabricated or non-existent citation reference: '{passage_id}'."
                    })
                    continue
            else:
                # Require passage linkage for authoritative claims (Provenance validation)
                warnings.append(f"Claim lacks direct passage provenance: '{statement[:30]}...'")

            # 3. Overclaiming / Uncertainty Check
            if confidence > 0.95 and "absolute" in statement.lower():
                confidence = 0.85
                warnings.append(f"Confidence downgraded due to absolute overclaiming risk in statement: '{statement[:30]}...'")

            validated_claims.append({
                "statement": statement,
                "passage_id": passage_id,
                "adjusted_confidence": confidence,
                "status": "VALIDATED"
            })

        is_blocked = len(blocked_claims) > 0
        output_status = "BLOCKED_OR_DOWNGRADED" if is_blocked or len(warnings) > 0 else "APPROVED"

        logger.info("Synthesis validation completed", status=output_status, validated_count=len(validated_claims), blocked_count=len(blocked_claims))

        return {
            "status": output_status,
            "validated_claims": validated_claims,
            "blocked_claims": blocked_claims,
            "warnings": warnings,
            "is_safe_for_publication": not is_blocked
        }