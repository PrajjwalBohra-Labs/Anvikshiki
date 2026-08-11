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


def test_list_documents_returns_seeded_documents(client):
    relational_db.create_document("Doc A", "path/a.txt", "hash-a")
    relational_db.create_document("Doc B", "path/b.txt", "hash-b")

    response = client.get("/documents")
    assert response.status_code == 200
    titles = {d["title"] for d in response.json()}
    assert {"Doc A", "Doc B"}.issubset(titles)


def test_list_concepts_returns_seeded_concepts(client):
    relational_db.create_concept("Concept A", "desc")
    response = client.get("/concepts")
    assert response.status_code == 200
    assert any(c["name"] == "Concept A" for c in response.json())


def test_list_projects_returns_seeded_projects(client):
    relational_db.create_project("Anvikshiki", "test")
    response = client.get("/projects")
    assert response.status_code == 200
    assert any(p["name"] == "Anvikshiki" for p in response.json())


def test_session_history_returns_turns_after_a_chat(client):
    vector_store.insert_embedding(
        relational_db.create_document("Doc A", "path/a.txt", "hash"),
        "grounded fact.", [1.0, 0.0, 0.0],
    )
    chat_response = client.post("/chat", json={"query": "what is the grounded fact?"})
    session_id = chat_response.json()["session_id"]

    history_response = client.get(f"/sessions/{session_id}/history")
    assert history_response.status_code == 200
    turns = history_response.json()
    assert len(turns) == 1
    assert turns[0]["question_text"] == "what is the grounded fact?"


def test_session_history_returns_404_for_unknown_session(client):
    assert client.get("/sessions/does-not-exist/history").status_code == 404
