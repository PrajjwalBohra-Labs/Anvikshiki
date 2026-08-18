"""
Application entrypoint. Wires config, logging, the API Gateway
router, security dependencies (§27), and initializes both stores via
a lifespan handler on startup.
"""

import logging
from contextlib import asynccontextmanager

import time

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.config import get_settings
from app.logging_config import configure_logging
from app.persistence.relational_db import init_db
from app.persistence.vector_store import init_vector_store
from app.infrastructure.observability import new_trace_id, record_event, set_current_trace_id
from app.security.auth import require_api_key
from app.security.rate_limiter import rate_limit_dependency

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("anvikshiki")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_vector_store()
    if settings.api_key == "change-me-local-dev-key":
        logger.warning("API_KEY is still the default placeholder -- change it in .env")
    logger.info("stores initialized")
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Log the max upload size for reference
logger.info(f"Max document upload size: {settings.max_document_bytes / (1024*1024):.0f} MB")
app.include_router(
    api_router,
    dependencies=[Depends(require_api_key), Depends(rate_limit_dependency)],
)


@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-Id") or new_trace_id()
    set_current_trace_id(trace_id)
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = (time.monotonic() - start) * 1000
    record_event(
        "http_request", "stage_end", duration_ms=duration_ms,
        path=str(request.url.path), method=request.method, status_code=response.status_code,
    )
    response.headers["X-Trace-Id"] = trace_id
    return response


@app.get("/health")
def health() -> dict:
    logger.info("health check called")
    return {"status": "ok", "service": settings.app_name, "environment": settings.environment}

