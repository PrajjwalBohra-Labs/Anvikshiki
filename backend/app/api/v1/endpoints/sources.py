from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from backend.app.infrastructure.database.session import get_db
from backend.app.infrastructure.database.models import SourceModel
from backend.app.domain.models.enums import SourceType
from backend.app.api.dependencies import AuthenticatedPrincipal, get_current_user

router = APIRouter(prefix="/sources", tags=["Sources"])

class SourceCreate(BaseModel):
    title: str
    author: Optional[str] = None
    historical_era: Optional[str] = None
    original_language: Optional[str] = None
    source_type: SourceType = SourceType.UNVERIFIED
    reference_url: Optional[str] = None

class SourceResponse(SourceCreate):
    id: str
    model_config = ConfigDict(from_attributes=True)

@router.post("/", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    payload: SourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedPrincipal | None = Depends(get_current_user),
):
    source = SourceModel(**payload.model_dump())
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source

@router.get("/", response_model=List[SourceResponse])
async def list_sources(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SourceModel))
    return result.scalars().all()
