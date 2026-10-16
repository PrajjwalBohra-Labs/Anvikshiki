from typing import Any

import structlog
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.app.infrastructure.database.models import (
    EpistemicPositionModel,
    ResearchQuestionModel,
    ResearchRunModel,
    ResearchStepModel,
)

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
    ) -> dict[str, Any] | None:
        """
        Resumes a previous investigation by assembling all contextual state, findings,
        evidence trails, positions, timelines, and next suggested steps.
        """
        # 1. Retrieve Research Question
        question = await self.session.get(ResearchQuestionModel, research_question_id)
        if not question:
            logger.warning("Research question not found for continuity resumption", question_id=research_question_id)
            return None
        if question.user_id is not None and question.user_id != user_id:
            return None

        # 2. Retrieve only runs belonging to this inquiry.  Older records did
        # not always persist the question foreign key, so retain a narrowly
        # scoped query fallback for those records without mixing other runs
        # that happen to have the same text.
        linked_stmt = (
            select(ResearchRunModel)
            .where(ResearchRunModel.research_question_id == question.id)
            .where(ResearchRunModel.user_id == user_id)
            .order_by(ResearchRunModel.started_at.desc())
        )
        linked_result = await self.session.execute(linked_stmt)
        runs = list(linked_result.scalars().all())
        if not runs:
            legacy_filters = [ResearchRunModel.query == question.main_question]
            if question.user_id is None:
                # Some historical rows were created before ownership was
                # attached to research runs. They are safe to recover only
                # for the corresponding unowned legacy question.
                legacy_filters.append(or_(ResearchRunModel.user_id == user_id, ResearchRunModel.user_id.is_(None)))
            else:
                legacy_filters.append(ResearchRunModel.user_id == user_id)
            legacy_stmt = (
                select(ResearchRunModel)
                .where(ResearchRunModel.research_question_id.is_(None))
                .where(*legacy_filters)
                .order_by(ResearchRunModel.started_at.desc())
            )
            legacy_result = await self.session.execute(legacy_stmt)
            runs = list(legacy_result.scalars().all())

        timeline = []
        evidence_trail = []
        established_findings = []
        latest_result: dict[str, Any] = {}

        for run in runs:
            if not latest_result and isinstance(run.output_references, dict):
                latest_result = run.output_references
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
                    if step.step_type not in {"SSE_EVENT", "GENERAL"}:
                        established_findings.append(f"Completed step: {step.step_name} in run {run.id}")

        # Prefer substantive inquiry artifacts from the latest completed run
        # over workflow labels.  Labels remain as a compatibility fallback for
        # historical runs that predate persisted result payloads.
        if latest_result:
            substantive = []
            for item in latest_result.get("synthesis", []) + latest_result.get("insights", []):
                if isinstance(item, dict):
                    text = item.get("conclusion") or item.get("insight") or item.get("claim")
                    if text:
                        substantive.append(str(text))
            for item in latest_result.get("validation", {}).get("validated_claims", []):
                if isinstance(item, dict) and item.get("statement"):
                    substantive.append(str(item["statement"]))
            if latest_result.get("final_response") and not substantive:
                substantive.append(str(latest_result["final_response"]))
            if substantive:
                established_findings = list(dict.fromkeys(substantive))

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
        gaps = (latest_result.get("reasoning", {}) or {}).get("gaps", []) if latest_result else []
        suggested_step = (
            f"Address open question: {open_qs[0]}" if open_qs else
            f"Investigate the grounded evidence gap: {gaps[0]}" if gaps else
            "Continue the inquiry only if a material, question-linked evidence gap remains."
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
            "suggested_next_step": suggested_step,
            "inquiry_context": {
                "original_question": question.main_question,
                "interpreted_question": question.interpreted_question,
                "current_requirements": question.intellectual_tasks or [],
                "supported_findings": established_findings,
                "unresolved_questions": open_qs,
                "latest_result": latest_result,
            }
        }
