import pytest

from backend.app.application.orchestration.graph_foundation import build_research_graph


@pytest.mark.asyncio
async def test_langgraph_execution_and_checkpointing():
    graph = build_research_graph()
    
    thread_config = {"configurable": {"thread_id": "test_thread_123"}}
    initial_state = {
        "query": "What are the core pillars of epistemology?",
        "validated": False,
        "status": "PENDING",
        "error": None,
        "history": []
    }
    
    # Run graph execution
    result = await graph.ainvoke(initial_state, config=thread_config)
    
    assert result["validated"] is True
    assert result["status"] == "COMPLETED"
    assert len(result["history"]) == 2
    assert "Validation passed successfully." in result["history"][1]

    # Test Checkpoint retrieval via thread state
    saved_state = await graph.aget_state(thread_config)
    assert saved_state.values["status"] == "COMPLETED"