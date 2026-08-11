import pytest

from app.infrastructure.event_bus import EventBus, EventName
from app.persistence import relational_db, vector_store
from app.services.memory.memory_engine import MemoryEngine


@pytest.fixture(autouse=True)
def _init_stores():
    relational_db.init_db()
    vector_store.init_vector_store()


def test_remember_publishes_memory_updated():
    bus = EventBus()
    received = []
    bus.subscribe(EventName.MEMORY_UPDATED, lambda e: received.append(e))

    engine = MemoryEngine(event_bus=bus)
    record = engine.remember({"content": "a fact", "tier": "working"})

    assert len(received) == 1
    assert received[0].payload["memory_id"] == record.id
    assert received[0].payload["tier"] == "working"
