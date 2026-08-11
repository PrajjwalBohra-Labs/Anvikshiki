"""
Authentication (§27). Single shared API key via the X-API-Key header
-- proportionate to a local-only, single-user deployment (§37
Decisions Made). Constant-time comparison (hmac.compare_digest)
avoids leaking key length/prefix through response timing.
"""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status

from app.config import get_settings
from app.security.audit_log import log_security_event


def require_api_key(x_api_key: str | None = Header(default=None)) -> str:
    settings = get_settings()
    expected = settings.api_key

    if x_api_key is None or not hmac.compare_digest(x_api_key, expected):
        log_security_event("auth_failure", {"reason": "missing_or_invalid_api_key"})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")

    return x_api_key
