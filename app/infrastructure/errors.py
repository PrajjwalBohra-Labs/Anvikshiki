"""
Error taxonomy (§29 Error Handling). Recoverable errors get retried
or gracefully degraded; non-recoverable errors are logged clearly and
terminate that turn safely -- never as an unhandled exception
reaching the API layer (§4 "Graceful Degradation: one subsystem
failing does not collapse the system").
"""


class RecoverableError(Exception):
    """Transient failure -- retry, fall back, or degrade rather than fail the whole turn."""


class LLMProviderError(RecoverableError):
    """Ollama call failed (after retries, where applicable)."""


class WebSearchError(RecoverableError):
    """Tavily call failed -- caller degrades to local-only evidence."""


class NonRecoverableError(Exception):
    """A genuine internal fault -- log clearly, terminate that turn
    safely, never crash the process."""


class EngineFailureError(NonRecoverableError):
    """An engine raised an unexpected exception. Wraps the original
    for structured logging without leaking a raw traceback to the
    API response."""

    def __init__(self, stage: str, original: Exception):
        self.stage = stage
        self.original = original
        super().__init__(f"{stage} failed: {type(original).__name__}: {original}")
