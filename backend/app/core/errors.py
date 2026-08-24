from fastapi import Request, status
from fastapi.responses import JSONResponse
import structlog

logger = structlog.get_logger(__name__)

class AnvikshikiDomainError(Exception):
    """Base class for domain-specific exceptions."""
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

async def domain_error_handler(request: Request, exc: AnvikshikiDomainError):
    logger.warning("Domain error", path=request.url.path, error=exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "type": "domain_error"}
    )

async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", path=request.url.path, error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "An internal server error occurred.", "type": "internal_error"}
    )