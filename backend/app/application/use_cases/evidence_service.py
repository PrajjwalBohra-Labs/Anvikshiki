from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.infrastructure.database.models import EvidenceLinkModel, PassageModel, ClaimModel
from backend.app.domain.models.enums import RelationType
from backend.app.core.errors import AnvikshikiDomainError
import structlog

logger = structlog.get_logger(__name__)

class EvidenceService:
    """
    Manages evidence extraction, validation, confidence weighting, 
    and relationship mapping (Support, Contradiction, Qualification).
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_evidence_relation(
        self,
        claim_id: str,
        passage_id: str,
        relation_type: RelationType,
        confidence_weight: float = 1.0
    ) -> EvidenceLinkModel:
        """Links a passage as evidence to a claim with validation and confidence scoring."""
        # 1. Validate existence of claim and passage
        claim = await self.session.get(ClaimModel, claim_id)
        if not claim:
            raise AnvikshikiDomainError(f"Claim {claim_id} not found.", status_code=404)
            
        passage = await self.session.get(PassageModel, passage_id)
        if not passage:
            raise AnvikshikiDomainError(f"Passage {passage_id} not found.", status_code=404)

        if not passage.content or len(passage.content.strip()) == 0:
            raise AnvikshikiDomainError("Evidence passage content cannot be empty.", status_code=422)

        # 2. Create and persist evidence link
        evidence_link = EvidenceLinkModel(
            claim_id=claim_id,
            passage_id=passage_id,
            relation_type=relation_type,
            confidence_weight=confidence_weight
        )
        self.session.add(evidence_link)
        await self.session.commit()
        await self.session.refresh(evidence_link)
        
        logger.info("Evidence relation established", claim_id=claim_id, passage_id=passage_id, relation=relation_type)
        return evidence_link

    async def trace_evidence_source(self, evidence_link_id: str) -> Dict[str, Any]:
        """Traces an evidence link back through its passage and document to its root source."""
        link = await self.session.get(EvidenceLinkModel, evidence_link_id)
        if not link:
            return {}

        passage = await self.session.get(PassageModel, link.passage_id)
        document = passage.document if passage else None
        source = document.source if document else None

        return {
            "evidence_link": link,
            "passage": passage,
            "document": document,
            "source": source
        }