from fastapi import APIRouter, status
from pydantic import BaseModel
import httpx
from backend.app.core.config import settings

router = APIRouter()

class HealthResponse(BaseModel):
    status: str
    project: str
    environment: str
    ollama_connected: bool

@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def check_health():
    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                ollama_ok = True
    except Exception:
        ollama_ok = False

    return HealthResponse(
        status="healthy",
        project=settings.PROJECT_NAME,
        environment=settings.ENV,
        ollama_connected=ollama_ok
    )
