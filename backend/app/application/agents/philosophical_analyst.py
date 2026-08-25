from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.app.infrastructure.database.models import ArgumentModel, PremiseModel, ObjectionModel, AssumptionModel, EvidenceLinkModel, PassageModel
from backend.app.domain.models.enums import RelationType

logger = structlog.get_logger(__name__)

class PhilosophicalAnalyst:
    """
    Reconstructs dialectical arguments, maps premises to evidence passages,
    and preserves original philosophical terminology.
    """
    def __init__(self, session: Optional[AsyncSession] = None):
        self.session = session

    async def reconstruct_argument(
        self,
        title: str,
        conclusion_statement: Optional[str] = None,
        conclusion: Optional[str] = None,
        premises: Optional[List[Dict[str, Any]]] = None,
        objections: Optional[List[Dict[str, Any]]] = None,
        assumptions: Optional[List[Dict[str, Any]]] = None
    ) -> ArgumentModel:
        final_conclusion = conclusion_statement or conclusion or "Unspecified conclusion"

        arg = ArgumentModel(
            title=title,
            conclusion_statement=final_conclusion
        )
        
        if self.session:
            self.session.add(arg)
            await self.session.flush()

            if premises:
                for p in premises:
                    premise = PremiseModel(
                        argument_id=arg.id,
                        statement=p.get("statement", ""),
                        is_supported=bool(p.get("passage_id"))
                    )
                    self.session.add(premise)
                    await self.session.flush()

                    if p.get("passage_id"):
                        if not await self.session.get(PassageModel, p["passage_id"]):
                            await self.session.rollback()
                            raise ValueError(
                                "Philosophical analysis validation failed: premise passage was not found."
                            )
                        link = EvidenceLinkModel(
                            premise_id=premise.id,
                            passage_id=p["passage_id"],
                            relation_type=RelationType.SUPPORTS,
                            confidence_weight=1.0
                        )
                        self.session.add(link)

            if objections:
                for obj in objections:
                    objection_record = ObjectionModel(
                        argument_id=arg.id,
                        objection_statement=obj.get("statement", obj.get("objection", "")),
                        reply_statement=obj.get("reply")
                    )
                    self.session.add(objection_record)

            if assumptions:
                for assump in assumptions:
                    assumption_record = AssumptionModel(
                        argument_id=arg.id,
                        statement=assump if isinstance(assump, str) else assump.get("statement", "")
                    )
                    self.session.add(assumption_record)

            await self.session.commit()
            await self.session.refresh(arg)
            
        logger.info("Argument reconstructed successfully", argument_id=arg.id, title=title)
        return arg
