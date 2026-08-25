from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.infrastructure.database.models import ResearchRunModel, ResearchStepModel
from datetime import datetime, timezone

class ResearchRunService:
    """
    Manages research runs, execution steps (retrieval, source-selection, evidence, validation),
    error tracking, output references, and inspection of run history and reproducibility.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_run(self, query: str) -> ResearchRunModel:
        run = ResearchRunModel(
            query=query,
            status="RUNNING"
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def start_run(self, query: str) -> ResearchRunModel:
        """Compatibility entry point for the existing run lifecycle API."""
        return await self.create_run(query)

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

    async def fail_run(self, run_id: str, error_message: str) -> Optional[ResearchRunModel]:
        run = await self.session.get(ResearchRunModel, run_id)
        if run:
            run.status = "FAILED"
            run.error_message = error_message
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
            "query": run.query,
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
                    "created_at": s.created_at
                }
                for s in steps
            ]
        }
