from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings
from backend.app.core.logging import setup_logging
from backend.app.core.errors import AnvikshikiDomainError, domain_error_handler, global_exception_handler
from backend.app.api.v1.router import api_router

setup_logging()

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        debug=settings.DEBUG,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(AnvikshikiDomainError, domain_error_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    app.include_router(api_router, prefix=settings.API_V1_STR)
    return app

app = create_app()