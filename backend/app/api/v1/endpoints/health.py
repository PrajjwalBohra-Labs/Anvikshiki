from fastapi import APIRouter, status
from pydantic import BaseModel
from backend.app.core.config import settings
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter()

class HealthResponse(BaseModel):
    status: str
    project: str
    environment: str

@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def check_health():
    logger.debug("Health check requested")
    return HealthResponse(
        status="healthy",
        project=settings.PROJECT_NAME,
        environment=settings.ENV
    )