import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import llm_adapter_dependency, memory_engine_dependency
from app.infrastructure.llm_adapter import LLMAdapter
from app.infrastructure.observability import get_trace_store
from app.main import app
from app.persistence import relational_db, vector_store
from app.services.memory.memory_engine import MemoryEngine


class FakeAdapter(LLMAdapter):
    def embed(self, text):
        return [1.0, 0.0, 0.0]

    def generate(self, prompt, **kwargs):
        return "[Doc A] a grounded answer."

    def stream(self, prompt, **kwargs):
        yield "a grounded answer."

    def summarize(self, text, **kwargs):
        raise NotImplementedError


@pytest.fixture(autouse=True)
def _init_stores_and_overrides():
    relational_db.init_db()
    vector_store.init_vector_store()
    app.dependency_overrides[llm_adapter_dependency] = lambda: FakeAdapter()
    app.dependency_overrides[memory_engine_dependency] = lambda: MemoryEngine()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_response_includes_trace_id_header(client):
    response = client.get("/health")
    assert "x-trace-id" in response.headers


def test_supplied_trace_id_header_is_honored(client):
    response = client.get("/health", headers={"X-Trace-Id": "my-custom-trace-id"})
    assert response.headers["x-trace-id"] == "my-custom-trace-id"


def test_get_trace_endpoint_returns_recorded_events_for_a_real_request(client):
    document_id = relational_db.create_document("Doc A", "path/a.txt", "hash")
    vector_store.insert_embedding(document_id, "a grounded fact.", [1.0, 0.0, 0.0])

    chat_response = client.post(
        "/chat", json={"query": "tell me the grounded fact"}, headers={"X-Trace-Id": "traceable-request-1"}
    )
    assert chat_response.status_code == 200

    trace_response = client.get("/trace/traceable-request-1")
    assert trace_response.status_code == 200
    events = trace_response.json()
    stages_seen = {e["stage"] for e in events}
    assert "http_request" in stages_seen
    assert "conversation_turn" in stages_seen
