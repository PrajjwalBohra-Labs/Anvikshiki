import asyncio
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import UUID, uuid4

import structlog
<<<<<<< HEAD

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
=======
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
>>>>>>> origin/main

from backend.app.api.v1 import api_router
from backend.app.application.background.worker import BackgroundWorker
from backend.app.core.config import settings
from backend.app.core.errors import (
    AnvikshikiDomainError,
    domain_error_handler,
    global_exception_handler,
)
from backend.app.core.logging import setup_logging
<<<<<<< HEAD
from backend.app.core.runtime_health import probe_runtime
from backend.app.infrastructure.database.session import AsyncSessionLocal
=======
from backend.app.infrastructure.database.session import AsyncSessionLocal, engine
>>>>>>> origin/main

setup_logging()
logger = structlog.get_logger(__name__)

background_worker = BackgroundWorker()


@asynccontextmanager
async def lifespan(_app: FastAPI):
<<<<<<< HEAD
    """Require database recovery to succeed before serving the application."""
=======
>>>>>>> origin/main
    await background_worker.recover_stale()
    worker_task = asyncio.create_task(background_worker.run_forever())
    try:
        yield
    finally:
        background_worker.stop()
        await worker_task
<<<<<<< HEAD
=======

>>>>>>> origin/main

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
<<<<<<< HEAD
async def security_and_observability_middleware(request: Request, call_next):
=======
async def observability_middleware(request: Request, call_next):
>>>>>>> origin/main
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
<<<<<<< HEAD
    duration_ms = round((perf_counter() - started) * 1000, 2)
=======
>>>>>>> origin/main
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
<<<<<<< HEAD
        duration_ms=duration_ms,
=======
        duration_ms=round((perf_counter() - started) * 1000, 2),
>>>>>>> origin/main
    )
    return response

app.include_router(api_router)
app.add_exception_handler(AnvikshikiDomainError, domain_error_handler)
app.add_exception_handler(Exception, global_exception_handler)

@app.get("/health", tags=["System"])
async def health_check():
<<<<<<< HEAD
    result = await probe_runtime(AsyncSessionLocal)
    if result["status"] == "degraded":
        logger.warning("health_check_degraded")
    return result
=======
    """
    Actively checks PostgreSQL database connectivity and pgvector readiness.
    """
    db_status = "unhealthy"
    pgvector_status = "unavailable"
    
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            db_status = "connected"
            if engine.dialect.name != "postgresql":
                pgvector_status = "unavailable_in_test_profile"
            else:
                await session.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
                extension = await session.execute(
                    text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
                )
                pgvector_status = "available" if extension.scalar_one_or_none() else "unavailable"
    except Exception as exc:  # noqa: BLE001 - health is a failure boundary.
        logger.warning("health_check_failed", error_type=type(exc).__name__)
        db_status = "unavailable"
>>>>>>> origin/main


@app.get("/ready", tags=["System"])
async def readiness_check():
    """Distinguish a listening process from a database-ready application."""
    result = await probe_runtime(AsyncSessionLocal)
    code = 200 if result["readiness"] == "ready" else 503
    return JSONResponse(status_code=code, content=result)
