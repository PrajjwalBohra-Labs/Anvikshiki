from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.app.infrastructure.database.models import CognitiveObservationModel

logger = structlog.get_logger(__name__)

class CognitiveMemoryService:
    """
    Records observable reasoning patterns only, ensuring every observation is evidence-linked,
    includes confidence, timestamps, and originating interactions, avoiding unsupported personality labels.
    Provides user inspection and deletion controls.
    """
    VALID_OBSERVATION_TYPES = {
        "reasoning strength",
        "recurring reasoning error",
        "source-checking behavior",
        "confidence calibration",
        "tendency to overgeneralize",
        "response to counterexample",
        "ability to distinguish evidence/interpretation"
    }

    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_observation(
        self,
        user_id: str,
        observation_type: str,
        observation_detail: str,
        evidence_reference: str,
        originating_interaction_id: str,
        confidence: float = 1.0
    ) -> CognitiveObservationModel:
        if observation_type not in self.VALID_OBSERVATION_TYPES:
            raise ValueError(f"Invalid observation type '{observation_type}'. Must be one of {self.VALID_OBSERVATION_TYPES}.")
        
        if not evidence_reference or len(evidence_reference.strip()) == 0:
            raise ValueError("Cognitive observation rejected: Observations must be strictly evidence-linked.")

        obs = CognitiveObservationModel(
            user_id=user_id,
            observation_type=observation_type,
            observation_detail=observation_detail,
            evidence_reference=evidence_reference,
            confidence=confidence,
            originating_interaction_id=originating_interaction_id
        )
        self.session.add(obs)
        await self.session.commit()
        await self.session.refresh(obs)
        logger.info("Cognitive observation recorded", observation_id=obs.id, type=observation_type)
        return obs

    async def inspect_observations(self, user_id: str, observation_type: str | None = None) -> list[dict[str, Any]]:
        stmt = select(CognitiveObservationModel).where(CognitiveObservationModel.user_id == user_id)
        if observation_type:
            stmt = stmt.where(CognitiveObservationModel.observation_type == observation_type)
        
        result = await self.session.execute(stmt)
        observations = result.scalars().all()

        return [
            {
                "observation_id": o.id,
                "observation_type": o.observation_type,
                "observation_detail": o.observation_detail,
                "evidence_reference": o.evidence_reference,
                "confidence": o.confidence,
                "originating_interaction_id": o.originating_interaction_id,
                "timestamp": o.timestamp,
                "is_evidence_linked": True
            }
            for o in observations
        ]

    async def delete_observation(self, observation_id: str, user_id: str) -> bool:
        obs = await self.session.get(CognitiveObservationModel, observation_id)
        if not obs or obs.user_id != user_id:
            return False
        
        await self.session.delete(obs)
        await self.session.commit()
        logger.info("Cognitive observation deleted by user", observation_id=observation_id)
        return True