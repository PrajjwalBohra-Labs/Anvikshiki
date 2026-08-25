import pytest

from backend.app.application.use_cases.web_acquisition import WebAcquisitionService
from backend.app.core.errors import AnvikshikiDomainError


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
