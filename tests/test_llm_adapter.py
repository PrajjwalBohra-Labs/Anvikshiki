import json

import httpx
import pytest

from app.config import Settings
from app.infrastructure.llm_adapter import (
    GeminiAdapter,
    OllamaAdapter,
    get_llm_adapter,
)


def _mock_settings() -> Settings:
    return Settings(
        llm_provider="ollama",
        ollama_base_url="http://fake-ollama",
        ollama_generation_model="test-model",
        ollama_embedding_model="test-embed-model",
    )


def test_generate_calls_ollama_api_and_parses_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/generate"
        body = json.loads(request.content)
        assert body["model"] == "test-model"
        assert body["stream"] is False
        return httpx.Response(200, json={"response": "hello from ollama"})

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://fake-ollama")
    adapter = OllamaAdapter(settings=_mock_settings(), client=client)

    assert adapter.generate("say hi") == "hello from ollama"


def test_embed_calls_ollama_embeddings_endpoint():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/embeddings"
        return httpx.Response(200, json={"embedding": [0.1, 0.2, 0.3]})

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://fake-ollama")
    adapter = OllamaAdapter(settings=_mock_settings(), client=client)

    assert adapter.embed("some text") == [0.1, 0.2, 0.3]


def test_stream_yields_tokens_in_order():
    lines = [
        json.dumps({"response": "Hel"}) + "\n",
        json.dumps({"response": "lo"}) + "\n",
        json.dumps({"response": "", "done": True}) + "\n",
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content="".join(lines))

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://fake-ollama")
    adapter = OllamaAdapter(settings=_mock_settings(), client=client)

    assert list(adapter.stream("say hi")) == ["Hel", "lo", ""]


def test_summarize_wraps_generate_with_summary_prompt():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["prompt"] = json.loads(request.content)["prompt"]
        return httpx.Response(200, json={"response": "a short summary"})

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://fake-ollama")
    adapter = OllamaAdapter(settings=_mock_settings(), client=client)

    result = adapter.summarize("a very long piece of text", max_words=20)
    assert result == "a short summary"
    assert "SUMMARY" in captured["prompt"]


def test_unimplemented_providers_raise_not_implemented():
    with pytest.raises(NotImplementedError):
        GeminiAdapter().generate("hi")


def test_get_llm_adapter_returns_ollama_by_default():
    adapter = get_llm_adapter(_mock_settings())
    assert isinstance(adapter, OllamaAdapter)


def test_get_llm_adapter_rejects_unknown_provider():
    settings = _mock_settings()
    settings.llm_provider = "not-a-real-provider"
    with pytest.raises(ValueError):
        get_llm_adapter(settings)
