"""
FastAPI dependency providers. Routes depend on these instead of
calling the underlying singletons directly, so tests can override
them via app.dependency_overrides.
"""

from app.infrastructure.event_bus import EventBus, get_event_bus
from app.infrastructure.llm_adapter import LLMAdapter, get_llm_adapter
from app.services.memory.memory_engine import MemoryEngine, get_memory_engine


def llm_adapter_dependency() -> LLMAdapter:
    return get_llm_adapter()


def memory_engine_dependency() -> MemoryEngine:
    return get_memory_engine()


def event_bus_dependency() -> EventBus:
    return get_event_bus()
