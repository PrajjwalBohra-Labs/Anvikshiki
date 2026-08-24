from langgraph.graph import StateGraph, END
from backend.app.agents.state import InquiryState
from backend.app.agents.specialized_agents import SpecializedAgentNodes

def create_inquiry_graph():
    workflow = StateGraph(InquiryState)

    # Add specialized agent nodes
    workflow.add_node("research", SpecializedAgentNodes.research_node)
    workflow.add_node("critique", SpecializedAgentNodes.evidence_and_critic_node)
    workflow.add_node("analysis", SpecializedAgentNodes.philosophical_analyst_node)
    workflow.add_node("challenger", SpecializedAgentNodes.challenger_node)
    workflow.add_node("dialogue", SpecializedAgentNodes.dialogue_node)

    # Define linear execution with deterministic checks
    workflow.set_entry_point("research")
    workflow.add_edge("research", "critique")
    workflow.add_edge("critique", "analysis")
    workflow.add_edge("analysis", "challenger")
    workflow.add_edge("challenger", "dialogue")
    workflow.add_edge("dialogue", END)

    return workflow.compile()