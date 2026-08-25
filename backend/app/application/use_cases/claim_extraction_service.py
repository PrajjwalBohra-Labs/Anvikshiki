import re
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.app.infrastructure.database.models import ClaimModel, EvidenceLinkModel
from backend.app.domain.models.enums import ClaimType, RelationType

logger = structlog.get_logger(__name__)

class ClaimExtractionService:
    """
    Extracts structured, evidence-linked claims distinguishing:
    DIRECT_SOURCE_CLAIM, TRANSLATION, SCHOLARLY_INTERPRETATION, SCIENTIFIC_FINDING, INFERENCE, HYPOTHESIS, MODEL_SYNTHESIS.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def extract_claims_from_passage(
        self,
        passage_id: str,
        passage_content: str,
        source_title: str,
        source_type: str = "PRIMARY"
    ) -> List[ClaimModel]:
        # Determine explicit claim type based on source taxonomy.
        if source_type == "PRIMARY":
            claim_type = ClaimType.DIRECT_SOURCE_CLAIM
        elif source_type == "TRANSLATION":
            claim_type = ClaimType.TRANSLATION
        elif source_type == "SCIENTIFIC":
            claim_type = ClaimType.SCIENTIFIC_FINDING
        else:
            claim_type = ClaimType.SCHOLARLY_INTERPRETATION

        statements = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", passage_content.strip())
            if sentence.strip()
        ] or [passage_content.strip()]
        claims = []
        for statement in statements:
            claim = ClaimModel(
                statement=statement,
                claim_type=claim_type,
                provenance_id=passage_id,
                confidence=0.95,
            )
            self.session.add(claim)
            await self.session.flush()
            self.session.add(
                EvidenceLinkModel(
                    claim_id=claim.id,
                    passage_id=passage_id,
                    relation_type=RelationType.SUPPORTS,
                    confidence_weight=1.0,
                )
            )
            claims.append(claim)

        await self.session.commit()
        for claim in claims:
            await self.session.refresh(claim)
        
        logger.info("Claims extracted and evidence-linked", claim_count=len(claims), type=claim_type.name)
        return claims
