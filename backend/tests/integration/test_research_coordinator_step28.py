import pytest

from backend.app.application.orchestration.research_coordinator import (
    build_coordinator_graph,
)


@pytest.mark.asyncio
async def test_research_coordinator_routing():
    graph = build_coordinator_graph()
    
    # 1. Test Simple Question Routing
    simple_state = {
        "query": "What is Pratyaksha?",
        "research_depth": "shallow",
        "retrieval_needed": True,
        "required_roles": [],
        "is_complex": False,
        "human_input_needed": False,
        "status": "PENDING",
        "history": []
    }
    res_simple = await graph.ainvoke(simple_state, config={"configurable": {"thread_id": "thread_simple"}})
    assert res_simple["status"] == "COMPLETED_SIMPLE"
    assert res_simple["is_complex"] is False

    # 2. Test Complex Question Routing
    complex_state = {
        "query": "Compare and critically analyze the interpretations of perception across Nyaya and Buddhist epistemology, citing primary source contradictions.",
        "research_depth": "shallow",
        "retrieval_needed": True,
        "required_roles": [],
        "is_complex": False,
        "human_input_needed": False,
        "status": "PENDING",
        "history": []
    }
    res_complex = await graph.ainvoke(complex_state, config={"configurable": {"thread_id": "thread_complex"}})
    assert res_complex["status"] == "COMPLETED_COMPLEX"
    assert res_complex["is_complex"] is True
    assert len(res_complex["required_roles"]) > 0