import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import llm_adapter_dependency, memory_engine_dependency
from app.infrastructure.llm_adapter import LLMAdapter
from app.main import app
from app.persistence import relational_db, vector_store
from app.services.memory.memory_engine import MemoryEngine


class FakeAdapter(LLMAdapter):
    def embed(self, text):
        return [1.0, 0.0, 0.0]

    def generate(self, prompt, **kwargs):
        return "[Doc A] a grounded test answer."

    def stream(self, prompt, **kwargs):
        for token in ["Hello", " ", "world"]:
            yield token

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


@pytest.fixture
def seeded_document():
    document_id = relational_db.create_document("Doc A", "path/a.txt", "hash")
    concept_id = relational_db.create_concept("Concept A", "desc")
    vector_store.insert_embedding(
        document_id, "grounded fact about Anvikshiki.", [1.0, 0.0, 0.0], metadata={"concept_id": concept_id}
    )
    return document_id, concept_id


def test_chat_endpoint_returns_delivered_response(client, seeded_document):
    response = client.post("/chat", json={"query": "what is the grounded fact?"})
    assert response.status_code == 200
    body = response.json()
    assert body["delivered"] is True
    assert body["response"] is not None
    assert "session_id" in body


def test_chat_endpoint_short_query_triggers_clarification(client, seeded_document):
    response = client.post("/chat", json={"query": "it"})
    assert response.status_code == 200
    assert "clarify" in " ".join(response.json()["state_trace"])


def test_chat_stream_endpoint_delivers_incrementally(client, seeded_document):
    with client.stream("POST", "/chat/stream", json={"query": "what is the grounded fact?"}) as response:
        assert response.status_code == 200
        lines = list(response.iter_lines())
    data_lines = [line for line in lines if line.startswith("data:")]
    assert len(data_lines) >= 3  # "Hello", " ", "world" -> at least 3 incremental events


def test_search_endpoint_returns_results(client, seeded_document):
    response = client.get("/search", params={"q": "grounded fact"})
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) >= 1
    assert results[0]["document_id"] == seeded_document[0]


def test_research_endpoint_returns_synthesis_and_references(client, seeded_document):
    response = client.post("/research", json={"question": "what is the grounded fact?"})
    assert response.status_code == 200
    body = response.json()
    assert body["synthesized_answer"]
    assert body["references"]
    assert "delivered" in body
    assert "validation_violations" in body


def test_document_upload_endpoint_ingests_a_real_file(client):
    files = {"file": ("note.txt", b"Anvikshiki test content for upload.", "text/plain")}
    response = client.post("/documents", files=files)
    assert response.status_code == 200
    body = response.json()
    assert body["chunk_count"] >= 1
    assert body["document_id"]


def test_get_document_returns_404_for_unknown_id(client):
    assert client.get("/documents/does-not-exist").status_code == 404


def test_project_create_and_get_roundtrip(client):
    create_response = client.post("/projects", json={"name": "Anvikshiki", "description": "test project"})
    assert create_response.status_code == 200
    project_id = create_response.json()["id"]

    get_response = client.get(f"/projects/{project_id}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Anvikshiki"


def test_concept_get_returns_seeded_concept(client, seeded_document):
    _, concept_id = seeded_document
    response = client.get(f"/concepts/{concept_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Concept A"


def test_session_create_and_get_roundtrip(client):
    create_response = client.post("/sessions")
    assert create_response.status_code == 200
    session_id = create_response.json()["id"]

    get_response = client.get(f"/sessions/{session_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == session_id


def test_settings_set_and_get_roundtrip(client):
    assert client.put("/settings", json={"key": "theme", "value": "dark"}).status_code == 200
    response = client.get("/settings/theme")
    assert response.status_code == 200
    assert response.json()["value"] == "dark"


def test_settings_get_returns_404_for_unknown_key(client):
    assert client.get("/settings/does-not-exist").status_code == 404



def test_chat_response_includes_real_verification_summary(client, seeded_document):
    response = client.post("/chat", json={"query": "what is the grounded fact?"})
    assert response.status_code == 200
    verification = response.json()["verification"]
    assert verification is not None
    assert verification["sources_checked"] >= 1
    assert "contradictions_detected" in verification
    assert "agreement_score" in verification


def test_session_summary_endpoint_returns_real_counts(client, seeded_document):
    chat_response = client.post("/chat", json={"query": "what is the grounded fact?"})
    session_id = chat_response.json()["session_id"]

    response = client.get(f"/sessions/{session_id}/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["message_count"] == 1
    assert body["verified_count"] == 1


def test_session_summary_returns_404_for_unknown_session(client):
    assert client.get("/sessions/does-not-exist/summary").status_code == 404


def test_concept_graph_endpoint_returns_nodes_and_edges(client, seeded_document):
    response = client.get("/concepts/graph")
    assert response.status_code == 200
    body = response.json()
    assert "nodes" in body
    assert "edges" in body


def test_chat_response_includes_context_summary(client, seeded_document):
    response = client.post("/chat", json={"query": "what is the grounded fact?"})
    context = response.json()["context"]
    assert context is not None
    assert context["retrieved_chunk_count"] >= 1


def test_research_response_includes_comparisons(client, seeded_document):
    response = client.post("/research", json={"question": "what is the grounded fact?"})
    body = response.json()
    assert "comparisons" in body
