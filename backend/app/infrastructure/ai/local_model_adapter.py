from abc import ABC, abstractmethod
from typing import Dict, Any, AsyncGenerator, Optional
import httpx
import json
import structlog
from backend.app.config.settings import config
from backend.app.core.config import settings as runtime_settings

logger = structlog.get_logger(__name__)

class BaseModelAdapter(ABC):
    """Abstract contract for all local/remote LLM adapters."""
    def __init__(self, model_name: str = "default-model"):
        self.model_name = model_name

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        pass

class OllamaLocalAdapter(BaseModelAdapter):
    """
    Production adapter for a local Ollama runtime.

    Ollama failures are surfaced to the caller; production synthesis never
    substitutes fabricated or deterministic output.
    """
    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 45.0
    ):
        selected_model = model_name or runtime_settings.OLLAMA_MODEL or config.llm.model_name
        super().__init__(model_name=selected_model)
        self.base_url = base_url or runtime_settings.OLLAMA_BASE_URL or config.llm.base_url
        self.timeout = timeout

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "system": system_prompt or "You are Anvīkṣikī, an epistemic research assistant.",
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": temperature}
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                content = data.get("response")
                if not content:
                    raise RuntimeError("Ollama returned an empty response.")
                return {"content": content, "model": self.model_name}
        except Exception as e:
            logger.error("Local Ollama generation failed", error=str(e), model=self.model_name)
            raise RuntimeError(
                f"Ollama model '{self.model_name}' is unavailable or returned an invalid response."
            ) from e

    async def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "system": system_prompt or "You are Anvīkṣikī, an epistemic research assistant.",
            "stream": True,
            "options": {"num_predict": max_tokens, "temperature": temperature}
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, json=payload) as resp:
                    async for line in resp.aiter_lines():
                        if line:
                            data = json.loads(line)
                            yield data.get("response", "")
        except Exception as e:
            logger.error("Local Ollama streaming failed", error=str(e), model=self.model_name)
            raise RuntimeError(
                f"Ollama model '{self.model_name}' is unavailable for streaming."
            ) from e
