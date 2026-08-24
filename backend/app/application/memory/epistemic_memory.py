from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.infrastructure.database.models import EpistemicPositionModel, EpistemicHistoryModel
import structlog

logger = structlog.get_logger(__name__)

class EpistemicMemoryService:
    """
    Manages user epistemic positions (claims, confidence, evidence, counterarguments, status),
    persists position state transitions, and retains complete chronological history.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_position(
        self,
        user_id: str,
        claim_statement: str,
        position: str,
        confidence: float = 1.0,
        supporting_evidence: Optional[List[Dict[str, Any]]] = None,
        counterarguments: Optional[List[Dict[str, Any]]] = None,
        status: str = "tentative"
    ) -> EpistemicPositionModel:
        valid_statuses = {"tentative", "accepted", "rejected", "contested", "under investigation", "unresolved"}
        if status not in valid_statuses:
            raise ValueError(f"Invalid epistemic status '{status}'. Must be one of {valid_statuses}.")

        pos = EpistemicPositionModel(
            user_id=user_id,
            claim_statement=claim_statement,
            position=position,
            confidence=confidence,
            supporting_evidence_payload=supporting_evidence or [],
            counterarguments_payload=counterarguments or [],
            status=status
        )
        self.session.add(pos)
        await self.session.commit()
        await self.session.refresh(pos)
        logger.info("Epistemic position recorded", position_id=pos.id, status=status)
        return pos

    async def update_position_status(
        self,
        position_id: str,
        new_status: str,
        change_reason: Optional[str] = None
    ) -> EpistemicPositionModel:
        valid_statuses = {"tentative", "accepted", "rejected", "contested", "under investigation", "unresolved"}
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid epistemic status '{new_status}'. Must be one of {valid_statuses}.")

        pos = await self.session.get(EpistemicPositionModel, position_id)
        if not pos:
            raise ValueError(f"Epistemic position '{position_id}' not found.")

        old_status = pos.status
        if old_status != new_status:
            # Record history transition
            history_entry = EpistemicHistoryModel(
                position_id=pos.id,
                previous_status=old_status,
                new_status=new_status,
                change_reason=change_reason
            )
            self.session.add(history_entry)
            pos.status = new_status
            await self.session.commit()
            await self.session.refresh(pos)
            logger.info("Epistemic position status updated and history retained", position_id=pos.id, old=old_status, new=new_status)

        return pos

    async def get_user_positions(self, user_id: str) -> List[Dict[str, Any]]:
        stmt = select(EpistemicPositionModel).where(EpistemicPositionModel.user_id == user_id)
        result = await self.session.execute(stmt)
        positions = result.scalars().all()

        output = []
        for p in positions:
            hist_stmt = select(EpistemicHistoryModel).where(EpistemicHistoryModel.position_id == p.id).order_by(EpistemicHistoryModel.timestamp.asc())
            hist_res = await self.session.execute(hist_stmt)
            history = hist_res.scalars().all()

            output.append({
                "position_id": p.id,
                "claim_statement": p.claim_statement,
                "position": p.position,
                "confidence": p.confidence,
                "supporting_evidence": p.supporting_evidence_payload,
                "counterarguments": p.counterarguments_payload,
                "status": p.status,
                "updated_at": p.updated_at,
                "history": [
                    {
                        "previous_status": h.previous_status,
                        "new_status": h.new_status,
                        "change_reason": h.change_reason,
                        "timestamp": h.timestamp
                    }
                    for h in history
                ]
            })
        return output