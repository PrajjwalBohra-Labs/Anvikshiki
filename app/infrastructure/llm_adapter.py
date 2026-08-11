"""
LLM Adapter (§20). Nothing outside this module ever calls a provider
directly. Ollama is the one real implementation (§37).

generate()/embed() retry on transient failures (§29) since they'"'"'re
atomic single-shot calls; stream() deliberately does NOT retry --
retrying a partially-consumed generator would silently duplicate or
drop output, which is worse than failing cleanly. Both raise
LLMProviderError on exhaustion, which callers (e.g. retrieval, Step
18) can catch to degrade gracefully instead of crashing.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Iterator

import httpx

from app.config import Settings, get_settings
from app.infrastructure.errors import LLMProviderError
from app.infrastructure.observability import record_event, trace_stage
from app.infrastructure.retry import retry_with_backoff

_TRANSIENT_EXCEPTIONS = (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError)


class LLMAdapter(ABC):
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str: ...

    @abstractmethod
    def stream(self, prompt: str, **kwargs) -> Iterator[str]: ...

    @abstractmethod
    def embed(self, text: str) -> list[float]: ...

    @abstractmethod
    def summarize(self, text: str, **kwargs) -> str: ...


class OllamaAdapter(LLMAdapter):
    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None):
        self._settings = settings or get_settings()
        self._client = client or httpx.Client(
            base_url=self._settings.ollama_base_url, timeout=60.0
        )

    def generate(self, prompt: str, **kwargs) -> str:
        model = kwargs.get("model", self._settings.ollama_generation_model)
        with trace_stage("llm_generate", model=model):
            def _call():
                response = self._client.post(
                    "/api/generate", json={"model": model, "prompt": prompt, "stream": False},
                )
                response.raise_for_status()
                return response.json()

            try:
                data = retry_with_backoff(_call, exceptions=_TRANSIENT_EXCEPTIONS)
            except _TRANSIENT_EXCEPTIONS as exc:
                raise LLMProviderError(f"Ollama generate call failed after retries: {exc}") from exc

            record_event(
                "llm_generate", "metric",
                prompt_tokens=data.get("prompt_eval_count"), completion_tokens=data.get("eval_count"),
            )
            return data["response"]

    def stream(self, prompt: str, **kwargs) -> Iterator[str]:
        model = kwargs.get("model", self._settings.ollama_generation_model)
        with trace_stage("llm_stream", model=model):
            try:
                with self._client.stream(
                    "POST", "/api/generate", json={"model": model, "prompt": prompt, "stream": True},
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line:
                            continue
                        chunk = json.loads(line)
                        if "response" in chunk:
                            yield chunk["response"]
                        if chunk.get("done"):
                            record_event(
                                "llm_stream", "metric",
                                prompt_tokens=chunk.get("prompt_eval_count"),
                                completion_tokens=chunk.get("eval_count"),
                            )
                            break
            except _TRANSIENT_EXCEPTIONS as exc:
                raise LLMProviderError(f"Ollama stream call failed: {exc}") from exc

    def embed(self, text: str) -> list[float]:
        with trace_stage("llm_embed"):
            def _call():
                response = self._client.post(
                    "/api/embeddings",
                    json={"model": self._settings.ollama_embedding_model, "prompt": text},
                )
                response.raise_for_status()
                return response.json()["embedding"]

            try:
                return retry_with_backoff(_call, exceptions=_TRANSIENT_EXCEPTIONS)
            except _TRANSIENT_EXCEPTIONS as exc:
                raise LLMProviderError(f"Ollama embed call failed after retries: {exc}") from exc

    def summarize(self, text: str, **kwargs) -> str:
        max_words = kwargs.pop("max_words", 100)
        prompt = (
            f"Summarize the following text in at most {max_words} words. "
            f"Be concise and preserve key facts.\n\nTEXT:\n{text}\n\nSUMMARY:"
        )
        return self.generate(prompt, **kwargs)


class _UnimplementedAdapter(LLMAdapter):
    def __init__(self, provider_name: str):
        self._provider_name = provider_name

    def _unimplemented(self):
        raise NotImplementedError(
            f"{self._provider_name} adapter is not implemented in this project "
            "(Ollama is the only real provider -- see §37 Decisions Made)."
        )

    def generate(self, prompt: str, **kwargs) -> str:
        self._unimplemented()

    def stream(self, prompt: str, **kwargs) -> Iterator[str]:
        self._unimplemented()
        yield  # pragma: no cover

    def embed(self, text: str) -> list[float]:
        self._unimplemented()

    def summarize(self, text: str, **kwargs) -> str:
        self._unimplemented()


class OpenAIAdapter(_UnimplementedAdapter):
    def __init__(self):
        super().__init__("OpenAI")


class AnthropicAdapter(_UnimplementedAdapter):
    def __init__(self):
        super().__init__("Anthropic")


class GeminiAdapter(_UnimplementedAdapter):
    def __init__(self):
        super().__init__("Gemini")


_ADAPTERS = {
    "ollama": OllamaAdapter,
    "openai": OpenAIAdapter,
    "anthropic": AnthropicAdapter,
    "gemini": GeminiAdapter,
}


def get_llm_adapter(settings: Settings | None = None) -> LLMAdapter:
    settings = settings or get_settings()
    provider = settings.llm_provider.lower()
    if provider not in _ADAPTERS:
        raise ValueError(f"Unknown LLM provider: {provider!r}. Expected one of {list(_ADAPTERS)}")
    adapter_cls = _ADAPTERS[provider]
    return adapter_cls(settings) if provider == "ollama" else adapter_cls()
