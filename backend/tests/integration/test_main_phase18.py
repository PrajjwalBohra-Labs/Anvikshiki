import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.core.config import settings

@pytest.mark.asyncio
async def test_health_check_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"{settings.API_V1_STR}/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["project"] == settings.PROJECT_NAME

@pytest.mark.asyncio
async def test_domain_error_exception_handler():
    from fastapi import APIRouter
    from backend.app.core.errors import AnvikshikiDomainError
    
    # Register a temporary route that raises a DomainError
    test_router = APIRouter()
    @test_router.get("/trigger-error")
    async def trigger_error():
        raise AnvikshikiDomainError("Epistemic contradiction detected.", status_code=422)
        
    app.include_router(test_router, prefix="/api/v1")
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/trigger-error")
        
    assert response.status_code == 422
    data = response.json()
    assert data["error"] is True
    assert data["message"] == "Epistemic contradiction detected."