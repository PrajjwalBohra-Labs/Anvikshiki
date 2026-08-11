from app.infrastructure.event_bus import Event, EventBus, EventName


def test_subscriber_receives_published_event():
    bus = EventBus()
    received = []
    bus.subscribe(EventName.DOCUMENT_IMPORTED, lambda event: received.append(event))

    bus.publish(EventName.DOCUMENT_IMPORTED, {"document_id": "doc-1"})

    assert len(received) == 1
    assert received[0].payload["document_id"] == "doc-1"


def test_second_subscriber_also_observes_the_same_event():
    bus = EventBus()
    first_seen, second_seen = [], []
    bus.subscribe(EventName.MEMORY_UPDATED, lambda event: first_seen.append(event))
    bus.subscribe(EventName.MEMORY_UPDATED, lambda event: second_seen.append(event))

    bus.publish(EventName.MEMORY_UPDATED, {"memory_id": "m-1"})

    assert len(first_seen) == 1
    assert len(second_seen) == 1


def test_unsubscribed_event_names_do_not_call_unrelated_handlers():
    bus = EventBus()
    received = []
    bus.subscribe(EventName.PROJECT_SAVED, lambda event: received.append(event))

    bus.publish(EventName.CONVERSATION_STARTED, {"session_id": "s-1"})

    assert received == []


def test_event_history_records_published_events():
    bus = EventBus()
    bus.publish(EventName.EMBEDDING_CREATED, {"chunk_id": "c-1"})
    assert len(bus.history) == 1
    assert isinstance(bus.history[0], Event)
