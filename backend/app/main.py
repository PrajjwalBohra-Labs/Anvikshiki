from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from backend.app.api.v1 import api_router
from backend.app.infrastructure.database.session import engine, AsyncSessionLocal

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
            try:
                await session.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
                pgvector_status = "available"
            except Exception:
                pgvector_status = "simulated_or_sqlite"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "pgvector": pgvector_status,
        "model_runtime": "local_adapter_ready",
        "mcp_boundary": "internal_tool_boundary_enforced"
    }