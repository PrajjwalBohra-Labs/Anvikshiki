from typing import TypedDict, List, Optional, Dict, Any
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

class CoordinatorState(TypedDict):
    """Typed state for the Research Coordinator workflow."""
    query: str
    research_depth: str  # "shallow" or "deep"
    retrieval_needed: bool
    required_roles: List[str]
    is_complex: bool
    human_input_needed: bool
    status: str
    history: List[str]

def coordinator_node(state: CoordinatorState) -> CoordinatorState:
    """
    Analyzes query complexity, research depth, retrieval necessity, 
    and determines which specialist roles are required while preventing unnecessary agent execution.
    """
    query = state.get("query", "").lower()
    history = list(state.get("history", []))
    
    # Determine complexity and depth based on query structure
    is_complex = len(query.split()) > 10 or any(w in query for w in ["compare", "analyze", "critique", "contradiction", "evaluate"])
    retrieval_needed = not any(w in query for w in ["hello", "hi", "help"])
    
    roles = []
    if is_complex:
        roles = ["evidence_analyst", "source_critic", "philosophical_analyst"]
        depth = "deep"
    else:
        roles = ["evidence_analyst"]
        depth = "shallow"
        
    history.append(f"Coordinator routed query: complex={is_complex}, depth={depth}, roles={roles}")
    
    return {
        **state,
        "research_depth": depth,
        "retrieval_needed": retrieval_needed,
        "required_roles": roles,
        "is_complex": is_complex,
        "human_input_needed": False,
        "status": "COORDINATED",
        "history": history
    }

def simple_workflow_node(state: CoordinatorState) -> CoordinatorState:
    """Executes streamlined workflow for simple queries, avoiding unnecessary agent overhead."""
    history = list(state.get("history", []))
    history.append("Executed simple workflow path.")
    return {**state, "status": "COMPLETED_SIMPLE", "history": history}

def complex_workflow_node(state: CoordinatorState) -> CoordinatorState:
    """Executes multi-step specialist workflow for complex philosophical/scientific inquiries."""
    history = list(state.get("history", []))
    history.append(f"Executed complex workflow path with roles: {state.get('required_roles')}")
    return {**state, "status": "COMPLETED_COMPLEX", "history": history}

def route_workflow(state: CoordinatorState) -> str:
    """Conditional router based on query complexity."""
    if state.get("is_complex", False):
        return "complex_workflow"
    return "simple_workflow"

def build_coordinator_graph() -> Any:
    """Constructs the coordinator graph with conditional routing."""
    workflow = StateGraph(CoordinatorState)
    
    workflow.add_node("coordinator", coordinator_node)
    workflow.add_node("simple_workflow", simple_workflow_node)
    workflow.add_node("complex_workflow", complex_workflow_node)
    
    workflow.add_edge(START, "coordinator")
    workflow.add_conditional_edges(
        "coordinator",
        route_workflow,
        {
            "simple_workflow": "simple_workflow",
            "complex_workflow": "complex_workflow"
        }
    )
    workflow.add_edge("simple_workflow", END)
    workflow.add_edge("complex_workflow", END)
    
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)