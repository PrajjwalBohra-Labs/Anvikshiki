from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.infrastructure.database.models import (
    ArgumentModel, PremiseModel, AssumptionModel, PassageModel, EvidenceLinkModel
)
from backend.app.domain.models.enums import RelationType
import structlog

logger = structlog.get_logger(__name__)

class PhilosophicalAnalyst:
    """
    Responsible for analyzing concepts, reconstructing arguments, distinguishing 
    source claims from scholarly interpretations, identifying underlying assumptions, 
    preserving original terminology, and linking analyses directly to evidence passages.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def reconstruct_argument(
        self,
        title: str,
        conclusion_statement: str,
        premises: List[Dict[str, Any]],
        assumptions: List[str],
        original_terminology: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Reconstructs a philosophical argument, anchoring premises to canonical evidence passages
        while preserving original-language terminology and marking interpretive distinctions.
        """
        # 1. Create Argument record
        argument = ArgumentModel(
            title=title,
            conclusion_statement=conclusion_statement
        )
        self.session.add(argument)
        await self.session.flush()

        created_premises = []
        for p_data in premises:
            passage_id = p_data.get("passage_id")
            # Verify passage reference exists to maintain source-grounding
            if passage_id:
                passage = await self.session.get(PassageModel, passage_id)
                if not passage:
                    raise ValueError(f"Philosophical analysis validation failed: Passage '{passage_id}' does not exist.")

            premise = PremiseModel(
                argument_id=argument.id,
                statement=p_data["statement"],
                is_supported=bool(passage_id)
            )
            self.session.add(premise)
            await self.session.flush()

            if passage_id:
                link = EvidenceLinkModel(
                    premise_id=premise.id,
                    passage_id=passage_id,
                    relation_type=RelationType.SUPPORTS,
                    confidence_weight=p_data.get("confidence", 1.0)
                )
                self.session.add(link)

            created_premises.append({
                "statement": premise.statement,
                "is_supported": premise.is_supported,
                "passage_id": passage_id
            })

        # 2. Add underlying assumptions
        created_assumptions = []
        for asm_text in assumptions:
            assumption = AssumptionModel(
                argument_id=argument.id,
                statement=asm_text
            )
            self.session.add(assumption)
            created_assumptions.append(asm_text)

        await self.session.commit()

        logger.info("Philosophical argument reconstructed successfully", argument_id=argument.id)

        return {
            "argument_id": argument.id,
            "title": argument.title,
            "conclusion": argument.conclusion_statement,
            "premises": created_premises,
            "assumptions": created_assumptions,
            "original_terminology": original_terminology or {},
            "analysis_type": "SOURCE_GROUNDED_RECONSTRUCTION",
            "is_interpretation": True
        }