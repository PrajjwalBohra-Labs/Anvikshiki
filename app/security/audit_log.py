"""
Audit logging (§27). Structured, append-only JSON lines for
security-relevant events -- separate from the general application
log (Step 1) so audit review doesn'"'"'t require sifting through
routine request logs.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings

_audit_logger = logging.getLogger("anvikshiki.audit")


def _ensure_handler() -> None:
    if _audit_logger.handlers:
        return
    settings = get_settings()
    audit_path = Path(settings.file_store_path).parent / "audit.log"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(audit_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    _audit_logger.addHandler(handler)
    _audit_logger.setLevel(logging.INFO)
    _audit_logger.propagate = False


def log_security_event(event_type: str, details: dict) -> None:
    _ensure_handler()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "details": details,
    }
    _audit_logger.info(json.dumps(entry))
