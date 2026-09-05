import asyncio
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import UUID, uuid4

import structlog

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.v1 import api_router
from backend.app.application.background.worker import BackgroundWorker
from backend.app.core.config import settings
from backend.app.core.errors import (
    AnvikshikiDomainError,
    domain_error_handler,
    global_exception_handler,
)
from backend.app.core.logging import setup_logging
from backend.app.core.runtime_health import probe_runtime
from backend.app.infrastructure.database.session import AsyncSessionLocal

setup_logging()
logger = structlog.get_logger(__name__)

background_worker = BackgroundWorker()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Require database recovery to succeed before serving the application."""
    await background_worker.recover_stale()
    worker_task = asyncio.create_task(background_worker.run_forever())
    try:
        yield
    finally:
        background_worker.stop()
        await worker_task

app = FastAPI(
    title="Anvīkṣikī Epistemic Research Engine",
    description="Local-First Intellectual Research and Verification System",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # Vite's host=true development server is reachable through either local
    # hostname. These are explicit local origins, not a wildcard.
    allow_origins=list(dict.fromkeys([settings.FRONTEND_URL, "http://127.0.0.1:5173"])),
    # In development, permit the RFC1918 address of the machine serving Vite
    # without baking a particular LAN address into the application. Credentials
    # remain enabled and the regex is restricted to the Vite port/private hosts.
    allow_origin_regex=(
        r"^http://(?:localhost|127\.0\.0\.1|10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2}):5173$"
        if settings.ENV.lower() in {"development", "dev", "local"}
        else None
    ),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type", "Last-Event-ID"],
)


@app.middleware("http")
async def security_and_observability_middleware(request: Request, call_next):
    request_id = uuid4().hex
    incoming_request_id = request.headers.get("X-Request-ID")
    if incoming_request_id:
        try:
            request_id = UUID(incoming_request_id).hex
        except ValueError:
            logger.warning("invalid_request_id", request_id_present=True)
    request.state.request_id = request_id
    started = perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.error(
            "http_request_failed",
            request_id=request_id,
            method=request.method,
            path_template=getattr(request.scope.get("route"), "path", "unmatched"),
            error_type=type(exc).__name__,
        )
        raise
    duration_ms = round((perf_counter() - started) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path.startswith("/api/") or request.url.path == "/health":
        response.headers["Cache-Control"] = "no-store"
    logger.info(
        "http_request",
        request_id=request_id,
        method=request.method,
        path_template=getattr(request.scope.get("route"), "path", "unmatched"),
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    return response

app.include_router(api_router)
app.add_exception_handler(AnvikshikiDomainError, domain_error_handler)
app.add_exception_handler(Exception, global_exception_handler)

@app.get("/health", tags=["System"])
async def health_check():
    result = await probe_runtime(AsyncSessionLocal)
    if result["status"] == "degraded":
        logger.warning("health_check_degraded")
    return result


@app.get("/ready", tags=["System"])
async def readiness_check():
    """Distinguish a listening process from a database-ready application."""
    result = await probe_runtime(AsyncSessionLocal)
    code = 200 if result["readiness"] == "ready" else 503
    return JSONResponse(status_code=code, content=result)
