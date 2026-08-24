from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.infrastructure.database.models import ResearchRunModel, ResearchStepModel

class ResearchRunService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def start_run(self, query: str) -> ResearchRunModel:
        run = ResearchRunModel(query=query, status="RUNNING")
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def log_step(self, run_id: str, step_name: str, status: str = "SUCCESS", payload: Optional[Dict[str, Any]] = None) -> ResearchStepModel:
        step = ResearchStepModel(run_id=run_id, step_name=step_name, status=status, payload=payload)
        self.session.add(step)
        await self.session.commit()
        await self.session.refresh(step)
        return step

    async def complete_run(self, run_id: str) -> ResearchRunModel:
        run = await self.session.get(ResearchRunModel, run_id)
        if run:
            run.status = "COMPLETED"
            run.finished_at = datetime.now(timezone.utc)
            await self.session.commit()
            await self.session.refresh(run)
        return run

    async def fail_run(self, run_id: str, error_message: str) -> ResearchRunModel:
        run = await self.session.get(ResearchRunModel, run_id)
        if run:
            run.status = "FAILED"
            run.error_message = error_message
            run.finished_at = datetime.now(timezone.utc)
            await self.session.commit()
            await self.session.refresh(run)
        return run