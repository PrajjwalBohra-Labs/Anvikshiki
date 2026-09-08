
import structlog
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from backend.app.infrastructure.database.session import get_db
from backend.app.infrastructure.database.models import SourceModel
from backend.app.domain.models.enums import SourceType
from backend.app.api.dependencies import AuthenticatedPrincipal, get_current_user
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.cache.in_memory import InMemoryTTLCache
from backend.app.infrastructure.database.models import SourceModel
from backend.app.infrastructure.database.session import get_db

router = APIRouter(prefix="/sources", tags=["Sources"])
logger = structlog.get_logger(__name__)
SOURCE_LIST_CACHE_KEY = "sources:list:v1"
source_list_cache = InMemoryTTLCache(ttl_seconds=30.0)

class SourceCreate(BaseModel):
    title: str
    author: str | None = None
    historical_era: str | None = None
    original_language: str | None = None
    source_type: SourceType = SourceType.UNVERIFIED
    reference_url: str | None = None

class SourceResponse(SourceCreate):
    id: str
    model_config = ConfigDict(from_attributes=True)

@router.post("/", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    payload: SourceCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: AuthenticatedPrincipal | None = Depends(get_current_user),  # noqa: B008
):
    source = SourceModel(**payload.model_dump(), user_id=current_user.user_id if current_user else None)
    db.add(source)
    await db.commit()
    await db.refresh(source)
    source_list_cache.clear()
    return source

@router.get("/", response_model=List[SourceResponse])
async def list_sources(
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedPrincipal | None = Depends(get_current_user),
):
    cache_key = f"{SOURCE_LIST_CACHE_KEY}:{current_user.user_id if current_user else 'public'}"
    try:
        cached = source_list_cache.get(cache_key)
        if cached is not None:
            return cached
    except Exception:
        # Cache is an optimization; never turn an unavailable cache into an
        # unavailable source library, and never log cache internals.
        logger.warning("cache_fallback", operation="read")

    stmt = select(SourceModel)
    if current_user is not None:
        stmt = stmt.where(
            or_(SourceModel.user_id == current_user.user_id, SourceModel.user_id.is_(None))
        )
    result = await db.execute(stmt)
    payload = [SourceResponse.model_validate(source).model_dump() for source in result.scalars().all()]
    try:
        source_list_cache.set(cache_key, payload)
    except Exception:
        logger.warning("cache_fallback", operation="write")
    return payload
