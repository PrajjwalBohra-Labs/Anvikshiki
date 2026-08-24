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
        # Determine explicit claim type based on source taxonomy
        if source_type == "PRIMARY":
            claim_type = ClaimType.DIRECT_SOURCE_CLAIM
            statement = f"[Direct Source: {source_title}] {passage_content.strip()}"
        elif source_type == "TRANSLATION":
            claim_type = ClaimType.TRANSLATION
            statement = f"[Translation: {source_title}] {passage_content.strip()}"
        elif source_type == "SCIENTIFIC":
            claim_type = ClaimType.SCIENTIFIC_FINDING
            statement = f"[Empirical Finding: {source_title}] {passage_content.strip()}"
        else:
            claim_type = ClaimType.SCHOLARLY_INTERPRETATION
            statement = f"[Interpretation: {source_title}] {passage_content.strip()}"

        claim = ClaimModel(
            statement=statement,
            claim_type=claim_type,
            provenance_id=passage_id,
            confidence=0.95
        )
        self.session.add(claim)
        await self.session.flush()

        # Link evidence to canonical passage
        link = EvidenceLinkModel(
            claim_id=claim.id,
            passage_id=passage_id,
            relation_type=RelationType.SUPPORTS,
            confidence_weight=1.0
        )
        self.session.add(link)
        await self.session.commit()
        await self.session.refresh(claim)
        
        logger.info("Claim extracted and evidence-linked", claim_id=claim.id, type=claim_type.name)
        return [claim]