"""
Input sanitization (§27). Strips control characters and enforces a
length cap on free-text input at the API boundary, on top of
Pydantic'"'"'s type validation.
"""

from __future__ import annotations

import re

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
MAX_QUERY_LENGTH = 4000


class InputValidationError(Exception):
    pass


def sanitize_text(text: str, max_length: int = MAX_QUERY_LENGTH) -> str:
    cleaned = _CONTROL_CHAR_RE.sub("", text)
    if len(cleaned) > max_length:
        raise InputValidationError(f"Input exceeds maximum length of {max_length} characters")
    return cleaned
