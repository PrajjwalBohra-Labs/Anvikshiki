"""Authenticated API for durable background research jobs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import AuthenticatedPrincipal, get_current_user
from backend.app.api.v1.schemas.dtos import (
    BackgroundJobResponseDTO,
    BackgroundResearchJobRequestDTO,
)
from backend.app.application.background.worker import BackgroundJobService
from backend.app.infrastructure.database.models import BackgroundJobModel
from backend.app.infrastructure.database.session import get_db

router = APIRouter(prefix="/research/jobs", tags=["Background Jobs"])


def _response(job) -> BackgroundJobResponseDTO:
    result = job.result_payload
    return BackgroundJobResponseDTO(
        job_id=job.id,
        job_type=job.job_type,
        research_run_id=job.research_run_id,
        status=job.status,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        result=result,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


@router.post("", response_model=BackgroundJobResponseDTO, status_code=status.HTTP_202_ACCEPTED)
async def create_background_research_job(
    payload: BackgroundResearchJobRequestDTO,
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: AuthenticatedPrincipal | None = Depends(get_current_user),  # noqa: B008
):
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required.")
    job, _created = await BackgroundJobService(db).create_research_job(
        user_id=current_user.user_id,
        query=payload.query,
        domain=payload.domain,
        depth=payload.depth,
        idempotency_key=payload.idempotency_key,
        include_web=payload.include_web,
        request_id=getattr(request.state, "request_id", None),
    )
    return _response(job)


@router.get("", response_model=list[BackgroundJobResponseDTO])
async def list_background_research_jobs(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: AuthenticatedPrincipal | None = Depends(get_current_user),  # noqa: B008
):
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required.")
    result = await db.execute(
        select(BackgroundJobModel)
        .where(BackgroundJobModel.user_id == current_user.user_id)
        .order_by(BackgroundJobModel.created_at.desc(), BackgroundJobModel.id.desc())
    )
    return [_response(job) for job in result.scalars().all()]


@router.get("/{job_id}", response_model=BackgroundJobResponseDTO)
async def get_background_research_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: AuthenticatedPrincipal | None = Depends(get_current_user),  # noqa: B008
):
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required.")
    job = await BackgroundJobService(db).get_owned_job(job_id, current_user.user_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Background job not found.")
    return _response(job)


@router.post("/{job_id}/cancel", response_model=BackgroundJobResponseDTO)
async def cancel_background_research_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: AuthenticatedPrincipal | None = Depends(get_current_user),  # noqa: B008
):
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required.")
    job = await BackgroundJobService(db).cancel_owned_job(job_id, current_user.user_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Background job not found.")
    return _response(job)
