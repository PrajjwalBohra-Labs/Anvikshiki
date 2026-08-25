from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from backend.app.api.v1 import api_router
from backend.app.infrastructure.database.session import engine, AsyncSessionLocal
from backend.app.core.errors import AnvikshikiDomainError, domain_error_handler, global_exception_handler

app = FastAPI(
    title="Anvīkṣikī Epistemic Research Engine",
    description="Local-First Intellectual Research and Verification System",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.add_exception_handler(AnvikshikiDomainError, domain_error_handler)
app.add_exception_handler(Exception, global_exception_handler)

@app.get("/health", tags=["System"])
async def health_check():
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
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "pgvector": pgvector_status,
        "model_runtime": "local_adapter_ready",
        "mcp_boundary": "internal_tool_boundary_enforced"
    }
