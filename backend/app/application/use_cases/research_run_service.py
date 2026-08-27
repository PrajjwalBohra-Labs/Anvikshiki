from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.infrastructure.database.models import ResearchQuestionModel, ResearchRunModel, ResearchStepModel
from datetime import datetime, timezone
from uuid import uuid4

class ResearchRunService:
    """
    Manages research runs, execution steps (retrieval, source-selection, evidence, validation),
    error tracking, output references, and inspection of run history and reproducibility.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_question(
        self,
        query: str,
        user_id: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> ResearchQuestionModel:
        question = ResearchQuestionModel(
            user_id=user_id,
            main_question=query,
            domain=domain,
            subquestions=[],
            open_questions=[],
            research_status="ACTIVE",
            research_history=[],
        )
        self.session.add(question)
        await self.session.commit()
        await self.session.refresh(question)
        return question

    async def create_run(
        self,
        query: str,
        user_id: Optional[str] = None,
        research_question_id: Optional[str] = None,
        domain: Optional[str] = None,
        depth: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> ResearchRunModel:
        run = ResearchRunModel(
            query=query,
            user_id=user_id,
            research_question_id=research_question_id,
            thread_id=thread_id or str(uuid4()),
            domain=domain,
            depth=depth,
            status="RUNNING",
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def start_run(self, query: str) -> ResearchRunModel:
        """Compatibility entry point for the existing run lifecycle API."""
        return await self.create_run(query)

    async def list_runs(
        self,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ResearchRunModel]:
        stmt = select(ResearchRunModel).order_by(ResearchRunModel.started_at.desc())
        if user_id is not None:
            stmt = stmt.where(ResearchRunModel.user_id == user_id)
        if status is not None:
            stmt = stmt.where(ResearchRunModel.status == status)
        result = await self.session.execute(stmt.offset(offset).limit(limit))
        return list(result.scalars().all())

    async def get_owned_run(self, run_id: str, user_id: Optional[str] = None) -> Optional[ResearchRunModel]:
        run = await self.session.get(ResearchRunModel, run_id)
        if run is None or (user_id is not None and run.user_id != user_id):
            return None
        return run

    async def add_step(
        self,
        run_id: str,
        step_name: str,
        step_type: str,
        status: str = "SUCCESS",
        payload: Optional[Dict[str, Any]] = None
    ) -> ResearchStepModel:
        step = ResearchStepModel(
            run_id=run_id,
            step_name=step_name,
            step_type=step_type,
            status=status,
            payload=payload or {}
        )
        self.session.add(step)
        await self.session.commit()
        await self.session.refresh(step)
        return step

    async def log_step(
        self,
        run_id: str,
        step_name: str,
        step_type: Optional[str] = None,
        status: str = "SUCCESS",
        payload: Optional[Dict[str, Any]] = None,
    ) -> ResearchStepModel:
        return await self.add_step(
            run_id,
            step_name=step_name,
            step_type=step_type or step_name,
            status=status,
            payload=payload,
        )

    async def record_event(
        self,
        run_id: str,
        event: Dict[str, Any],
        sequence: int,
    ) -> ResearchStepModel:
        event_id = f"{run_id}:{sequence}"
        existing = await self.session.execute(
            select(ResearchStepModel).where(
                ResearchStepModel.run_id == run_id,
                ResearchStepModel.event_sequence == sequence,
            )
        )
        existing_step = existing.scalars().first()
        if existing_step is not None:
            return existing_step
        step = ResearchStepModel(
            run_id=run_id,
            event_id=event_id,
            event_sequence=sequence,
            step_name=str(event.get("event", "research_event")),
            step_type="SSE_EVENT",
            status=str(event.get("status", "EMITTED")),
            payload=event,
        )
        self.session.add(step)
        await self.session.commit()
        await self.session.refresh(step)
        return step

    async def list_events(self, run_id: str, after_sequence: int = 0) -> List[ResearchStepModel]:
        stmt = (
            select(ResearchStepModel)
            .where(
                ResearchStepModel.run_id == run_id,
                ResearchStepModel.step_type == "SSE_EVENT",
                ResearchStepModel.event_sequence > after_sequence,
            )
            .order_by(ResearchStepModel.event_sequence.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def fail_run(self, run_id: str, error_message: str) -> Optional[ResearchRunModel]:
        run = await self.session.get(ResearchRunModel, run_id)
        if run:
            run.status = "FAILED"
            run.error_message = error_message
            run.finished_at = datetime.now(timezone.utc)
            await self.session.commit()
            await self.session.refresh(run)
        return run

    async def cancel_run(self, run_id: str) -> Optional[ResearchRunModel]:
        run = await self.session.get(ResearchRunModel, run_id)
        if run:
            run.status = "CANCELLED"
            run.finished_at = datetime.now(timezone.utc)
            await self.session.commit()
            await self.session.refresh(run)
        return run

    async def complete_run(self, run_id: str, output_references: Optional[Dict[str, Any]] = None) -> Optional[ResearchRunModel]:
        run = await self.session.get(ResearchRunModel, run_id)
        if run:
            run.status = "COMPLETED"
            run.output_references = output_references or {}
            run.finished_at = datetime.now(timezone.utc)
            await self.session.commit()
            await self.session.refresh(run)
        return run

    async def get_run_details(self, run_id: str) -> Optional[Dict[str, Any]]:
        run = await self.session.get(ResearchRunModel, run_id)
        if not run:
            return None
        
        stmt = select(ResearchStepModel).where(ResearchStepModel.run_id == run_id).order_by(ResearchStepModel.created_at.asc())
        result = await self.session.execute(stmt)
        steps = result.scalars().all()

        last_successful_step = None
        for s in reversed(steps):
            if s.status == "SUCCESS":
                last_successful_step = s.step_name
                break

        return {
            "run_id": run.id,
            "research_question_id": run.research_question_id,
            "thread_id": run.thread_id,
            "user_id": run.user_id,
            "query": run.query,
            "domain": run.domain,
            "depth": run.depth,
            "status": run.status,
            "error_message": run.error_message,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "output_references": run.output_references,
            "last_successful_step": last_successful_step,
            "steps": [
                {
                    "step_name": s.step_name,
                    "step_type": s.step_type,
                    "status": s.status,
                    "payload": s.payload,
                    "event_id": s.event_id,
                    "event_sequence": s.event_sequence,
                    "created_at": s.created_at
                }
                for s in steps
            ]
        }
