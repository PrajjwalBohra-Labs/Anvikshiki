from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from pydantic import BaseModel
from backend.app.infrastructure.database.session import get_db
from backend.app.application.use_cases.reasoning_engine import ReasoningEngineService, ReconstructedArgumentResponse
from backend.app.domain.models.enums import SourceType

router = APIRouter(prefix="/reasoning", tags=["Reasoning & Arguments"])

class ReasoningQueryRequest(BaseModel):
    query: str
    source_type: Optional[SourceType] = None

@router.post("/synthesize", response_model=ReconstructedArgumentResponse, status_code=status.HTTP_200_OK)
async def synthesize_argument_endpoint(
    payload: ReasoningQueryRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Synthesizes a formal epistemological argument and evidence map from retrieved passages
    based on the input research query.
    """
    engine_service = ReasoningEngineService(db)
    argument = await engine_service.synthesize_argument(
        query=payload.query,
        source_type=payload.source_type
    )
    return argument