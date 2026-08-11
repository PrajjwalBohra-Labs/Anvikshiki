"""
Session Engine (§6; represents one interaction session, §11). Thin
wrapper over the sessions table. Returns whether a new session was
actually created, so callers can decide whether a "session started"
notification is warranted.
"""

from __future__ import annotations

from app.persistence import relational_db


def get_or_create_session(session_id: str | None = None, user_id: str | None = None) -> tuple[str, bool]:
    if session_id is not None:
        existing = relational_db.get_session(session_id)
        if existing is not None:
            return session_id, False
    return relational_db.create_session(user_id=user_id), True
