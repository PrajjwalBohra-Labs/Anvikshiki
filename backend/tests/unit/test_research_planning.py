from backend.app.application.orchestration.research_workflow import (
    research_depth_for_query,
    should_run_web_research,
)
from backend.app.core.config import RuntimeProfile, settings


def test_complex_inquiry_gets_deep_budget() -> None:
    query = "What are the correlations between perception, inference, comparison and verbal testimony?"

    assert research_depth_for_query(query) == "deep"
    assert research_depth_for_query(query, "brief") == "brief"


def test_web_research_is_required_when_local_evidence_is_missing(monkeypatch) -> None:
    monkeypatch.setattr(settings, "RUNTIME_PROFILE", RuntimeProfile.DEVELOPMENT)
    monkeypatch.setattr(settings, "ENABLE_WEB_RETRIEVAL", True)

    assert should_run_web_research("What is pramana?", "standard", 0)
    assert should_run_web_research("Compare these schools", "deep", 2)
    assert not should_run_web_research("What is pramana?", "standard", 2)


def test_isolated_tests_never_depend_on_external_web_search(monkeypatch) -> None:
    monkeypatch.setattr(settings, "RUNTIME_PROFILE", RuntimeProfile.TEST)
    monkeypatch.setattr(settings, "ENABLE_WEB_RETRIEVAL", True)

    assert not should_run_web_research("What is pramana?", "standard", 0)
