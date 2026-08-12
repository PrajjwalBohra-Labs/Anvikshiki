"""
End-to-End (§31). The only test in the suite that talks to a real,
locally running Ollama instance -- everything else in this project
uses injected adapters specifically to avoid that dependency, so the
suite stays fast and deterministic by default. This test auto-skips
(does not fail) when Ollama isn't reachable, so `pytest` always
"just works" regardless of whether Ollama happens to be running.
"""

import httpx
import pytest

from app.config import get_settings
from app.persistence import relational_db, vector_store
from app.services.conversation.conversation_controller import handle_message
from app.services.knowledge.ingestion import ingest_document
from app.services.memory.memory_engine import MemoryEngine


def _ollama_available() -> bool:
    try:
        settings = get_settings()
        response = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=2.0)
        return response.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _ollama_available(), reason="Ollama is not reachable at the configured base URL"
)


@pytest.fixture(autouse=True)
def _init_stores():
    relational_db.init_db()
    vector_store.init_vector_store()


def test_real_end_to_end_conversation_against_live_ollama():
    """Ingest a real document with real embeddings, ask a real
    question, get a real generated and validated answer -- no mocks
    anywhere in this test."""
    content = (
        b"Anvikshiki is a modular cognitive architecture. It separates "
        b"reasoning from generation and keeps knowledge storage independent "
        b"from reasoning, per its core design principles."
    )
    ingest_document("e2e_test_doc.txt", content, title="E2E Test Doc")

    result = handle_message("what does Anvikshiki separate from what?", memory_engine=MemoryEngine())

    assert result.response is not None
    assert result.reasoning is not None
    assert result.reasoning.confidence is not None
    assert 0.0 <= result.reasoning.confidence.overall <= 1.0
