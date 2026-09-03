from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.infrastructure.ai.local_model_adapter import OllamaLocalAdapter


@pytest.mark.asyncio
async def test_ollama_adapter_generation_success():
    adapter = OllamaLocalAdapter(model_name="test-llama", base_url="http://localhost:11434")
    
    mock_response_data = {"response": "Epistemology is the study of knowledge."}
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        # Use MagicMock for the response object since httpx.Response methods (like json()) are synchronous
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = lambda: None
        
        mock_post.return_value = mock_response

        result = await adapter.generate("Define epistemology.")
        assert result["content"] == "Epistemology is the study of knowledge."
        assert result["model"] == "test-llama"
        mock_post.assert_awaited_once()

@pytest.mark.asyncio
async def test_ollama_adapter_error_handling():
    adapter = OllamaLocalAdapter(model_name="test-llama", base_url="http://localhost:11434", timeout=1.0)
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        import httpx
        mock_post.side_effect = httpx.TimeoutException("Connection timed out")

        with pytest.raises(RuntimeError, match="unavailable or returned an invalid response"):
            await adapter.generate("Test prompt")
