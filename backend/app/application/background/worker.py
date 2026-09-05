"""Small durable worker for existing research orchestration."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.application.orchestration.research_workflow import (
    ResearchWorkflowEngine,
)
from backend.app.application.use_cases.research_run_service import ResearchRunService
from backend.app.infrastructure.database.models import (
    BackgroundJobModel,
    ResearchQuestionModel,
    ResearchRunModel,
)
from backend.app.infrastructure.database.session import AsyncSessionLocal

logger = structlog.get_logger(__name__)

JOB_TYPE_RESEARCH = "research"
PENDING = "PENDING"
RUNNING = "RUNNING"
COMPLETED = "COMPLETED"
FAILED = "FAILED"
CANCELLED = "CANCELLED"
MAX_ATTEMPTS = 3
SAFE_FAILURE = "Background research execution failed."


def deterministic_job_id(user_id: str, job_type: str, idempotency_key: str) -> str:
    """Return a stable UUID without putting credentials or payloads in it."""

    identity = f"anvikshiki:{job_type}:{user_id}:{idempotency_key}"
    return str(uuid5(NAMESPACE_URL, identity))


class BackgroundJobService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_research_job(
        self,
        user_id: str,
        query: str,
        domain: str | None,
        depth: str | None,
        idempotency_key: str,
        include_web: bool = False,
        request_id: str | None = None,
    ) -> tuple[BackgroundJobModel, bool]:
        job_id = deterministic_job_id(user_id, JOB_TYPE_RESEARCH, idempotency_key)
        existing = await self.session.get(BackgroundJobModel, job_id)
        if existing is not None:
            return existing, False

        question_id = str(uuid5(NAMESPACE_URL, f"{job_id}:question"))
        run_id = str(uuid5(NAMESPACE_URL, f"{job_id}:run"))
        question = ResearchQuestionModel(
            id=question_id,
            user_id=user_id,
            main_question=query,
            domain=domain,
            subquestions=[],
            open_questions=[],
            research_status="ACTIVE",
            research_history=[],
        )
        run = ResearchRunModel(
            id=run_id,
            user_id=user_id,
            research_question_id=question_id,
            thread_id=job_id,
            query=query,
            domain=domain,
            depth=depth,
            status=PENDING,
        )
        job = BackgroundJobModel(
            id=job_id,
            user_id=user_id,
            job_type=JOB_TYPE_RESEARCH,
            idempotency_key=idempotency_key,
            payload={"query": query, "domain": domain, "depth": depth, "include_web": include_web},
            status=PENDING,
            attempts=0,
            max_attempts=MAX_ATTEMPTS,
            research_run_id=run_id,
            request_id=request_id,
        )
        # These legacy models expose their foreign keys as scalar IDs rather
        # than ORM relationships. Flush each parent explicitly so the
        # database sees the referenced rows before their children.
        self.session.add(question)
        await self.session.flush()
        self.session.add(run)
        await self.session.flush()
        self.session.add(job)
        try:
            await self.session.flush()
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            existing = await self.session.get(BackgroundJobModel, job_id)
            if existing is None:
                raise
            return existing, False
        await self.session.refresh(job)
        logger.info(
            "background_job_created",
            job_id=job.id,
            job_type=job.job_type,
            request_id=job.request_id,
        )
        return job, True

    async def get_owned_job(self, job_id: str, user_id: str) -> BackgroundJobModel | None:
        job = await self.session.get(BackgroundJobModel, job_id)
        if job is None or job.user_id != user_id:
            return None
        return job

    async def cancel_owned_job(self, job_id: str, user_id: str) -> BackgroundJobModel | None:
        job = await self.get_owned_job(job_id, user_id)
        if job is None:
            return None
        if job.status == PENDING:
            job.status = CANCELLED
            job.finished_at = datetime.now(timezone.utc)
            job.updated_at = datetime.now(timezone.utc)
            if job.research_run_id:
                run = await self.session.get(ResearchRunModel, job.research_run_id)
                if run is not None and run.status == PENDING:
                    run.status = CANCELLED
                    run.finished_at = datetime.now(timezone.utc)
            await self.session.commit()
            logger.info("background_job_cancelled", job_id=job.id, job_type=job.job_type)
        return job

    async def claim_next(self) -> BackgroundJobModel | None:
        statement = (
            select(BackgroundJobModel)
            .where(BackgroundJobModel.status == PENDING)
            .order_by(BackgroundJobModel.created_at.asc(), BackgroundJobModel.id.asc())
            .limit(1)
        )
        if self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            statement = statement.with_for_update(skip_locked=True)
        result = await self.session.execute(statement)
        job = result.scalars().first()
        if job is None:
            return None
        job.status = RUNNING
        job.attempts += 1
        job.started_at = datetime.now(timezone.utc)
        job.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(job)
        logger.info(
            "background_job_started",
            job_id=job.id,
            job_type=job.job_type,
            attempt=job.attempts,
            request_id=job.request_id,
        )
        return job

    async def complete(self, job_id: str, result: dict[str, Any]) -> None:
        job = await self.session.get(BackgroundJobModel, job_id)
        if job is None:
            return
        job.status = COMPLETED
        job.result_payload = result
        job.error_message = None
        job.finished_at = datetime.now(timezone.utc)
        job.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def fail_or_retry(self, job_id: str) -> str | None:
        job = await self.session.get(BackgroundJobModel, job_id)
        if job is None:
            return None
        job.error_message = SAFE_FAILURE
        job.updated_at = datetime.now(timezone.utc)
        if job.attempts < job.max_attempts:
            job.status = PENDING
            job.started_at = None
            await self.session.commit()
            return PENDING
        job.status = FAILED
        job.finished_at = datetime.now(timezone.utc)
        await self.session.commit()
        return FAILED

    async def requeue_stale(self, stale_after: timedelta) -> int:
        cutoff = datetime.now(timezone.utc) - stale_after
        result = await self.session.execute(
            select(BackgroundJobModel).where(
                BackgroundJobModel.status == RUNNING,
                BackgroundJobModel.started_at < cutoff,
            )
        )
        recovered = 0
        for job in result.scalars().all():
            if job.attempts < job.max_attempts:
                job.status = PENDING
                job.started_at = None
            else:
                job.status = FAILED
                job.error_message = SAFE_FAILURE
                job.finished_at = datetime.now(timezone.utc)
            job.updated_at = datetime.now(timezone.utc)
            recovered += 1
        if recovered:
            await self.session.commit()
            logger.warning("background_jobs_recovered", count=recovered)
        return recovered


async def execute_research_job(job: BackgroundJobModel) -> dict[str, Any]:
    """Run one existing research workflow using an independent DB session."""

    if job.job_type != JOB_TYPE_RESEARCH:
        raise ValueError("Unsupported background job type")
    payload = job.payload
    async with AsyncSessionLocal() as session:
        run = await session.get(ResearchRunModel, job.research_run_id)
        if run is None or run.user_id != job.user_id:
            raise ValueError("Background research run is unavailable")
        if run.status == COMPLETED and run.output_references:
            return {"research_run_id": run.id, "result": run.output_references}
        run.status = RUNNING
        run.error_message = None
        run.finished_at = None
        await session.commit()

    engine = ResearchWorkflowEngine(session_or_factory=AsyncSessionLocal)
    try:
        state = await engine.execute_research(
            query=str(payload["query"]),
            user_id=job.user_id,
            domain=str(payload.get("domain") or "Epistemology"),
            thread_id=job.id,
            run_id=job.research_run_id,
            depth=str(payload.get("depth") or "standard"),
            include_web=bool(payload.get("include_web", False)),
        )
        result = engine._result_payload(state)
        async with AsyncSessionLocal() as session:
            service = ResearchRunService(session)
            await service.complete_run(job.research_run_id, output_references=result)
            await service.record_event(
                job.research_run_id,
                {"event": "background_research_completed", "status": COMPLETED},
                1,
            )
        return {"research_run_id": job.research_run_id, "result": result}
    except Exception:
        async with AsyncSessionLocal() as session:
            await ResearchRunService(session).fail_run(job.research_run_id, SAFE_FAILURE)
        raise


Executor = Callable[[BackgroundJobModel], Awaitable[dict[str, Any]]]


class BackgroundWorker:
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession] = AsyncSessionLocal,
        executor: Executor = execute_research_job,
        poll_interval: float = 0.25,
        stale_after: timedelta = timedelta(minutes=5),
    ):
        self.session_factory = session_factory
        self.executor = executor
        self.poll_interval = poll_interval
        self.stale_after = stale_after
        self._stop = asyncio.Event()
        self._claim_lock = asyncio.Lock()

    async def recover_stale(self) -> int:
        async with self.session_factory() as session:
            return await BackgroundJobService(session).requeue_stale(self.stale_after)

    async def run_once(self) -> bool:
        async with self._claim_lock, self.session_factory() as session:
            job = await BackgroundJobService(session).claim_next()
        if job is None:
            return False
        started = perf_counter()
        try:
            result = await self.executor(job)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - worker boundary logs only type.
            async with self.session_factory() as session:
                next_status = await BackgroundJobService(session).fail_or_retry(job.id)
            logger.error(
                "background_job_failed",
                job_id=job.id,
                job_type=job.job_type,
                attempt=job.attempts,
                next_status=next_status,
                error_type=type(exc).__name__,
                request_id=job.request_id,
                duration_ms=round((perf_counter() - started) * 1000, 2),
            )
            return True
        async with self.session_factory() as session:
            await BackgroundJobService(session).complete(job.id, result)
        logger.info(
            "background_job_completed",
            job_id=job.id,
            job_type=job.job_type,
            attempt=job.attempts,
            request_id=job.request_id,
            duration_ms=round((perf_counter() - started) * 1000, 2),
        )
        return True

    async def run_forever(self) -> None:
        while not self._stop.is_set():
            processed = await self.run_once()
            if not processed:
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self.poll_interval)
                except TimeoutError:
                    pass

    def stop(self) -> None:
        self._stop.set()
