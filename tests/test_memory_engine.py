import pytest

from app.persistence import relational_db, vector_store
from app.services.memory.memory_engine import (
    MemoryEngine,
    MemoryTier,
    get_memory_engine,
)


@pytest.fixture(autouse=True)
def _init_stores():
    relational_db.init_db()
    vector_store.init_vector_store()


@pytest.fixture
def engine():
    return MemoryEngine()


@pytest.mark.parametrize(
    "tier",
    [
        MemoryTier.WORKING,
        MemoryTier.DIALOGUE,
        MemoryTier.SESSION,
        MemoryTier.CONCEPT,
        MemoryTier.PROJECT,
        MemoryTier.RESEARCH,
        MemoryTier.SYSTEM,
    ],
)
def test_write_and_read_each_tier_independently(engine, tier):
    record = engine.remember({"content": f"a fact for {tier.value}", "tier": tier.value})
    read_back = engine.recall(tier, record.id)

    assert read_back is not None
    assert read_back.content == f"a fact for {tier.value}"
    assert read_back.tier == tier


def test_tiers_are_isolated_from_each_other(engine):
    working_record = engine.remember({"content": "working fact", "tier": "working"})
    # a working-tier id must not resolve under a different tier
    assert engine.recall(MemoryTier.DIALOGUE, working_record.id) is None


def test_persistent_tier_survives_across_engine_instances():
    first_engine = MemoryEngine()
    record = first_engine.remember({"content": "concept insight", "tier": "concept"})

    second_engine = MemoryEngine()  # simulates a fresh process using the same DB
    read_back = second_engine.recall(MemoryTier.CONCEPT, record.id)

    assert read_back is not None
    assert read_back.content == "concept insight"


def test_working_tier_does_not_survive_across_engine_instances():
    first_engine = MemoryEngine()
    record = first_engine.remember({"content": "ephemeral fact", "tier": "working"})

    second_engine = MemoryEngine()
    assert second_engine.recall(MemoryTier.WORKING, record.id) is None


def test_remember_defaults_to_working_tier_without_hint(engine):
    record = engine.remember({"content": "no tier specified"})
    assert record.tier == MemoryTier.WORKING


def test_remember_rejects_empty_content(engine):
    with pytest.raises(ValueError):
        engine.remember({"content": "", "tier": "working"})


def test_get_memory_engine_is_a_singleton():
    assert get_memory_engine() is get_memory_engine()
