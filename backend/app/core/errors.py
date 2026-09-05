<<<<<<< HEAD
import structlog
=======
﻿import structlog
>>>>>>> origin/main
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
<<<<<<< HEAD
    # 503 messages are deliberately limited to safe service-state guidance
    # (for example, a local model is not provisioned).  Other 5xx responses
    # remain opaque so database/driver internals never cross the API boundary.
    message = (
        exc.message
        if exc.status_code < 500 or exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        else "An internal server error occurred."
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": message, "type": "domain_error"},
=======
    message = exc.message if exc.status_code < 500 else "An internal server error occurred."
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": message, "type": "domain_error"}
>>>>>>> origin/main
    )


async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_exception",
        path_template=getattr(request.scope.get("route"), "path", "unmatched"),
        error_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
<<<<<<< HEAD
        content={"error": "An internal server error occurred.", "type": "internal_error"},
=======
        content={"error": "An internal server error occurred.", "type": "internal_error"}
>>>>>>> origin/main
    )
