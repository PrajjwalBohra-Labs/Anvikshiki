import pytest
from pydantic import ValidationError

from backend.app.api.v1.schemas.dtos import ResearchRunRequestDTO


def test_research_request_rejects_oversized_query() -> None:
    with pytest.raises(ValidationError):
        ResearchRunRequestDTO(user_id="user", query="x" * 10_001)


def test_research_request_rejects_empty_user_id() -> None:
    with pytest.raises(ValidationError):
        ResearchRunRequestDTO(user_id="", query="valid research question")
