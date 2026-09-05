from backend.app.application.orchestration.research_workflow import (
    append_citation_ledger,
    merge_research_evidence,
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


def test_acquired_web_evidence_enters_the_synthesis_set() -> None:
    local = [{"passage_id": "local", "source_id": "book", "relevance_score": 0.99, "rank": 1}]
    web = [
        {
            "passage_id": "web-1",
            "source_id": "web-source",
            "relevance_score": 0.2,
            "rank": 3,
            "citation_string": "Authoritative page (Retrieved from https://example.org/page)",
        }
    ]

    selected = merge_research_evidence(local, web, limit=2)
    assert [item["passage_id"] for item in selected] == ["web-1", "local"]

    response = append_citation_ledger("The evidence supports this cautiously. [P1]", selected)
    assert "[P1] Authoritative page (Retrieved from https://example.org/page)" in response
    assert "[P2]" not in response
