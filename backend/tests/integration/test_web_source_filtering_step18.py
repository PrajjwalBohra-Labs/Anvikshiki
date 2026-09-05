from backend.app.application.use_cases.web_source_filtering import (
    WebSourceFilteringService,
)
from backend.app.domain.models.enums import SourceType


def test_web_source_filtering_checkpoints():
    service = WebSourceFilteringService()

    # 1. Test Preferred Scholarly Source (Evidence-based & Explainable)
    res_pref = service.evaluate_source("https://plato.stanford.edu/entries/epistemology/")
    assert res_pref["classification"] == "PREFERRED"
    assert res_pref["source_type"] == SourceType.PRIMARY
    assert "reason" in res_pref  # Checkpoint: Filters are explainable
    assert len(res_pref["reason"]) > 0

    # 2. Test Discovery-Only Source
    res_disc = service.evaluate_source("https://en.wikipedia.org/wiki/Pramana")
    assert res_disc["classification"] == "DISCOVERY_ONLY"
    assert res_disc["source_type"] == SourceType.DISCOVERY_ONLY
    assert "reason" in res_disc

    # 3. Test Rejected Social Media Source
    res_rej = service.evaluate_source("https://twitter.com/some_user/status/12345")
    assert res_rej["classification"] == "REJECTED"
    assert res_rej["source_type"] == SourceType.UNVERIFIED
    assert "social media" in res_rej["reason"].lower()