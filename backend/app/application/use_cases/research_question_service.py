from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.infrastructure.database.models import ResearchQuestionModel

class ResearchQuestionService:
    """
    Manages research inquiries, subquestions, scope, constraints, 
    user positions, open questions, and research history for continuity.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_question(
        self,
        main_question: str,
        subquestions: Optional[List[str]] = None,
        scope: Optional[str] = None,
        domain: Optional[str] = None,
        constraints: Optional[List[str]] = None,
        user_position: Optional[str] = None
    ) -> ResearchQuestionModel:
        rq = ResearchQuestionModel(
            main_question=main_question,
            subquestions=subquestions or [],
            scope=scope,
            domain=domain,
            constraints=constraints or [],
            user_position=user_position,
            open_questions=[],
            research_history=[]
        )
        self.session.add(rq)
        await self.session.commit()
        await self.session.refresh(rq)
        return rq

    async def update_research_history(self, question_id: str, history_entry: Dict[str, Any]) -> Optional[ResearchQuestionModel]:
        rq = await self.session.get(ResearchQuestionModel, question_id)
        if rq:
            history = list(rq.research_history) if rq.research_history else []
            history.append(history_entry)
            rq.research_history = history
            await self.session.commit()
            await self.session.refresh(rq)
        return rq