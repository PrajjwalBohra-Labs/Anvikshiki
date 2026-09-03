from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.app.core.errors import AnvikshikiDomainError
from backend.app.infrastructure.database.models import (
    ArgumentModel,
    AssumptionModel,
    EvidenceLinkModel,
    ObjectionModel,
    PremiseModel,
)


class ArgumentReconstructionService:
    """
    Reconstructs arguments structurally, linking premises to evidence, 
    detecting unsupported premises, and attaching counterarguments/objections.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_argument(
        self,
        title: str,
        conclusion: str,
        premises: list[str],
        objections: list[dict[str, str]] | None = None,
        assumptions: list[str] | None = None
    ) -> ArgumentModel:
        arg = ArgumentModel(title=title, conclusion_statement=conclusion)
        self.session.add(arg)
        await self.session.flush()

        for p_stmt in premises:
            premise = PremiseModel(argument_id=arg.id, statement=p_stmt, is_supported=False)
            self.session.add(premise)

        if objections:
            for obj in objections:
                objection = ObjectionModel(
                    argument_id=arg.id,
                    objection_statement=obj.get("objection", ""),
                    reply_statement=obj.get("reply")
                )
                self.session.add(objection)

        if assumptions:
            for asm in assumptions:
                assumption = AssumptionModel(argument_id=arg.id, statement=asm)
                self.session.add(assumption)

        await self.session.commit()
        await self.session.refresh(arg)
        return arg

    async def link_premise_evidence(self, premise_id: str, passage_id: str) -> EvidenceLinkModel:
        premise = await self.session.get(PremiseModel, premise_id)
        if not premise:
            raise AnvikshikiDomainError(f"Premise {premise_id} not found.", status_code=404)

        evidence = EvidenceLinkModel(
            premise_id=premise_id,
            passage_id=passage_id,
            relation_type="SUPPORTS",
            confidence_weight=1.0
        )
        premise.is_supported = True
        self.session.add(evidence)
        await self.session.commit()
        await self.session.refresh(evidence)
        return evidence

    async def detect_unsupported_premises(self, argument_id: str) -> list[PremiseModel]:
        result = await self.session.execute(
            select(PremiseModel).where(
                PremiseModel.argument_id == argument_id,
                ~PremiseModel.is_supported,
            )
        )
        return list(result.scalars().all())

    async def serialize_argument(self, argument_id: str) -> dict[str, Any]:
        arg = await self.session.get(ArgumentModel, argument_id)
        if not arg:
            return {}

        premises_res = await self.session.execute(select(PremiseModel).where(PremiseModel.argument_id == argument_id))
        objections_res = await self.session.execute(select(ObjectionModel).where(ObjectionModel.argument_id == argument_id))
        assumptions_res = await self.session.execute(select(AssumptionModel).where(AssumptionModel.argument_id == argument_id))

        return {
            "id": arg.id,
            "title": arg.title,
            "conclusion": arg.conclusion_statement,
            "premises": [{"id": p.id, "statement": p.statement, "is_supported": p.is_supported} for p in premises_res.scalars().all()],
            "objections": [{"objection": o.objection_statement, "reply": o.reply_statement} for o in objections_res.scalars().all()],
            "assumptions": [a.statement for a in assumptions_res.scalars().all()]
        }
