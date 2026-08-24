from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.v1 import api_router
from backend.app.infrastructure.database.session import engine, Base

app = FastAPI(
    title="Anvīkṣikī API",
    description="Advanced Intellectual Research and Evidence Verification Engine",
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
    return {
        "status": "healthy",
        "system": "Anvikshiki Epistemic Engine",
        "database": "connected",
        "security": "MCP boundary enforced"
    }