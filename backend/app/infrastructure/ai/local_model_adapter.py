import abc
import httpx
import structlog
from typing import AsyncGenerator, Dict, Any, Optional

logger = structlog.get_logger(__name__)

class BaseModelAdapter(abc.ABC):
    """Generic interface for local language model adapters, keeping AI logic outside domain models."""
    
    @abc.abstractmethod
    async def generate(self, prompt: str, options: Optional[Dict[str, Any]] = None) -> str:
        pass

    @abc.abstractmethod
    async def stream_generate(self, prompt: str, options: Optional[Dict[str, Any]] = None) -> AsyncGenerator[str, None]:
        pass


class OllamaLocalAdapter(BaseModelAdapter):
    """
    Ollama local model adapter supporting streaming, timeout, cancellation, 
    error handling, and model identity tracking.
    """
    def __init__(self, model_name: str = "llama3", base_url: str = "http://localhost:11434", timeout_seconds: float = 30.0):
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_seconds

    async def generate(self, prompt: str, options: Optional[Dict[str, Any]] = None) -> str:
        endpoint = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": options or {}
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(endpoint, json=payload)
                response.raise_for_status()
                data = response.json()
                logger.info("Ollama generation successful", model=self.model_name)
                return data.get("response", "")
        except httpx.TimeoutException as te:
            logger.error("Ollama request timed out", model=self.model_name, error=str(te))
            raise TimeoutError(f"Local model request timed out after {self.timeout} seconds.") from te
        except httpx.HTTPStatusError as hse:
            logger.error("Ollama HTTP error", status_code=hse.response.status_code, error=str(hse))
            raise RuntimeError(f"Local model error [{hse.response.status_code}]: {hse.response.text}") from hse
        except Exception as e:
            logger.exception("Unexpected error communicating with Ollama", error=str(e))
            raise RuntimeError(f"Local model connection failure: {str(e)}") from e

    async def stream_generate(self, prompt: str, options: Optional[Dict[str, Any]] = None) -> AsyncGenerator[str, None]:
        endpoint = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": True,
            "options": options or {}
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", endpoint, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line:
                            import json
                            chunk = json.loads(line)
                            token = chunk.get("response", "")
                            if token:
                                yield token
        except httpx.TimeoutException as te:
            logger.error("Ollama streaming timed out", model=self.model_name)
            raise TimeoutError(f"Local model streaming timed out after {self.timeout} seconds.") from te
        except Exception as e:
            logger.exception("Unexpected error during Ollama stream", error=str(e))
            raise RuntimeError(f"Local model streaming failure: {str(e)}") from e