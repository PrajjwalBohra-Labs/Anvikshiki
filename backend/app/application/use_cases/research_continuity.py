from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.infrastructure.database.models import (
    ResearchQuestionModel, ResearchRunModel, ResearchStepModel, EpistemicPositionModel
)
import structlog

logger = structlog.get_logger(__name__)

class ResearchContinuityService:
    """
    Manages research continuity: allowing users to leave and resume previous investigations,
    retrieving established findings, unresolved/open questions, user epistemic positions, 
    evidence trails, research timelines, and suggesting the next logical investigation step.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def resume_investigation(
        self,
        research_question_id: str,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Resumes a previous investigation by assembling all contextual state, findings,
        evidence trails, positions, timelines, and next suggested steps.
        """
        # 1. Retrieve Research Question
        question = await self.session.get(ResearchQuestionModel, research_question_id)
        if not question:
            logger.warning("Research question not found for continuity resumption", question_id=research_question_id)
            return None

        # 2. Retrieve associated Research Runs & Steps (Evidence Trail & Timeline)
        run_stmt = select(ResearchRunModel).where(ResearchRunModel.query == question.main_question).order_by(ResearchRunModel.started_at.desc())
        run_result = await self.session.execute(run_stmt)
        runs = run_result.scalars().all()

        timeline = []
        evidence_trail = []
        established_findings = []

        for run in runs:
            step_stmt = select(ResearchStepModel).where(ResearchStepModel.run_id == run.id).order_by(ResearchStepModel.created_at.asc())
            step_res = await self.session.execute(step_stmt)
            steps = step_res.scalars().all()

            for step in steps:
                timeline.append({
                    "run_id": run.id,
                    "step_name": step.step_name,
                    "step_type": step.step_type,
                    "status": step.status,
                    "timestamp": step.created_at
                })
                if step.step_type == "EVIDENCE" and step.payload:
                    evidence_trail.append(step.payload)
                if step.status == "SUCCESS":
                    established_findings.append(f"Completed step: {step.step_name} in run {run.id}")

        # 3. Retrieve User Epistemic Positions
        pos_stmt = select(EpistemicPositionModel).where(EpistemicPositionModel.user_id == user_id)
        pos_res = await self.session.execute(pos_stmt)
        positions = pos_res.scalars().all()

        user_positions_summary = [
            {
                "claim": p.claim_statement,
                "position": p.position,
                "status": p.status,
                "confidence": p.confidence
            }
            for p in positions
        ]

        # 4. Determine Suggested Next Step
        open_qs = question.open_questions or []
        suggested_step = (
            f"Address open question: {open_qs[0]}" if open_qs else "Execute comparative source criticism or validation."
        )

        logger.info("Investigation successfully resumed", question_id=question.id)

        return {
            "research_question_id": question.id,
            "main_question": question.main_question,
            "subquestions": question.subquestions or [],
            "scope": question.scope,
            "domain": question.domain,
            "research_status": question.research_status,
            "established_findings": established_findings,
            "unresolved_questions": open_qs,
            "user_positions": user_positions_summary,
            "evidence_trail": evidence_trail,
            "research_timeline": timeline,
            "suggested_next_step": suggested_step
        }