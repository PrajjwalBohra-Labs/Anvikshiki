from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.app.core.config import settings
from backend.app.core.errors import AnvikshikiDomainError
from backend.app.api.v1.endpoints import sources, documents, search, reasoning, chat
import structlog

logger = structlog.get_logger(__name__)

def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
        openapi_url=f"{settings.API_V1_STR}/openapi.json"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.FRONTEND_URL, "http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AnvikshikiDomainError)
    async def anvikshiki_exception_handler(request: Request, exc: AnvikshikiDomainError):
        logger.error("Domain error encountered", path=request.url.path, error=exc.message, status_code=exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "message": exc.message,
                "status_code": exc.status_code
            }
        )

    @app.get(f"{settings.API_V1_STR}/health", tags=["System"])
    async def health_check():
        return {
            "status": "healthy",
            "project": settings.PROJECT_NAME,
            "environment": settings.ENV,
            "runtime_profile": settings.RUNTIME_PROFILE
        }

    # Register V1 Routers
    app.include_router(sources.router, prefix=settings.API_V1_STR)
    app.include_router(documents.router, prefix=settings.API_V1_STR)
    app.include_router(search.router, prefix=settings.API_V1_STR)
    app.include_router(reasoning.router, prefix=settings.API_V1_STR)
    app.include_router(chat.router, prefix=settings.API_V1_STR)

    return app

app = create_application()