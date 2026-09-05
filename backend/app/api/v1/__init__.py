from fastapi import APIRouter
from backend.app.api.v1.conversations import router as conversations_router
from backend.app.api.v1.dialogue import router as dialogue_router
from backend.app.api.v1.research import router as research_router
from backend.app.api.v1.epistemic import router as epistemic_router
from backend.app.api.v1.endpoints.health import router as health_router
from backend.app.api.v1.endpoints.documents import router as documents_router
from backend.app.api.v1.endpoints.reasoning import router as reasoning_router
from backend.app.api.v1.endpoints.search import router as search_router
from backend.app.api.v1.endpoints.sources import router as sources_router
from backend.app.api.v1.endpoints.chat import router as chat_router
from backend.app.api.v1.endpoints.web import router as web_router
from backend.app.api.v1.endpoints.users import router as users_router
from backend.app.api.v1.endpoints.auth import router as auth_router
from backend.app.api.v1.endpoints.notebooks import router as notebooks_router
from backend.app.api.v1.background_jobs import router as background_jobs_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(conversations_router, prefix="/conversations", tags=["Conversations"])
api_router.include_router(dialogue_router, prefix="/dialogue", tags=["Dialogue"])
api_router.include_router(research_router, prefix="/research", tags=["Research"])
api_router.include_router(epistemic_router, prefix="/epistemic", tags=["Epistemic Memory"])
api_router.include_router(health_router, tags=["System"])
api_router.include_router(documents_router)
api_router.include_router(reasoning_router)
api_router.include_router(search_router)
api_router.include_router(sources_router)
api_router.include_router(chat_router)
api_router.include_router(web_router)
api_router.include_router(users_router)
api_router.include_router(auth_router)
api_router.include_router(notebooks_router)
api_router.include_router(background_jobs_router)
