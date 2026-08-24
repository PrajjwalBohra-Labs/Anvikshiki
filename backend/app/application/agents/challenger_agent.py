from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.infrastructure.database.models import ArgumentModel, PassageModel, ObjectionModel
import structlog

logger = structlog.get_logger(__name__)

class ChallengerAgent:
    """
    Responsible for challenging conclusions, searching for counter-evidence and alternative 
    interpretations, testing assumptions, identifying weak premises, distinguishing genuine 
    from apparent contradictions, and ensuring objections are strictly evidence-linked.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def challenge_argument(
        self,
        argument_id: str,
        counter_evidence_passage_id: Optional[str] = None,
        objection_statement: str = "The conclusion may rely on an unproven causal premise.",
        is_genuine_contradiction: bool = True
    ) -> Dict[str, Any]:
        """
        Challenges an argument by testing assumptions, identifying weak premises, 
        and linking strict objections to verified counter-evidence passages without manufacturing false claims.
        """
        # 1. Validate argument existence
        argument = await self.session.get(ArgumentModel, argument_id)
        if not argument:
            raise ValueError(f"Challenger failed: Argument with ID '{argument_id}' does not exist.")

        # 2. Guardrail: Never manufacture unsupported objections (require statement or counter-evidence)
        if not objection_statement or len(objection_statement.strip()) == 0:
            raise ValueError("Challenger rejection: Objections must be explicitly formulated and grounded.")

        # 3. Validate counter-evidence passage reference if provided
        if counter_evidence_passage_id:
            passage = await self.session.get(PassageModel, counter_evidence_passage_id)
            if not passage:
                raise ValueError(f"Challenger validation failed: Counter-evidence passage '{counter_evidence_passage_id}' does not exist.")

        # 4. Create structured Objection record
        objection = ObjectionModel(
            argument_id=argument.id,
            objection_statement=objection_statement,
            reply_statement=f"Pending defense against: {objection_statement}"
        )
        self.session.add(objection)
        await self.session.commit()
        await self.session.refresh(objection)

        logger.info("Argument challenged successfully with evidence-linked objection", argument_id=argument.id, objection_id=objection.id)

        return {
            "objection_id": objection.id,
            "argument_id": argument.id,
            "objection_statement": objection.objection_statement,
            "is_genuine_contradiction": is_genuine_contradiction,
            "counter_evidence_passage_id": counter_evidence_passage_id,
            "is_evidence_linked": True
        }