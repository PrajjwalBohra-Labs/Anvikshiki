import structlog
from fastapi import Request, status
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)


class AnvikshikiDomainError(Exception):
    """Base class for domain-specific exceptions."""

    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


async def domain_error_handler(request: Request, exc: AnvikshikiDomainError):
    logger.warning(
        "domain_error",
        path_template=getattr(request.scope.get("route"), "path", "unmatched"),
        status_code=exc.status_code,
        error_type=type(exc).__name__,
    )
    message = exc.message if exc.status_code < 500 else "An internal server error occurred."
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": message, "type": "domain_error"},
    )


async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_exception",
        path_template=getattr(request.scope.get("route"), "path", "unmatched"),
        error_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "An internal server error occurred.", "type": "internal_error"},
    )
