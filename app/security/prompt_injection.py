"""
Prompt injection protection (§27). A heuristic scanner over both user
input and retrieved document content -- documents are an injection
vector too, since their text is inserted into prompts verbatim
(§22 Retrieved Knowledge layer). This is pattern-matching, not a
guarantee; flagged content gets logged (audit trail) and redacted
rather than silently trusted.
"""

from __future__ import annotations

import re

from app.security.audit_log import log_security_event

_INJECTION_PATTERNS = [
    re.compile(r"ignore (all |any )?(previous|prior|above) instructions", re.IGNORECASE),
    re.compile(r"disregard (all |any )?(previous|prior|above)", re.IGNORECASE),
    re.compile(r"you are now", re.IGNORECASE),
    re.compile(r"system\s*:", re.IGNORECASE),
    re.compile(r"new instructions?\s*:", re.IGNORECASE),
    re.compile(r"reveal (your |the )?(system )?prompt", re.IGNORECASE),
]


def detect_injection(text: str) -> list[str]:
    return [pattern.pattern for pattern in _INJECTION_PATTERNS if pattern.search(text)]


def sanitize_against_injection(text: str, source: str) -> str:
    matches = detect_injection(text)
    if not matches:
        return text

    log_security_event("prompt_injection_detected", {"source": source, "patterns": matches})
    cleaned = text
    for pattern in _INJECTION_PATTERNS:
        cleaned = pattern.sub("[redacted]", cleaned)
    return cleaned
