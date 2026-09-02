
import structlog
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

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
    source = SourceModel(**payload.model_dump())
    db.add(source)
    await db.commit()
    await db.refresh(source)
    source_list_cache.invalidate(SOURCE_LIST_CACHE_KEY)
    return source

@router.get("/", response_model=list[SourceResponse])
async def list_sources(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: AuthenticatedPrincipal | None = Depends(get_current_user),  # noqa: B008
):
    del current_user  # Authentication is enforced; source metadata is globally shared.
    try:
        cached = source_list_cache.get(SOURCE_LIST_CACHE_KEY)
    except Exception as exc:  # noqa: BLE001 - cache failure must fail open.
        logger.warning("cache_fallback", cache_name="source_metadata", error_type=type(exc).__name__)
        cached = None
    if cached is not None:
        return cached
    result = await db.execute(select(SourceModel).order_by(SourceModel.id))
    sources = [SourceResponse.model_validate(source).model_dump() for source in result.scalars().all()]
    try:
        source_list_cache.set(SOURCE_LIST_CACHE_KEY, sources)
    except Exception as exc:  # noqa: BLE001 - cache failure must fail open.
        logger.warning("cache_fallback", cache_name="source_metadata", error_type=type(exc).__name__)
    return sources
