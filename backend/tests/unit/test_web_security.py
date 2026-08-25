import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.application.use_cases.web_acquisition import WebAcquisitionService
from backend.app.core.errors import AnvikshikiDomainError
from backend.app.core.config import settings


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8080/admin",
        "http://localhost/internal",
        "http://10.0.0.4/metadata",
        "file:///etc/passwd",
        "http://user:password@example.com/private",
    ],
)
def test_web_acquisition_rejects_private_or_unsafe_destinations(url: str) -> None:
    with pytest.raises(AnvikshikiDomainError):
        WebAcquisitionService._validate_public_url(url)


def test_web_acquisition_accepts_public_https_destination() -> None:
    WebAcquisitionService._validate_public_url("https://example.com/research")


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get", new_callable=AsyncMock)
async def test_web_acquisition_rejects_unsupported_content_type(mock_get, tmp_path, monkeypatch) -> None:
    response = MagicMock(status_code=200, headers={"content-type": "application/octet-stream"})
    response.content = b"binary"
    response.text = "binary"
    response.raise_for_status.return_value = None
    mock_get.return_value = response
    monkeypatch.setattr(settings, "WEB_MAX_RESPONSE_BYTES", 1024)

    with pytest.raises(AnvikshikiDomainError, match="Unsupported web content type"):
        await WebAcquisitionService(None, None).acquire_url("https://example.com/file")


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get", new_callable=AsyncMock)
async def test_web_acquisition_rejects_oversized_response(mock_get, monkeypatch) -> None:
    response = MagicMock(status_code=200, headers={"content-type": "text/html"})
    response.content = b"x" * 1025
    response.text = "x" * 1025
    response.raise_for_status.return_value = None
    mock_get.return_value = response
    monkeypatch.setattr(settings, "WEB_MAX_RESPONSE_BYTES", 1024)

    with pytest.raises(AnvikshikiDomainError, match="size limit"):
        await WebAcquisitionService(None, None).acquire_url("https://example.com/large")
