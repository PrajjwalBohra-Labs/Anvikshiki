"""
Event Bus (§25 Events): in-process pub/sub, no external broker (§37
tech decision). Named events, exactly as listed in §25:
DocumentImported, EmbeddingCreated, ConversationStarted,
ReasoningCompleted, MemoryUpdated, ProjectSaved.

Services subscribe rather than tightly couple (§25) -- this bus lets
other parts of the system observe what happened without the
publisher needing to know who's listening.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from functools import lru_cache
from typing import Callable


class EventName(str, Enum):
    DOCUMENT_IMPORTED = "DocumentImported"
    EMBEDDING_CREATED = "EmbeddingCreated"
    CONVERSATION_STARTED = "ConversationStarted"
    REASONING_COMPLETED = "ReasoningCompleted"
    MEMORY_UPDATED = "MemoryUpdated"
    PROJECT_SAVED = "ProjectSaved"


@dataclass
class Event:
    name: EventName
    payload: dict = field(default_factory=dict)
    occurred_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


Handler = Callable[[Event], None]


class EventBus:
    """In-process pub/sub -- no external broker, per §37 tech decision."""

    def __init__(self):
        self._subscribers: dict[EventName, list[Handler]] = defaultdict(list)
        self._history: list[Event] = []  # useful for tests/debugging, not a durable log

    def subscribe(self, event_name: EventName, handler: Handler) -> None:
        self._subscribers[event_name].append(handler)

    def publish(self, event_name: EventName, payload: dict | None = None) -> Event:
        event = Event(name=event_name, payload=payload or {})
        self._history.append(event)
        for handler in self._subscribers[event_name]:
            handler(event)
        return event

    @property
    def history(self) -> list[Event]:
        return list(self._history)


@lru_cache
def get_event_bus() -> EventBus:
    return EventBus()
