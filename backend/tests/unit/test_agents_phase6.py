import pytest
from backend.app.agents.supervisor import create_inquiry_graph
from backend.app.domain.models.enums import SourceType

def test_inquiry_graph_workflow_execution():
    graph = create_inquiry_graph()

    initial_state = {
        "query": "Is perception (pratyaksha) an infallible pramana?",
        "user_id": "test_user_1",
        "sub_questions": [],
        "retrieved_passages": [
            {
                "id": "p1",
                "content": "Perception is produced by sense-object contact but is conditioned by sensory validity.",
                "source_type": SourceType.PRIMARY.value,
                "author": "Gautama",
                "original_language": "Sanskrit",
                "translator": "Jha",
                "translation_year": 1915,
                "citation_string": "Nyaya Sutra 1.1.4"
            }
        ],
        "extracted_claims": [
            {
                "id": "c1",
                "statement": "Perception is conditioned by sense-object contact and sensory validity."
            }
        ],
        "critique_findings": [],
        "reconstructed_arguments": [],
        "counterarguments": [],
        "uncertainties": [],
        "final_synthesis": None,
        "current_step": "init"
    }

    final_state = graph.invoke(initial_state)

    assert final_state["current_step"] == "complete"
    assert len(final_state["sub_questions"]) >= 1
    assert len(final_state["critique_findings"]) >= 1
    assert any("TRANSLATION_MEDIATION" in str(f) or "HISTORICAL_ERA" in str(f) for f in final_state["critique_findings"])
    assert len(final_state["reconstructed_arguments"]) == 1
    assert len(final_state["counterarguments"]) >= 1
    assert final_state["final_synthesis"] is not None
    assert "Points of Critical Examination" in final_state["final_synthesis"]