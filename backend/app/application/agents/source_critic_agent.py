from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.infrastructure.database.models import SourceModel, SourceCriticismModel
from backend.app.domain.models.enums import EvidenceStatus
import structlog

logger = structlog.get_logger(__name__)

class SourceCriticAgent:
    """
    Responsible for investigating sources: evaluating primary-source proximity,
    translation dependence, methodological concerns, and competing interpretations,
    producing strict evidence-linked findings.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def evaluate_source(
        self,
        source_id: str,
        finding: str,
        basis: str,
        confidence: float = 0.9,
        status: EvidenceStatus = EvidenceStatus.CONTESTED,
        supporting_payload: Optional[Dict[str, Any]] = None,
        contradicting_payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluates source provenance, translation dependence, and methodological constraints,
        persisting an inspectable, evidence-linked finding.
        """
        # 1. Validate source existence
        source = await self.session.get(SourceModel, source_id)
        if not source:
            raise ValueError(f"Source criticism failed: Source with ID '{source_id}' does not exist.")

        # 2. Guardrail: Never produce unsupported accusations (require a factual basis)
        if not basis or len(basis.strip()) == 0:
            raise ValueError("Source criticism rejected: Findings must be grounded in an explicit textual/provenance basis.")

        # 3. Create Source Criticism record
        criticism = SourceCriticismModel(
            source_id=source.id,
            finding=finding,
            basis=basis,
            confidence=confidence,
            status=status,
            supporting_evidence_payload=supporting_payload or {},
            contradicting_evidence_payload=contradicting_payload or {}
        )
        self.session.add(criticism)
        await self.session.commit()
        await self.session.refresh(criticism)

        logger.info("Source criticism recorded successfully", source_id=source.id, criticism_id=criticism.id)

        return {
            "criticism_id": criticism.id,
            "source_id": source.id,
            "finding": criticism.finding,
            "basis": criticism.basis,
            "status": criticism.status,
            "confidence": criticism.confidence,
            "inspectable": True
        }