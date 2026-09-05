
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import AuthenticatedPrincipal, get_current_user
from backend.app.application.use_cases.reasoning_engine import (
    ReasoningEngineService,
    ReconstructedArgumentResponse,
)
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.database.session import get_db

router = APIRouter(prefix="/reasoning", tags=["Reasoning & Arguments"])


class ReasoningQueryRequest(BaseModel):
    query: str
    source_type: SourceType | None = None


@router.post("/synthesize", response_model=ReconstructedArgumentResponse, status_code=status.HTTP_200_OK)
async def synthesize_argument_endpoint(
    payload: ReasoningQueryRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: AuthenticatedPrincipal | None = Depends(get_current_user),  # noqa: B008
):
    """
    Synthesizes a formal epistemological argument and evidence map from retrieved passages
    based on the input research query.
    """
    del current_user
    engine_service = ReasoningEngineService(db)
    argument = await engine_service.synthesize_argument(
        query=payload.query,
        source_type=payload.source_type
    )
    return argument
