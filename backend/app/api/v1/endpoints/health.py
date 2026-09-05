from fastapi import APIRouter, status
from pydantic import BaseModel
from backend.app.core.config import settings
from backend.app.core.runtime_health import probe_runtime
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter()

class HealthResponse(BaseModel):
    status: str
    project: str
    environment: str
    database: str
    pgvector: str
    database_schema: str
    readiness: str

@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def check_health():
    logger.debug("Health check requested")
    runtime = await probe_runtime()
    return HealthResponse(
        status=runtime["status"],
        project=settings.PROJECT_NAME,
        environment=settings.ENV,
        database=runtime["database"],
        pgvector=runtime["pgvector"],
        database_schema=runtime["database_schema"],
        readiness=runtime["readiness"],
    )
