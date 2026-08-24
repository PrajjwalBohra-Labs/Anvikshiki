from fastapi import APIRouter
from backend.app.api.v1.conversations import router as conversations_router
from backend.app.api.v1.dialogue import router as dialogue_router
from backend.app.api.v1.research import router as research_router
from backend.app.api.v1.epistemic import router as epistemic_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(conversations_router, prefix="/conversations", tags=["Conversations"])
api_router.include_router(dialogue_router, prefix="/dialogue", tags=["Dialogue"])
api_router.include_router(research_router, prefix="/research", tags=["Research"])
api_router.include_router(epistemic_router, prefix="/epistemic", tags=["Epistemic Memory"])