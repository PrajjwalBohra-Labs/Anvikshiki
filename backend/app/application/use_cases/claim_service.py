from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.infrastructure.database.models import ClaimModel, EvidenceLinkModel
from backend.app.domain.models.enums import ClaimType, RelationType

class ClaimService:
    """
    Manages the lifecycle, provenance, confidence scoring, and evidence linkages of epistemic claims.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_claim(
        self,
        statement: str,
        claim_type: ClaimType,
        provenance_id: Optional[str] = None,
        confidence: float = 1.0,
        lifecycle_status: str = "ACTIVE"
    ) -> ClaimModel:
        claim = ClaimModel(
            statement=statement,
            claim_type=claim_type,
            provenance_id=provenance_id,
            confidence=confidence,
            lifecycle_status=lifecycle_status
        )
        self.session.add(claim)
        await self.session.commit()
        await self.session.refresh(claim)
        return claim

    async def link_evidence(
        self,
        claim_id: str,
        passage_id: str,
        relation_type: RelationType,
        confidence_weight: float = 1.0
    ) -> EvidenceLinkModel:
        evidence = EvidenceLinkModel(
            claim_id=claim_id,
            passage_id=passage_id,
            relation_type=relation_type,
            confidence_weight=confidence_weight
        )
        self.session.add(evidence)
        await self.session.commit()
        await self.session.refresh(evidence)
        return evidence

    async def get_claim_with_evidence(self, claim_id: str) -> Dict[str, Any]:
        claim = await self.session.get(ClaimModel, claim_id)
        if not claim:
            return {}
        
        result = await self.session.execute(
            select(EvidenceLinkModel).where(EvidenceLinkModel.claim_id == claim_id)
        )
        evidence_links = result.scalars().all()

        return {
            "claim": claim,
            "evidence_links": evidence_links
        }