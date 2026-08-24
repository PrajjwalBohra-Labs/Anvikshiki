from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.infrastructure.database.models import EpistemicStateModel, CognitiveObservationModel, MisconceptionModel
from backend.app.domain.models.memory import CognitiveObservation, MisconceptionRecord

class MemoryService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_or_update_epistemic_position(
        self,
        user_id: str,
        claim_statement: str,
        position: str,
        confidence: float,
        supporting_evidence: list | None = None,
        counterarguments: list | None = None,
        status: str = "under_investigation"
    ) -> EpistemicStateModel:
        # Find existing position on claim
        result = await self.session.execute(
            select(EpistemicStateModel).filter(
                EpistemicStateModel.user_id == user_id,
                EpistemicStateModel.claim_statement == claim_statement
            )
        )
        existing = result.scalars().first()

        if existing:
            existing.user_position = position
            existing.confidence = confidence
            existing.status = status
            existing.supporting_evidence = {"items": supporting_evidence or []}
            existing.counterarguments = {"items": counterarguments or []}
            await self.session.flush()
            return existing

        new_state = EpistemicStateModel(
            user_id=user_id,
            claim_statement=claim_statement,
            user_position=position,
            confidence=confidence,
            status=status,
            supporting_evidence={"items": supporting_evidence or []},
            counterarguments={"items": counterarguments or []}
        )
        self.session.add(new_state)
        await self.session.flush()
        return new_state

    async def record_cognitive_observation(
        self,
        user_id: str,
        pattern_name: str,
        description: str,
        evidence_dialogue_turn: str,
        confidence: float = 0.75
    ) -> CognitiveObservationModel:
        obs = CognitiveObservationModel(
            user_id=user_id,
            pattern_name=pattern_name,
            description=description,
            evidence_dialogue_turn=evidence_dialogue_turn,
            confidence=confidence
        )
        self.session.add(obs)
        await self.session.flush()
        return obs

    async def get_user_epistemic_history(self, user_id: str) -> List[EpistemicStateModel]:
        result = await self.session.execute(
            select(EpistemicStateModel).filter(EpistemicStateModel.user_id == user_id)
        )
        return list(result.scalars().all())