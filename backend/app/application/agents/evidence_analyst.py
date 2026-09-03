from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domain.models.enums import ClaimType, RelationType
from backend.app.infrastructure.database.models import (
    ClaimModel,
    EvidenceLinkModel,
    PassageModel,
)

logger = structlog.get_logger(__name__)

class EvidenceAnalyst:
    """
    Responsible for extracting claims, supporting/counter evidence, identifying evidence types,
    assigning uncertainty, linking evidence to canonical passages, and validating references.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def analyze_passage_evidence(
        self,
        passage_id: str,
        claim_statement: str,
        claim_type: ClaimType = ClaimType.DIRECT_SOURCE_CLAIM,
        relation_type: RelationType = RelationType.SUPPORTS,
        confidence_weight: float = 1.0
    ) -> dict[str, Any]:
        """
        Extracts claims and links them securely to passages with confidence/uncertainty tracking.
        """
        # 1. Validate passage existence reference (prevent unsupported/dangling evidence)
        passage = await self.session.get(PassageModel, passage_id)
        if not passage:
            raise ValueError(f"Evidence validation failed: Passage with ID '{passage_id}' does not exist.")

        # 2. Create authoritative Claim record
        claim = ClaimModel(
            statement=claim_statement,
            claim_type=claim_type,
            confidence=confidence_weight,
            lifecycle_status="ACTIVE"
        )
        self.session.add(claim)
        await self.session.flush()

        # 3. Create Evidence Link binding claim to passage with relation type (supports/contradicts)
        evidence_link = EvidenceLinkModel(
            claim_id=claim.id,
            passage_id=passage.id,
            relation_type=relation_type,
            confidence_weight=confidence_weight
        )
        self.session.add(evidence_link)
        await self.session.commit()

        logger.info("Evidence analyzed and linked successfully", claim_id=claim.id, passage_id=passage_id)

        return {
            "claim_id": claim.id,
            "statement": claim.statement,
            "relation_type": relation_type,
            "confidence": confidence_weight,
            "passage_id": passage.id,
            "traceable": True
        }