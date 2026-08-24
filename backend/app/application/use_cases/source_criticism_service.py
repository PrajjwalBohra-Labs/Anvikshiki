from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.infrastructure.database.models import SourceCriticismModel, SourceModel
from backend.app.domain.models.enums import EvidenceStatus
from backend.app.core.errors import AnvikshikiDomainError

class SourceCriticismEngine:
    """
    Evaluates sources objectively across proximity, translation dependence, 
    methodology, and historical context without ideological or national bias.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def evaluate_source(
        self,
        source_id: str,
        finding: str,
        basis: str,
        confidence: float = 1.0,
        status: EvidenceStatus = EvidenceStatus.PLAUSIBLE,
        supporting_evidence: Optional[Dict[str, Any]] = None,
        contradicting_evidence: Optional[Dict[str, Any]] = None
    ) -> SourceCriticismModel:
        source = await self.session.get(SourceModel, source_id)
        if not source:
            raise AnvikshikiDomainError(f"Source {source_id} not found.", status_code=404)

        criticism = SourceCriticismModel(
            source_id=source_id,
            finding=finding,
            basis=basis,
            confidence=confidence,
            status=status,
            supporting_evidence_payload=supporting_evidence,
            contradicting_evidence_payload=contradicting_evidence
        )
        self.session.add(criticism)
        await self.session.commit()
        await self.session.refresh(criticism)
        return criticism