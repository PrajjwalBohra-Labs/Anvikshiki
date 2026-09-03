from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph


class ResearchState(TypedDict):
    """Typed research state definition for LangGraph execution."""
    query: str
    validated: bool
    status: str
    error: str | None
    history: list[str]

def node_research_input(state: ResearchState) -> ResearchState:
    """Initial research input node."""
    history = list(state.get("history", []))
    history.append("Input received and processed.")
    return {
        "query": state["query"],
        "validated": False,
        "status": "INPUT_PROCESSED",
        "error": None,
        "history": history
    }

def node_validate(state: ResearchState) -> ResearchState:
    """Validation node checking query integrity and safety."""
    history = list(state.get("history", []))
    query = state.get("query", "")
    
    if not query or len(query.strip()) == 0:
        return {
            **state,
            "validated": False,
            "status": "FAILED",
            "error": "Empty or invalid research query.",
            "history": history + ["Validation failed: Empty query."]
        }
    
    history.append("Validation passed successfully.")
    return {
        **state,
        "validated": True,
        "status": "COMPLETED",
        "error": None,
        "history": history
    }

def build_research_graph() -> Any:
    """Constructs the minimal deterministic research graph with checkpointing memory."""
    workflow = StateGraph(ResearchState)
    
    workflow.add_node("research_input", node_research_input)
    workflow.add_node("validate", node_validate)
    
    workflow.add_edge(START, "research_input")
    workflow.add_edge("research_input", "validate")
    workflow.add_edge("validate", END)
    
    memory = MemorySaver()
    graph = workflow.compile(checkpointer=memory)
    return graph