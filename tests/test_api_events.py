import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import event_bus_dependency, llm_adapter_dependency, memory_engine_dependency
from app.infrastructure.event_bus import EventBus, EventName
from app.infrastructure.llm_adapter import LLMAdapter
from app.main import app
from app.persistence import relational_db, vector_store
from app.services.memory.memory_engine import MemoryEngine


class FakeAdapter(LLMAdapter):
    def embed(self, text):
        return [1.0, 0.0, 0.0]

    def generate(self, prompt, **kwargs):
        return "a response"

    def stream(self, prompt, **kwargs):
        yield "a response"

    def summarize(self, text, **kwargs):
        raise NotImplementedError


@pytest.fixture(autouse=True)
def _init_stores():
    relational_db.init_db()
    vector_store.init_vector_store()
    app.dependency_overrides[llm_adapter_dependency] = lambda: FakeAdapter()
    app.dependency_overrides[memory_engine_dependency] = lambda: MemoryEngine()
    yield
    app.dependency_overrides.clear()


def test_creating_a_project_publishes_project_saved():
    bus = EventBus()
    received = []
    bus.subscribe(EventName.PROJECT_SAVED, lambda e: received.append(e))
    app.dependency_overrides[event_bus_dependency] = lambda: bus

    client = TestClient(app)
    response = client.post("/projects", json={"name": "Anvikshiki", "description": "test"})

    assert response.status_code == 200
    assert len(received) == 1
    assert received[0].payload["name"] == "Anvikshiki"
