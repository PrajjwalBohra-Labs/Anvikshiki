from app.infrastructure.observability import (
    get_current_trace_id,
    get_trace_store,
    new_trace_id,
    record_event,
    set_current_trace_id,
    trace_stage,
)


def test_record_event_is_a_noop_without_an_active_trace():
    get_trace_store().clear()
    record_event("some_stage", "metric", value=1)
    assert get_trace_store().get_trace("nonexistent") == []


def test_record_event_stores_event_under_current_trace_id():
    trace_id = new_trace_id()
    set_current_trace_id(trace_id)

    record_event("test_stage", "metric", value=42)

    events = get_trace_store().get_trace(trace_id)
    assert len(events) == 1
    assert events[0].stage == "test_stage"
    assert events[0].metadata["value"] == 42


def test_trace_stage_records_start_and_end_with_duration():
    trace_id = new_trace_id()
    set_current_trace_id(trace_id)

    with trace_stage("my_stage"):
        pass

    events = get_trace_store().get_trace(trace_id)
    event_types = [e.event_type for e in events]
    assert event_types == ["stage_start", "stage_end"]
    assert events[1].duration_ms is not None


def test_trace_stage_records_failure_and_reraises():
    trace_id = new_trace_id()
    set_current_trace_id(trace_id)

    try:
        with trace_stage("failing_stage"):
            raise ValueError("boom")
    except ValueError:
        pass

    events = get_trace_store().get_trace(trace_id)
    assert any(e.event_type == "failure" and e.metadata["error_type"] == "ValueError" for e in events)
